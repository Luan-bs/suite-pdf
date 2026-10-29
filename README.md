# File Compressor — Compressor Universal de PDF

Um otimizador e compressor inteligente de arquivos PDF desenvolvido em Python, inspirado no mecanismo de alta performance do **iLovePDF**. Reduz drasticamente o tamanho em kilobytes mantendo a nitidez, textos cristalinos e fidelidade cromática de imagens e diagramas.

---

## 🎯 Objetivo do Projeto

Muitos PDFs corporativos, apostilas, apresentações e contratos escaneados chegam a pesar dezenas de megabytes devido a:
- Capturas de tela e fotos salvas em resolução desnecessária para visualização/impressão;
- Máscaras de canal alfa (`SMask`) redundantes e objetos duplicados;
- Fontes embutidas completas e metadados estruturais não compactados.

Compressores simples ou scripts básicos que apenas utilizam filtros genéricos frequentemente falham — **podendo até aumentar o tamanho do PDF** ou corromper gráficos com blocos pretos.

O objetivo do **File Compressor** é fornecer uma solução profissional, universal e autônoma, capaz de:
1. Reduzir em **40% a 80%** o peso em KB de documentos PDF.
2. Manter 100% da nitidez de textos e elementos vetoriais.
3. Evitar artefatos visuais (como blocos pretos em fluxogramas com transparência).
4. Oferecer uma interface de linha de comando (CLI) simples e uma biblioteca Python reutilizável.

---

## 🚀 Como Usar

### 1. Pré-requisitos e Instalação

O projeto utiliza o gerenciador de pacotes ultrarrápido **uv** (ou `pip` padrão) com **Python 3.10+**.

Clone o repositório ou acesse a pasta do projeto:
```bash
cd c:\vscode\file_compressor
```

Instale as dependências com o ambiente virtual:
```bash
# Com uv:
uv sync

# Ou com pip tradicional:
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### 2. Uso via Linha de Comando (CLI)

O compressor oferece dois modos de uso: **Modo Assistido Interativo** e **Modo Direto**.

#### A) Modo Assistido Interativo (Recomendado)
Basta executar o script sem argumentos:
```bash
python src/file_compressor/main.py
```
O terminal iniciará um assistente amigável:
1. **Busca:** Você digita apenas o nome ou parte do nome do arquivo (ex: `faturamento`, `contrato`, `treinamento`).
2. **Localização e Confirmação:** O sistema busca o arquivo no diretório e subpastas, exibe o **nome**, **caminho absoluto** e o **tamanho em MB/KB**, e pede sua confirmação (`[S/n]`).
3. **Destino Sugerido:** Sugere automaticamente salvar como `nome_otimizado.pdf` na mesma pasta (basta apertar Enter para aceitar).
4. **Perfil de Compressão:** Permite escolher entre os perfis *Recomendado (estilo iLovePDF)*, *Extremo* ou *Alta Fidelidade*.

#### B) Modo Direto
Se preferir automatizar em scripts ou passar os caminhos diretamente:
```bash
python src/file_compressor/main.py "meu_documento.pdf" -o "documento_comprimido.pdf"
```

#### Parâmetros e Opções:

| Parâmetro | Padrão | Descrição |
| :--- | :--- | :--- |
| `entrada` | `arquivo_original.pdf` | Caminho do PDF a ser comprimido |
| `-o`, `--saida` | `arquivo_otimizado.pdf` | Caminho do arquivo de destino |
| `-q`, `--qualidade` | `68` | Qualidade JPEG das imagens (1 a 100) |
| `-m`, `--max-dim` | `850` | Resolução máxima em pixels para fotos/telas |
| `-s`, `--senha` | `None` | Senha para descriptografar PDFs protegidos |
| `-f`, `--forcar` | `False` | Força gravação mesmo se não houver redução |

#### Exemplos práticos:

```bash
# Compressão equilibrada recomendada (estilo iLovePDF)
python src/file_compressor/main.py relatorio.pdf -o relatorio_leve.pdf

# Compressão agressiva para e-mail / WhatsApp (máxima redução de KB)
python src/file_compressor/main.py apresentacao.pdf -o apresentacao_web.pdf -q 55 -m 720

# Compressão de alta fidelidade para impressão comercial
python src/file_compressor/main.py catalogo.pdf -o catalogo_print.pdf -q 85 -m 1200
```

### 3. Uso como Biblioteca Python

Você pode importar a função em qualquer aplicação, script ou API:

```python
from file_compressor.main import comprimir_pdf

sucesso = comprimir_pdf(
    caminho_entrada="documento_original.pdf",
    caminho_saida="documento_otimizado.pdf",
    qualidade=70,
    dimensao_maxima=900,
)

if sucesso:
    print("PDF comprimido com sucesso!")
```

---

## 🏢 Onde Usar

- **Sistemas de Gestão / ERPs:** Redução de custos de armazenamento e upload de notas fiscais, relatórios e comprovantes.
- **Portais Web e Aplicativos:** Otimização automática de uploads de usuários antes de persistir em buckets S3 ou bancos de dados.
- **Envio por E-mail e Mensageiros:** Adequação de apresentações e manuais ao limite de anexos (ex: 25 MB do Gmail ou 16 MB do WhatsApp).
- **Automação de Backoffice:** Processamento em lote de documentos digitalizados e contratos.

---

## 🛠️ Ferramentas e Tecnologias

- **[PyMuPDF (MuPDF C-Engine)](https://pymupdf.readthedocs.io/):** Motor de parsing e reconstrução de PDF em baixo nível. Permite leitura de tabelas XREF, manipulação de streams crus de objetos e gerenciamento de lixo estrutural (`garbage collection`).
- **[Pillow (PIL Fork)](https://pillow.readthedocs.io/):** Mecanismo de processamento de imagens utilizado para reamostragem com filtro Lanczos, interpolação bicúbica e codificação JPEG com quantização e árvores Huffman otimizadas.
- **[Python 3.14 / UV](https://github.com/astral-sh/uv):** Plataforma moderna de desenvolvimento e empacotamento com tipagem estática e alta performance.

---

## 📖 Documentação Técnica Detalhada

Para entender o funcionamento em baixo nível do formato PDF, o tratamento de máscaras de corte (`SMask`), a eliminação de duplicações e o pipeline de reamostragem, consulte a **[Documentação Técnica em docs/README.md](docs/README.md)**.

