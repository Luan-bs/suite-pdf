"""
Módulo de Compressão Universal de PDFs.
Aplica desduplicação de fluxos, detecção geométrica e tonal de transparência (SMask Modo A/B),
redimensionamento via Lanczos e descarte de glifos órfãos de fontes.
"""

from collections.abc import Callable
import io
from pathlib import Path
from typing import Any
import zlib
from PIL import Image
import pymupdf as fitz


def _mapear_imagens_sobre_fundo_nao_branco(doc: fitz.Document) -> set[int]:
    """
    Identifica quais imagens com SMask estão posicionadas sobre um plano de fundo
    não-branco (outra imagem de slide ou forma vetorial colorida/escura).
    Quando uma imagem com SMask intersecta outro elemento visual de fundo (> 5% da área),
    seu canal de transparência (/SMask) deve ser preservado (Modo B).
    """
    imgs_sobre_fundo: set[int] = set()

    for page in doc:
        # 1. Coleta retângulos de desenhos vetoriais com preenchimento não-branco
        retangulos_coloridos: list[fitz.Rect] = []
        try:
            for d in page.get_drawings():
                r = d.get("rect")
                fill = d.get("fill")
                if r and fill and any(c < 0.98 for c in fill) and r.width > 5 and r.height > 5:
                    retangulos_coloridos.append(r)
        except Exception:
            pass

        # 2. Coleta retângulos de todas as imagens presentes na página
        rects_imagens: list[tuple[int, int, fitz.Rect]] = []
        for img in page.get_images():
            xref = img[0]
            smask = img[1]
            try:
                for r in page.get_image_rects(xref):
                    if r.width > 0 and r.height > 0:
                        rects_imagens.append((xref, smask, r))
            except Exception:
                pass

        # 3. Verifica interseção geométrica para cada imagem que possui SMask
        for i, (xref, smask, r) in enumerate(rects_imagens):
            if smask <= 0 or xref in imgs_sobre_fundo:
                continue

            area_img = r.width * r.height
            if area_img <= 0:
                continue

            # Intersecta outra imagem na mesma página (ex: fundo de slide)?
            for j, (_xref2, _smask2, r2) in enumerate(rects_imagens):
                if i != j and r.intersects(r2):
                    inter = r & r2
                    if (inter.width * inter.height) > 0.05 * area_img:
                        imgs_sobre_fundo.add(xref)
                        break

            # Intersecta célula/retângulo vetorial colorido (ex: cabeçalho colorido)?
            if xref not in imgs_sobre_fundo:
                for cr in retangulos_coloridos:
                    if r.intersects(cr):
                        inter = r & cr
                        if (inter.width * inter.height) > 0.05 * area_img:
                            imgs_sobre_fundo.add(xref)
                            break

    return imgs_sobre_fundo


def _deve_preservar_smask(
    im_base: Image.Image,
    im_mask: Image.Image,
    sobre_fundo_nao_branco: bool,
) -> bool:
    """
    Classificador determinístico (Modo A vs. Modo B):
    - Retorna True (Modo B: Preservar /SMask) quando:
      1. A imagem intersecta geometricamente outra imagem ou forma colorida na página;
      2. Ou mais de 90% dos pixels visíveis da imagem base são brancos puros (>= 245),
         evitando que logos/textos brancos desapareçam ao serem colados sobre branco.
    - Retorna False (Modo A: Achatar sobre branco e remover /SMask) quando a imagem
      está sobre o papel branco da página (ex: fluxogramas e diagramas em documentos A4).
    """
    if sobre_fundo_nao_branco:
        return True

    mask_bytes = im_mask.tobytes()
    total_px = len(mask_bytes)
    if total_px == 0:
        return False

    passo = max(1, total_px // 16384)
    amostra_mask = mask_bytes[::passo]
    gray_bytes = im_base.convert("L").tobytes()[::passo]

    visiveis = [g for g, m in zip(gray_bytes, amostra_mask) if m > 128]
    if visiveis:
        proporcao_branco_puro = sum(1 for g in visiveis if g >= 245) / len(visiveis)
        if proporcao_branco_puro > 0.90:
            return True

    return False


def _processar_imagem(
    doc: fitz.Document,
    xref: int,
    smask_xref: int | None,
    sobre_fundo_nao_branco: bool,
    qualidade: int,
    dimensao_maxima: int,
) -> dict[str, Any]:
    """
    Otimiza uma imagem extraída do PDF aplicando detecção adaptativa de SMask.
    """
    pix_base = fitz.Pixmap(doc, xref)

    # 1. Carrega o Pixmap base no Pillow
    if pix_base.alpha:
        im_base = Image.frombytes("RGBA", (pix_base.width, pix_base.height), pix_base.samples)
    elif pix_base.n == 1:
        im_base = Image.frombytes("L", (pix_base.width, pix_base.height), pix_base.samples)
    else:
        im_base = Image.frombytes("RGB", (pix_base.width, pix_base.height), pix_base.samples)

    preservar_smask = False
    im_mask: Image.Image | None = None

    # 2. Avaliação inteligente de transparência / SMask (Modo A vs. Modo B)
    if smask_xref and smask_xref > 0:
        try:
            mask_pix = fitz.Pixmap(doc, smask_xref)
            im_mask = Image.frombytes("L", (mask_pix.width, mask_pix.height), mask_pix.samples)
            if im_mask.size != im_base.size:
                im_mask = im_mask.resize(im_base.size, Image.Resampling.LANCZOS)

            preservar_smask = _deve_preservar_smask(im_base, im_mask, sobre_fundo_nao_branco)

            if preservar_smask:
                # Modo B: Mantém os canais de cor originais sem achatar sobre branco
                pil_img = im_base if im_base.mode == "L" else im_base.convert("RGB")
            else:
                # Modo A: Imagem sobre papel branco -> achata sobre branco e descarta SMask
                bg = Image.new("RGB", im_base.size, (255, 255, 255))
                bg.paste(im_base.convert("RGB"), (0, 0), mask=im_mask)
                pil_img = bg
        except Exception:
            pil_img = im_base.convert("RGB")
            preservar_smask = False
    elif im_base.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im_base.size, (255, 255, 255))
        alpha = im_base.split()[-1]
        bg.paste(im_base.convert("RGB"), (0, 0), mask=alpha)
        pil_img = bg
    elif im_base.mode == "L":
        pil_img = im_base
    else:
        pil_img = im_base.convert("RGB")

    # 3. Redimensionamento inteligente preservando proporção
    w, h = pil_img.size
    if max(w, h) > dimensao_maxima:
        escala = dimensao_maxima / max(w, h)
        w, h = max(1, int(w * escala)), max(1, int(h * escala))
        pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)

    # 4. Codificação da imagem base em JPEG com árvore Huffman otimizada
    buffer = io.BytesIO()
    pil_img.save(buffer, format="JPEG", quality=qualidade, optimize=True)
    jpeg_bytes = buffer.getvalue()
    colorspace = "/DeviceGray" if pil_img.mode == "L" else "/DeviceRGB"

    # 5. Se Modo B (preservar SMask), redimensiona e comprime a máscara com min(Flate, DCT)
    mask_bytes: bytes | None = None
    mask_filter: str = "/FlateDecode"
    if preservar_smask and im_mask is not None:
        if im_mask.size != (w, h):
            im_mask = im_mask.resize((w, h), Image.Resampling.LANCZOS)

        flate_candidate = zlib.compress(im_mask.tobytes(), level=9)
        buf_mask = io.BytesIO()
        im_mask.save(buf_mask, format="JPEG", quality=qualidade, optimize=True)
        dct_candidate = buf_mask.getvalue()

        if len(dct_candidate) < len(flate_candidate):
            mask_bytes = dct_candidate
            mask_filter = "/DCTDecode"
        else:
            mask_bytes = flate_candidate
            mask_filter = "/FlateDecode"

    return {
        "jpeg_bytes": jpeg_bytes,
        "filter": "/DCTDecode",
        "colorspace": colorspace,
        "width": w,
        "height": h,
        "preservar_smask": preservar_smask,
        "mask_bytes": mask_bytes,
        "mask_filter": mask_filter,
    }


def comprimir_pdf(
    caminho_entrada: str | Path,
    caminho_saida: str | Path,
    qualidade: int = 68,
    dimensao_maxima: int = 850,
    senha: str | None = None,
    forcar_salvamento: bool = False,
    callback_progresso: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """
    Comprime um PDF reduzindo imagens e limpando a estrutura interna.

    :param caminho_entrada: Arquivo PDF original.
    :param caminho_saida: Arquivo PDF de destino.
    :param qualidade: Qualidade JPEG (1 a 100).
    :param dimensao_maxima: Resolução máxima de tela/imagem.
    :param senha: Senha para PDFs protegidos.
    :param forcar_salvamento: Salva mesmo se o tamanho final for maior.
    :param callback_progresso: Função callback(progresso_0_a_1, mensagem).
    :return: Dicionário com métricas do processo.
    """
    caminho_in = Path(caminho_entrada).resolve()
    caminho_out = Path(caminho_saida).resolve()

    if not caminho_in.exists():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {caminho_in}")

    def reportar(pct: float, msg: str):
        if callback_progresso:
            callback_progresso(pct, msg)

    reportar(0.05, f"Abrindo documento: {caminho_in.name}...")
    tamanho_original = caminho_in.stat().st_size / 1024

    doc = fitz.open(caminho_in)

    if doc.is_encrypted:
        if senha is not None:
            if not doc.authenticate(senha):
                doc.close()
                raise PermissionError("Senha incorreta para o PDF.")
        else:
            if not doc.authenticate(""):
                doc.close()
                raise PermissionError("O documento está criptografado e requer senha.")

    reportar(0.15, "Analisando camadas de página e máscaras de transparência...")
    imgs_sobre_fundo = _mapear_imagens_sobre_fundo_nao_branco(doc)

    img_smasks: dict[int, int | None] = {}
    for page in doc:
        for img in page.get_images():
            xref = img[0]
            smask = img[1]
            if xref not in img_smasks:
                img_smasks[xref] = smask if smask > 0 else None

    total_imagens = len(img_smasks)
    otimizadas = 0
    smasks_processados: set[int] = set()

    if total_imagens > 0:
        for idx, (xref, smask_xref) in enumerate(sorted(img_smasks.items()), start=1):
            pct = 0.20 + (0.50 * (idx / total_imagens))
            reportar(pct, f"Otimizando imagem {idx}/{total_imagens}...")
            try:
                stream_original = doc.xref_stream_raw(xref) or b""
                stream_smask_orig = (
                    (doc.xref_stream_raw(smask_xref) or b"") if (smask_xref and smask_xref > 0) else b""
                )

                info = _processar_imagem(
                    doc=doc,
                    xref=xref,
                    smask_xref=smask_xref,
                    sobre_fundo_nao_branco=(xref in imgs_sobre_fundo),
                    qualidade=qualidade,
                    dimensao_maxima=dimensao_maxima,
                )

                novos_bytes = info["jpeg_bytes"]
                w, h = info["width"], info["height"]
                colorspace = info["colorspace"]
                filtro = info["filter"]

                if info["preservar_smask"] and smask_xref and info["mask_bytes"]:
                    mask_bytes = info["mask_bytes"]
                    peso_antes = len(stream_original) + len(stream_smask_orig)
                    peso_depois = len(novos_bytes) + len(mask_bytes)

                    if peso_depois < peso_antes:
                        obj_def = (
                            f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
                            f"/ColorSpace {colorspace} /BitsPerComponent 8 /SMask {smask_xref} 0 R >>"
                        )
                        doc.update_object(xref, obj_def)
                        doc.update_stream(xref, novos_bytes, new=False, compress=False)
                        doc.xref_set_key(xref, "Filter", filtro)

                        if smask_xref not in smasks_processados:
                            smask_def = (
                                f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
                                f"/ColorSpace /DeviceGray /BitsPerComponent 8 >>"
                            )
                            doc.update_object(smask_xref, smask_def)
                            doc.update_stream(smask_xref, mask_bytes, new=False, compress=False)
                            doc.xref_set_key(smask_xref, "Filter", info["mask_filter"])
                            smasks_processados.add(smask_xref)

                        otimizadas += 1
                else:
                    if novos_bytes and len(novos_bytes) < len(stream_original):
                        obj_def = (
                            f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
                            f"/ColorSpace {colorspace} /BitsPerComponent 8 >>"
                        )
                        doc.update_object(xref, obj_def)
                        doc.update_stream(xref, novos_bytes, new=False, compress=False)
                        doc.xref_set_key(xref, "Filter", filtro)
                        otimizadas += 1
            except Exception:
                pass
    else:
        reportar(0.60, "Nenhuma imagem embutida encontrada. Otimizando estrutura...")

    reportar(0.75, "Otimizando glifos de fontes (subsetting)...")
    try:
        doc.subset_fonts()
    except Exception:
        pass

    caminho_out.parent.mkdir(parents=True, exist_ok=True)
    caminho_temp = caminho_out.with_suffix(".tmp")

    reportar(0.85, "Reorganizando e gravando documento otimizado...")
    doc.save(
        caminho_temp,
        garbage=4,
        deflate=True,
    )
    doc.close()

    tamanho_final = caminho_temp.stat().st_size / 1024

    if tamanho_final >= tamanho_original and not forcar_salvamento:
        if caminho_temp.exists():
            caminho_temp.unlink()
        reportar(1.0, "O arquivo já se encontra com tamanho otimizado.")
        return {
            "sucesso": False,
            "ja_otimizado": True,
            "tamanho_original": tamanho_original,
            "tamanho_final": tamanho_final,
            "reducao_pct": 0.0,
            "caminho_saida": str(caminho_in),
            "imagens_otimizadas": otimizadas,
            "total_imagens": total_imagens,
            "mensagem": "O arquivo já estava otimizado. Nenhuma alteração foi necessária.",
        }

    if caminho_out.exists():
        caminho_out.unlink()
    caminho_temp.rename(caminho_out)

    reducao_pct = (1.0 - (tamanho_final / tamanho_original)) * 100.0
    reportar(1.0, f"Compressão concluída! Redução de {reducao_pct:.1f}%.")

    return {
        "sucesso": True,
        "ja_otimizado": False,
        "tamanho_original": tamanho_original,
        "tamanho_final": tamanho_final,
        "reducao_pct": reducao_pct,
        "caminho_saida": str(caminho_out),
        "imagens_otimizadas": otimizadas,
        "total_imagens": total_imagens,
        "mensagem": f"Redução de {reducao_pct:.1f}% ({tamanho_original:.1f} KB -> {tamanho_final:.1f} KB).",
    }
