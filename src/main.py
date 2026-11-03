"""
Ponto de entrada principal do File Compressor & PDF Merger.
Abre a Interface Gráfica moderna por padrão (para usuários finais e .exe),
mas mantém suporte a comandos de terminal para automações e uso administrativo.
"""

import argparse
from pathlib import Path
import sys

# Garante resolução de imports tanto no script quanto no executável PyInstaller
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from src.compressor import comprimir_pdf
    from src.gui import iniciar_interface
    from src.merger import unir_pdfs
except ImportError:
    from compressor import comprimir_pdf
    from gui import iniciar_interface
    from merger import unir_pdfs


def executar_cli():
    parser = argparse.ArgumentParser(
        description="Suite PDF — Compressor Universal e Mesclador de PDFs."
    )
    parser.add_argument(
        "entrada",
        nargs="*",
        help="Caminho(s) do(s) arquivo(s) PDF de entrada.",
    )
    parser.add_argument(
        "-o",
        "--saida",
        default=None,
        help="Caminho do PDF de saída.",
    )
    parser.add_argument(
        "--unir",
        action="store_true",
        help="Une os arquivos de entrada em um único PDF.",
    )
    parser.add_argument(
        "-q",
        "--qualidade",
        type=int,
        default=68,
        help="Qualidade JPEG das imagens (1-100). Padrão: 68.",
    )
    parser.add_argument(
        "-m",
        "--max-dim",
        type=int,
        default=850,
        help="Dimensão máxima em pixels para fotos/telas (Padrão: 850).",
    )
    parser.add_argument(
        "-s",
        "--senha",
        default=None,
        help="Senha para PDFs criptografados (opcional).",
    )
    parser.add_argument(
        "-f",
        "--forcar",
        action="store_true",
        help="Força salvar o arquivo mesmo se não houver redução.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Força a abertura da Interface Gráfica.",
    )

    args = parser.parse_args()

    # Se chamado com --gui ou sem arquivos de entrada no terminal, abre a interface gráfica
    if args.gui or not args.entrada:
        iniciar_interface()
        return

    # Modo CLI: União
    if args.unir or len(args.entrada) > 1:
        if not args.saida:
            args.saida = "documento_unificado.pdf"
        print(f"Unindo {len(args.entrada)} arquivos em '{args.saida}'...")
        res = unir_pdfs(
            arquivos=args.entrada,
            caminho_saida=args.saida,
            comprimir_apos_unir=True,
            qualidade=args.qualidade,
            dimensao_maxima=args.max_dim,
        )
        print(res.get("mensagem", "Operação concluída."))
        return

    # Modo CLI: Compressão individual
    caminho_in = Path(args.entrada[0])
    if args.saida:
        caminho_out = Path(args.saida)
    else:
        caminho_out = caminho_in.with_name(f"{caminho_in.stem}_otimizado.pdf")

    print(f"Comprimindo '{caminho_in}' para '{caminho_out}'...")
    res = comprimir_pdf(
        caminho_entrada=caminho_in,
        caminho_saida=caminho_out,
        qualidade=args.qualidade,
        dimensao_maxima=args.max_dim,
        senha=args.senha,
        forcar_salvamento=args.forcar,
    )
    print(res.get("mensagem", "Operação concluída."))


def main():
    # Se iniciado diretamente sem argumentos (ou em clique duplo do .exe), abre a GUI
    if len(sys.argv) == 1:
        iniciar_interface()
    else:
        executar_cli()


if __name__ == "__main__":
    main()
