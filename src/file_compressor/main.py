import argparse
import io
import os
from pathlib import Path
import sys
import pymupdf as fitz
from PIL import Image


def _processar_imagem(
    doc: fitz.Document,
    xref: int,
    smask_xref: int | None,
    qualidade: int,
    dimensao_maxima: int,
) -> tuple[bytes | None, str, str, int, int]:
    """
    Otimiza a imagem extraída do PDF:
    - Se tem canal alfa ou SMask de recorte: compõe perfeitamente sobre fundo branco
    - Redimensiona inteligentemente respeitando dimensao_maxima
    - Codifica em JPEG otimizado (RGB ou Grayscale)
    Retorna: (jpeg_bytes, filter_name, colorspace_name, width, height)
    """
    pix_base = fitz.Pixmap(doc, xref)

    # 1. Carrega o Pixmap base no PIL
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

    # 3. Redimensionamento inteligente
    w, h = pil_img.size
    if max(w, h) > dimensao_maxima:
        escala = dimensao_maxima / max(w, h)
        w, h = max(1, int(w * escala)), max(1, int(h * escala))
        pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)

    # 4. Codificação em JPEG otimizado
    buffer = io.BytesIO()
    pil_img.save(buffer, format="JPEG", quality=qualidade, optimize=True)
    jpeg_bytes = buffer.getvalue()

    colorspace = "/DeviceGray" if pil_img.mode == "L" else "/DeviceRGB"
    return jpeg_bytes, "/DCTDecode", colorspace, w, h


def comprimir_pdf(
    caminho_entrada: str,
    caminho_saida: str,
    qualidade: int = 68,
    dimensao_maxima: int = 850,
    senha: str | None = None,
    forcar_salvamento: bool = False,
) -> bool:
    """
    Compressor Universal de PDF no estilo iLovePDF.
    
    Analisa recursos de imagem únicos, compõe máscaras com fidelidade cromática,
    re-codifica em JPEG otimizado, elimina objetos órfãos (garbage collection)
    e compacta streams de texto e vetores.
    """
    if not os.path.exists(caminho_entrada):
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {caminho_entrada}")

    tamanho_original = os.path.getsize(caminho_entrada) / 1024

    doc = fitz.open(caminho_entrada)

    # Suporte a senhas / criptografia
    if doc.is_encrypted:
        if senha is not None:
            if not doc.authenticate(senha):
                doc.close()
                raise PermissionError("A senha informada para o PDF é inválida.")
        else:
            if not doc.authenticate(""):
                doc.close()
                raise PermissionError("PDF protegido por senha. Forneça o parâmetro 'senha' (--senha).")

    print(f"\n-> Arquivo de entrada: {caminho_entrada} ({tamanho_original:.1f} KB)")
    print(f"-> Páginas no PDF:     {len(doc)}")

    # 1. Mapeia imagens únicas (xrefs) e smasks associadas
    img_smasks: dict[int, int | None] = {}
    for page in doc:
        for img in page.get_images():
            xref = img[0]
            smask = img[1]
            if xref not in img_smasks:
                img_smasks[xref] = smask if smask > 0 else None

    total_imagens = len(img_smasks)
    print(f"-> Recursos de imagem únicos: {total_imagens}")

    otimizadas = 0
    # 2. Processa cada imagem única
    for xref, smask_xref in sorted(img_smasks.items()):
        try:
            stream_original = doc.xref_stream_raw(xref) or b""
            novos_bytes, filtro, colorspace, w, h = _processar_imagem(
                doc=doc,
                xref=xref,
                smask_xref=smask_xref,
                qualidade=qualidade,
                dimensao_maxima=dimensao_maxima,
            )

            # Só substitui se houver ganho real de tamanho
            if novos_bytes and len(novos_bytes) < len(stream_original):
                obj_def = (
                    f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
                    f"/ColorSpace {colorspace} /BitsPerComponent 8 >>"
                )
                doc.update_object(xref, obj_def)
                doc.update_stream(xref, novos_bytes, new=False, compress=False)
                doc.xref_set_key(xref, "Filter", filtro)
                otimizadas += 1
        except Exception as e:
            print(f"   [Aviso] Imagem xref {xref} mantida original ({e})")

    if total_imagens > 0:
        print(f"-> Imagens otimizadas: {otimizadas}/{total_imagens}")

    # 3. Subsetting de fontes: descarta glifos não utilizados
    try:
        doc.subset_fonts()
    except Exception:
        pass

    # Garante existência do diretório pai do caminho de saída
    dir_saida = os.path.dirname(os.path.abspath(caminho_saida))
    os.makedirs(dir_saida, exist_ok=True)

    # 4. Salva aplicando garbage collection agressivo e compressão de texto
    caminho_temp = caminho_saida + ".tmp"
    doc.save(
        caminho_temp,
        garbage=4,
        deflate=True,
    )
    doc.close()

    tamanho_final = os.path.getsize(caminho_temp) / 1024

    # 5. Rede de segurança contra aumento de tamanho
    if tamanho_final >= tamanho_original and not forcar_salvamento:
        os.remove(caminho_temp)
        print("\n[Aviso] O arquivo já se encontra hiper-otimizado.")
        print(f"Original: {tamanho_original:.1f} KB | Gerado: {tamanho_final:.1f} KB")
        print("Nenhuma alteração foi gravada para evitar aumento do arquivo.")
        return False

    if os.path.exists(caminho_saida):
        os.remove(caminho_saida)
    os.rename(caminho_temp, caminho_saida)

    reducao = (1 - (tamanho_final / tamanho_original)) * 100
    print("\n" + "=" * 48)
    print(f"Sucesso na Compressão!")
    print(f"Original:   {tamanho_original:.1f} KB")
    print(f"Otimizado:  {tamanho_final:.1f} KB")
    print(f"Redução:    {reducao:.1f}%")
    print("=" * 48)
    return True


def buscar_arquivos_pdf(termo: str = "", diretorio_base: str = ".") -> list[Path]:
    """
    Busca arquivos PDF correspondentes no diretório atual e subpastas,
    ignorando diretórios de ambiente virtual e controle de versão.
    """
    base = Path(diretorio_base).resolve()
    termo = termo.strip().lower()

    # Se o usuário digitou um caminho exato que existe
    caminho_direto = Path(termo)
    if caminho_direto.is_file() and caminho_direto.suffix.lower() == ".pdf":
        return [caminho_direto.resolve()]

    ignorar_pastas = {".venv", "venv", ".git", "__pycache__", "build", "dist", ".idea", ".vscode"}
    candidatos = []

    for item in base.glob("**/*.pdf"):
        if any(ign in item.parts for ign in ignorar_pastas):
            continue
        if not termo or termo in item.name.lower():
            candidatos.append(item.resolve())

    # Ordena: arquivos na raiz primeiro, depois por nome
    candidatos.sort(key=lambda p: (len(p.parts), p.name.lower()))
    return candidatos


def formatar_tamanho(bytes_qty: int) -> str:
    """Retorna tamanho formatado legível (KB ou MB)."""
    kb = bytes_qty / 1024
    if kb >= 1024:
        return f"{kb / 1024:.2f} MB ({kb:.1f} KB)"
    return f"{kb:.1f} KB"


def modo_interativo() -> tuple[str, str, int, int]:
    """
    Interface interativa no terminal:
    1. Usuário digita o nome ou parte do nome.
    2. Sistema busca, exibe os resultados com caminho e tamanho.
    3. Usuário confirma o arquivo desejado.
    4. Define o destino e o nível de compressão.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")

    print("\n" + "=" * 58)
    print("        COMPRESSOR UNIVERSAL DE PDF -- MODO ASSISTIDO")
    print("=" * 58)

    while True:
        termo = input("\n[?] Digite o nome ou parte do arquivo PDF (ou Enter para listar todos): ").strip()
        print("Buscando arquivos...")
        encontrados = buscar_arquivos_pdf(termo)

        if not encontrados:
            print(f"[!] Nenhum arquivo PDF encontrado para a busca: '{termo}'")
            opcao = input("Deseja tentar outra busca? [S/n]: ").strip().lower()
            if opcao in ("n", "nao", "não", "exit", "sair"):
                print("Operação cancelada.")
                sys.exit(0)
            continue

        arquivo_selecionado = None

        if len(encontrados) == 1:
            item = encontrados[0]
            tam_str = formatar_tamanho(item.stat().st_size)
            print(f"\n[+] Arquivo localizado:")
            print(f"   Nome:    {item.name}")
            print(f"   Caminho: {item}")
            print(f"   Tamanho: {tam_str}")
            conf = input("\nConfirma a compressão deste arquivo? [S/n]: ").strip().lower()
            if conf in ("", "s", "sim", "y", "yes"):
                arquivo_selecionado = item
            else:
                continue
        else:
            print(f"\n[+] Foram encontrados {len(encontrados)} arquivos correspondentes:")
            for idx, item in enumerate(encontrados, start=1):
                tam_str = formatar_tamanho(item.stat().st_size)
                print(f"   [{idx}] {item.name} -- ({tam_str})")
                print(f"       Local: {item}")

            while True:
                escolha = input(f"\nEscolha o número do arquivo (1-{len(encontrados)}) ou 'c' para cancelar: ").strip()
                if escolha.lower() in ("c", "cancelar", "sair"):
                    print("Operação cancelada.")
                    sys.exit(0)
                if escolha.isdigit() and 1 <= int(escolha) <= len(encontrados):
                    arquivo_selecionado = encontrados[int(escolha) - 1]
                    break
                print("Opção inválida. Digite um número da lista.")

        if arquivo_selecionado:
            break

    caminho_entrada = str(arquivo_selecionado)

    # Sugestão inteligente de nome de saída
    sugestao_saida = str(arquivo_selecionado.with_name(f"{arquivo_selecionado.stem}_otimizado.pdf"))
    print(f"\n[*] Onde deseja salvar o PDF comprimido?")
    print(f"   Sugestão: {sugestao_saida}")
    resp_saida = input("Pressione Enter para aceitar a sugestão ou digite o novo caminho: ").strip()
    caminho_saida = resp_saida if resp_saida else sugestao_saida

    # Escolha de perfil de compressão
    print("\n[*] Escolha o perfil de compressão:")
    print("   [1] Recomendado (Estilo iLovePDF -- ótimo equilíbrio entre KB e nitidez) [Padrão]")
    print("   [2] Extremo     (Máxima redução em KB, ideal para e-mail/WhatsApp)")
    print("   [3] Alta Fidelidade (Compressão leve, máxima nitidez para impressão)")
    perfil = input("Escolha [1/2/3] (Padrão: 1): ").strip()

    if perfil == "2":
        qualidade = 55
        max_dim = 720
    elif perfil == "3":
        qualidade = 82
        max_dim = 1200
    else:
        qualidade = 68
        max_dim = 850

    return caminho_entrada, caminho_saida, qualidade, max_dim


def main():
    parser = argparse.ArgumentParser(
        description="Compressor Universal de PDF - Redução inteligente de tamanho mantendo alta qualidade."
    )
    parser.add_argument(
        "entrada",
        nargs="?",
        default=None,
        help="Caminho do PDF de entrada. Se omitido, abre a busca interativa.",
    )
    parser.add_argument(
        "-o",
        "--saida",
        default=None,
        help="Caminho do PDF de saída.",
    )
    parser.add_argument(
        "-q",
        "--qualidade",
        type=int,
        default=68,
        help="Qualidade JPEG das imagens (1-100). Padrão: 68",
    )
    parser.add_argument(
        "-m",
        "--max-dim",
        type=int,
        default=850,
        help="Dimensão máxima em pixels para fotos/telas (Padrão: 850)",
    )
    parser.add_argument(
        "-s",
        "--senha",
        default=None,
        help="Senha para PDFs criptografados (opcional)",
    )
    parser.add_argument(
        "-f",
        "--forcar",
        action="store_true",
        help="Força salvar o arquivo mesmo se não houver redução",
    )

    args = parser.parse_args()

    # Se nenhum arquivo foi passado por argumento, inicia o modo interativo
    if args.entrada is None:
        caminho_entrada, caminho_saida, qualidade, max_dim = modo_interativo()
        senha = None
        forcar = False
    else:
        caminho_entrada = args.entrada
        if args.saida:
            caminho_saida = args.saida
        else:
            p = Path(caminho_entrada)
            caminho_saida = str(p.with_name(f"{p.stem}_otimizado.pdf"))
        qualidade = args.qualidade
        max_dim = args.max_dim
        senha = args.senha
        forcar = args.forcar

    try:
        comprimir_pdf(
            caminho_entrada=caminho_entrada,
            caminho_saida=caminho_saida,
            qualidade=qualidade,
            dimensao_maxima=max_dim,
            senha=senha,
            forcar_salvamento=forcar,
        )
    except Exception as erro:
        print(f"\n[Erro] Falha ao processar PDF: {erro}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
