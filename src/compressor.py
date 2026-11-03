"""
Módulo de Compressão Universal de PDFs.
Aplica desduplicação de fluxos, composição de máscaras (SMask),
redimensionamento inteligente via Lanczos e descarte de glifos órfãos de fontes.
"""

from collections.abc import Callable
import io
import os
from pathlib import Path
from typing import Any
from PIL import Image
import pymupdf as fitz


def _processar_imagem(
    doc: fitz.Document,
    xref: int,
    smask_xref: int | None,
    qualidade: int,
    dimensao_maxima: int,
) -> tuple[bytes | None, str, str, int, int]:
    """
    Otimiza uma imagem extraída do PDF.
    Retorna: (jpeg_bytes, filter_name, colorspace_name, width, height)
    """
    pix_base = fitz.Pixmap(doc, xref)

    # 1. Carrega o Pixmap base no Pillow
    if pix_base.alpha:
        im_base = Image.frombytes("RGBA", (pix_base.width, pix_base.height), pix_base.samples)
    elif pix_base.n == 1:
        im_base = Image.frombytes("L", (pix_base.width, pix_base.height), pix_base.samples)
    else:
        im_base = Image.frombytes("RGB", (pix_base.width, pix_base.height), pix_base.samples)

    # 2. Reconstrução e composição de transparência / SMask sobre fundo branco
    if smask_xref and smask_xref > 0:
        try:
            mask_pix = fitz.Pixmap(doc, smask_xref)
            im_mask = Image.frombytes("L", (mask_pix.width, mask_pix.height), mask_pix.samples)
            if im_mask.size != im_base.size:
                im_mask = im_mask.resize(im_base.size, Image.Resampling.LANCZOS)

            bg = Image.new("RGB", im_base.size, (255, 255, 255))
            bg.paste(im_base.convert("RGB"), (0, 0), mask=im_mask)
            pil_img = bg
        except Exception:
            pil_img = im_base.convert("RGB")
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

    # 4. Codificação em JPEG com árvore Huffman otimizada
    buffer = io.BytesIO()
    pil_img.save(buffer, format="JPEG", quality=qualidade, optimize=True)
    jpeg_bytes = buffer.getvalue()

    colorspace = "/DeviceGray" if pil_img.mode == "L" else "/DeviceRGB"
    return jpeg_bytes, "/DCTDecode", colorspace, w, h


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

    reportar(0.15, "Mapeando recursos de imagem únicos...")
    img_smasks: dict[int, int | None] = {}
    for page in doc:
        for img in page.get_images():
            xref = img[0]
            smask = img[1]
            if xref not in img_smasks:
                img_smasks[xref] = smask if smask > 0 else None

    total_imagens = len(img_smasks)
    otimizadas = 0

    if total_imagens > 0:
        for idx, (xref, smask_xref) in enumerate(sorted(img_smasks.items()), start=1):
            pct = 0.20 + (0.50 * (idx / total_imagens))
            reportar(pct, f"Otimizando imagem {idx}/{total_imagens}...")
            try:
                stream_original = doc.xref_stream_raw(xref) or b""
                novos_bytes, filtro, colorspace, w, h = _processar_imagem(
                    doc=doc,
                    xref=xref,
                    smask_xref=smask_xref,
                    qualidade=qualidade,
                    dimensao_maxima=dimensao_maxima,
                )

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

