"""
Módulo de União e Concatenação de PDFs.
Permite juntar múltiplos documentos PDF preservando a ordem definida pelo usuário,
com suporte opcional a compressão pós-junção.
"""

from collections.abc import Callable
import os
from pathlib import Path
from typing import Any
import pymupdf as fitz
from src.compressor import comprimir_pdf


def obter_qtd_paginas(caminho: str | Path) -> int:
    """Retorna o número de páginas de um arquivo PDF de forma segura."""
    try:
        with fitz.open(caminho) as doc:
            return len(doc)
    except Exception:
        return 0


def unir_pdfs(
    arquivos: list[str | Path],
    caminho_saida: str | Path,
    comprimir_apos_unir: bool = False,
    qualidade: int = 68,
    dimensao_maxima: int = 850,
    callback_progresso: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """
    Concatena múltiplos arquivos PDF em um único documento na ordem fornecida.

    :param arquivos: Lista com os caminhos dos arquivos PDF a unir.
    :param caminho_saida: Caminho final do arquivo PDF unificado.
    :param comprimir_apos_unir: Se True, aplica a compressão no PDF gerado.
    :param qualidade: Qualidade caso comprimir_apos_unir seja True.
    :param dimensao_maxima: Dimensão máxima de imagem para compressão.
    :param callback_progresso: Função callback(progresso_0_a_1, mensagem).
    :return: Dicionário com informações do processo.
    """
    if not arquivos:
        raise ValueError("Nenhum arquivo fornecido para união.")

    lista_paths = [Path(p).resolve() for p in arquivos]
    for p in lista_paths:
        if not p.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {p}")

    def reportar(pct: float, msg: str):
        if callback_progresso:
            callback_progresso(pct, msg)

    caminho_out = Path(caminho_saida).resolve()
    caminho_out.parent.mkdir(parents=True, exist_ok=True)

    doc_unificado = fitz.open()
    total_arquivos = len(lista_paths)
    total_paginas = 0

    reportar(0.05, f"Iniciando junção de {total_arquivos} arquivos...")

    for idx, p in enumerate(lista_paths, start=1):
        pct = 0.05 + (0.55 * (idx / total_arquivos))
        reportar(pct, f"Mesclando arquivo {idx}/{total_arquivos}: {p.name}...")

        doc_origem = fitz.open(p)
        if doc_origem.is_encrypted:
            if not doc_origem.authenticate(""):
                doc_origem.close()
                doc_unificado.close()
                raise PermissionError(f"O arquivo {p.name} está protegido por senha.")

        total_paginas += len(doc_origem)
        doc_unificado.insert_pdf(doc_origem)
        doc_origem.close()

    reportar(0.65, "Salvando PDF unificado temporário...")
    temp_unificado = caminho_out.with_suffix(".temp_merged.pdf")
    doc_unificado.save(
        temp_unificado,
        garbage=3,
        deflate=True,
    )
    doc_unificado.close()

    tamanho_unido = temp_unificado.stat().st_size / 1024

    if comprimir_apos_unir:
        reportar(0.70, "Otimizando e comprimindo PDF unificado...")

        def sub_callback(sub_pct: float, sub_msg: str):
            pct_global = 0.70 + (0.30 * sub_pct)
            reportar(pct_global, f"[Otimização] {sub_msg}")

        res = comprimir_pdf(
            caminho_entrada=temp_unificado,
            caminho_saida=caminho_out,
            qualidade=qualidade,
            dimensao_maxima=dimensao_maxima,
            forcar_salvamento=True,
            callback_progresso=sub_callback,
        )

        if temp_unificado.exists():
            temp_unificado.unlink()

        tamanho_final = caminho_out.stat().st_size / 1024
        reducao = (1.0 - (tamanho_final / tamanho_unido)) * 100.0 if tamanho_unido > 0 else 0.0

        return {
            "sucesso": True,
            "total_arquivos": total_arquivos,
            "total_paginas": total_paginas,
            "tamanho_bruto": tamanho_unido,
            "tamanho_final": tamanho_final,
            "comprimido": True,
            "reducao_pct": reducao,
            "caminho_saida": str(caminho_out),
            "mensagem": f"Unidos {total_arquivos} PDFs ({total_paginas} páginas). Tamanho otimizado: {tamanho_final:.1f} KB ({reducao:.1f}% de redução).",
        }

    # Se não pediu compressão adicional, apenas move o temporário para o destino final
    if caminho_out.exists():
        caminho_out.unlink()
    temp_unificado.rename(caminho_out)
    reportar(1.0, f"Junção finalizada! Total: {total_paginas} páginas.")

    return {
        "sucesso": True,
        "total_arquivos": total_arquivos,
        "total_paginas": total_paginas,
        "tamanho_bruto": tamanho_unido,
        "tamanho_final": tamanho_unido,
        "comprimido": False,
        "reducao_pct": 0.0,
        "caminho_saida": str(caminho_out),
        "mensagem": f"Unidos {total_arquivos} PDFs com sucesso! ({total_paginas} páginas, {tamanho_unido:.1f} KB).",
    }

