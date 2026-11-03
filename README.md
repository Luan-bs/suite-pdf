# Suite PDF

Um utilitário desktop completo, moderno e de alta performance desenvolvido em Python para **compressão universal** e **união/mesclagem** de arquivos PDF. 

Acompanha **Interface Gráfica (GUI)** elegante com Dark Mode / Light Mode adaptativo e um executável standalone **`SuitePDF.exe`** pronto para uso no Windows (sem necessidade de instalar Python).

---

## 🎯 Objetivo do Projeto

Muitos PDFs corporativos, apostilas, apresentações e contratos escaneados chegam a pesar dezenas de megabytes devido a:
- Capturas de tela e fotos salvas em resolução excessiva;
- Máscaras de canal alfa (`SMask`) redundantes e objetos duplicados;
- Falta de ferramentas simples e seguras para juntar vários documentos em um arquivo leve e organizado.

O **Suite PDF** resolve esses problemas com:
1. **Compressão Real:** Redução de **40% a 85%** no peso em KB/MB, preservando a legibilidade de textos, vetores e tabelas.
2. **União / Mesclagem de PDFs:** Concatenação de múltiplos documentos na ordem exata escolhida (com reordenação via drag-and-drop), com opção de comprimir o PDF unificado.
3. **Renomeação e Destino Flexíveis:** Edição do nome final, escolha de pasta de destino ou opção de **fixar pasta padrão**.
4. **Sem Artefatos Visuais:** Composição de transparência sobre fundo branco, eliminando o erro comum de retângulos pretos em fluxogramas e logos.
5. **Executável Windows Standalone:** Arquivo `.exe` único sem telas pretas de terminal.

---

## 🖥️ Como Usar o Executável (.exe)

O executável já compilado e pronto para distribuição encontra-se em:
```text
dist/SuitePDF.exe
```

1. Dê um duplo clique em `SuitePDF.exe`.
2. A interface gráfica abrirá instantaneamente em modo janela nativa.
3. Escolha a seção desejada:
   - **Aba "Unir / Comprimir PDF(s)":** Adicione os PDFs que deseja juntar, arraste os itens para reordenar ou use as setas, marque opcionalmente *"Comprimir e otimizar após unir"* e clique em **Unir e Comprimir PDF(s)**.
   - **Aba "Comprimir PDF(s)":** Adicione um ou mais PDFs, escolha o perfil de qualidade, edite o nome do arquivo se desejar e clique em **Comprimir PDF(s)**.
4. Ao concluir, use os botões **📄 Abrir PDF** ou **📂 Abrir Pasta** para visualizar o resultado no Windows Explorer.

---

## 🚀 Execução em Ambiente de Desenvolvimento

### 1. Instalação com UV (ou Pip)

O projeto é estruturado diretamente na pasta `src/`:
```bash
cd c:\vscode\suite-pdf

# Sincroniza ambiente e dependências com uv
uv sync
```

### 2. Iniciar a Interface Gráfica

```bash
uv run python src/main.py
# ou:
uv run suitepdf
```

### 3. Uso via Linha de Comando (CLI para Automações)

Se desejar executar rotinas automatizadas no terminal:
```bash
# Comprimir um arquivo individual:
uv run python src/main.py "documento.pdf" -o "documento_leve.pdf" -q 68

# Unir múltiplos arquivos em um só:
uv run python src/main.py "parte1.pdf" "parte2.pdf" "parte3.pdf" --unir -o "completo.pdf"
```

### 4. Compilar um Novo Executável (.exe)

Para gerar uma nova versão standalone do executável através do PyInstaller:
```bash
uv run pyinstaller suitepdf.spec --noconfirm
```
O `.exe` standalone será gerado em `dist/SuitePDF.exe`.

---

## 📂 Arquitetura do Projeto

O código-fonte foi refatorado e organizado diretamente em `src/`:

```text
suite-pdf/
├── assets/
│   ├── app_icon.ico              # Ícone oficial multi-resolução do Windows
│   └── app_icon.png              # Logo oficial em alta resolução
├── dist/
│   └── SuitePDF.exe              # Executável standalone distribuível
├── src/
│   ├── __init__.py
│   ├── compressor.py             # Motor universal de compressão de PDFs
│   ├── merger.py                 # Mecanismo de junção e concatenação ordenada
│   ├── gui.py                    # Interface Gráfica moderna (CustomTkinter)
│   └── main.py                   # Ponto de entrada (GUI padrão ou CLI com flags)
├── docs/
│   └── README.md                 # Documentação técnica e engenharia em baixo nível
├── suitepdf.spec                 # Especificação de empacotamento do PyInstaller
└── pyproject.toml                # Metadados e dependências do projeto
```

---

## 🛠️ Tecnologias Utilizadas

- **[CustomTkinter](https://customtkinter.tomschimansky.com/):** Interface gráfica moderna com suporte a temas Dark/Light e componentes fluidos.
- **[PyMuPDF](https://pymupdf.readthedocs.io/):** Motor em C de alto desempenho para manipulação de XObjects, streams e páginas PDF.
- **[Pillow (PIL)](https://pillow.readthedocs.io/):** Processamento e reamostragem de imagens com filtro Lanczos e quantização JPEG adaptativa.
- **[PyInstaller](https://pyinstaller.org/):** Empacotamento do runtime Python em um arquivo executável Windows de arquivo único (`--onefile --windowed`).
- **[UV](https://github.com/astral-sh/uv):** Gerenciador de pacotes e ambientes Python ultrarrápido.

---

## 📖 Documentação Técnica

Para detalhes sobre a especificação **ISO 32000 (PDF)**, o tratamento do canal alfa (`SMask`), a eliminação de duplicações na tabela XREF e os testes de compressão, consulte a **[Documentação Técnica em docs/README.md](docs/README.md)**.
