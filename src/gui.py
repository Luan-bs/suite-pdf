import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from src.compressor import comprimir_pdf
from src.merger import obter_qtd_paginas, unir_pdfs

# Configuração global inicial do CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = Path.home() / ".suitepdf_gui_config.json"


def obter_caminho_recurso(nome_relativo: str) -> Path:
    """Retorna o caminho de um recurso tanto em execução local quanto empacotado no PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / nome_relativo
    return Path(__file__).resolve().parent.parent / nome_relativo

# ==============================================================================
# DESIGN SYSTEM: Paleta Slate + Emerald
# Tuplas (Cor Modo Claro, Cor Modo Escuro) para adaptação automática
# ==============================================================================
THEME = {
    # Superfícies principais (Modo Claro "Off-White / Soft Slate" sem branco puro #ffffff)
    "app_bg": ("#e2e8f0", "#0f172a"),          # Slate 200 / Slate 900
    "card_bg": ("#f1f5f9", "#1e293b"),         # Slate 100 / Slate 800
    "card_border": ("#cbd5e1", "#334155"),     # Slate 300 / Slate 700
    "subcard_bg": ("#e8eef5", "#0f172a"),      # Soft Slate / Slate 900
    "header_table_bg": ("#dde5ef", "#1e293b"), # Slate 200-150 / Slate 800
    # Linhas da lista (Estilo AG-Grid Alpine)
    "row_bg": ("#f4f7fa", "#1e293b"),          # Off-White Suave / Slate 800
    "row_border": ("#cbd5e1", "#334155"),      # Slate 300 / Slate 700
    "row_sel_bg": ("#d1fae5", "#064e3b"),      # Emerald 100 / Emerald 950
    "row_sel_border": ("#10b981", "#10b981"),  # Emerald 500
    "row_drop_bg": ("#a7f3d0", "#065f46"),     # Emerald 200 / Emerald 800
    "row_drop_border": ("#059669", "#34d399"), # Emerald 600 / Emerald 400
    # Tipografia
    "text_primary": ("#1e293b", "#f8fafc"),    # Slate 800 / Slate 50
    "text_secondary": ("#475569", "#cbd5e1"),  # Slate 600 / Slate 300
    "text_muted": ("#64748b", "#94a3b8"),      # Slate 500 / Slate 400
    "text_emerald": ("#047857", "#34d399"),    # Emerald 700 / Emerald 400
    # Acento Primário (Emerald)
    "primary": ("#10b981", "#10b981"),         # Emerald 500
    "primary_hover": ("#059669", "#059669"),   # Emerald 600
    "primary_text": ("#f8fafc", "#f8fafc"),    # Off-White (Slate 50)
    # Botões Secundários (Slate)
    "secondary_bg": ("#dfe6ee", "#334155"),    # Soft Slate 200 / Slate 700
    "secondary_hover": ("#cbd5e1", "#475569"), # Slate 300 / Slate 600
    "secondary_border": ("#b8c4d4", "#475569"),# Slate 350 / Slate 600
    "secondary_text": ("#334155", "#f1f5f9"),  # Slate 700 / Slate 100
    # Botões de Remoção / Perigo (Red)
    "danger_bg": ("#fee2e2", "#451a1a"),       # Red 100 / Red 950
    "danger_hover": ("#fecaca", "#7f1d1d"),    # Red 200 / Red 900
    "danger_border": ("#fca5a5", "#991b1b"),   # Red 300 / Red 800
    "danger_text": ("#dc2626", "#fca5a5"),     # Red 600 / Red 300
    # Inputs
    "input_bg": ("#f4f7fa", "#0f172a"),        # Off-White Suave / Slate 900
    "input_border": ("#b8c4d4", "#475569"),    # Slate 350 / Slate 600
}

FONT_FAMILY = "Segoe UI"


def carregar_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def salvar_config(dados: dict) -> None:
    try:
        CONFIG_FILE.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def formatar_tamanho(tamanho_bytes: int) -> str:
    kb = tamanho_bytes / 1024
    if kb >= 1024:
        return f"{kb / 1024:.2f} MB ({kb:.0f} KB)"
    return f"{kb:.1f} KB"


def abrir_no_explorer(caminho: Path) -> None:
    """Abre o Windows Explorer selecionando o arquivo ou abrindo a pasta."""
    caminho = Path(caminho).resolve()
    if sys.platform == "win32":
        if caminho.is_file():
            subprocess.Popen(["explorer", "/select,", str(caminho)])
        elif caminho.is_dir():
            os.startfile(str(caminho))
    else:
         subprocess.Popen(["xdg-open", str(caminho.parent if caminho.is_file() else caminho)])


def abrir_arquivo_padrao(caminho: Path) -> None:
    """Abre o arquivo PDF diretamente no leitor padrão do sistema operacional."""
    caminho = Path(caminho).resolve()
    if not caminho.exists():
        messagebox.showwarning("Arquivo não encontrado", f"O arquivo não foi encontrado:\n{caminho}")
        return
    if sys.platform == "win32":
        os.startfile(str(caminho))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(caminho)])
    else:
        subprocess.Popen(["xdg-open", str(caminho)])


def extrair_parametros_perfil(perfil_texto: str) -> tuple[int, int]:
    """Converte o texto do seletor de nível de compressão em (qualidade, dimensao_maxima)."""
    if "Extremo" in perfil_texto:
        return 55, 720
    if "Alta Fidelidade" in perfil_texto:
        return 82, 1200
    return 68, 850


class AppPDFMaster(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Suite PDF — Unir e Comprimir PDF(s)")
        self.geometry("1020x720")
        self.minsize(900, 640)
        self.configure(fg_color=THEME["app_bg"])

        # Ícone da Janela no Windows
        caminho_ico = obter_caminho_recurso("assets/app_icon.ico")
        if caminho_ico.exists():
            try:
                self.iconbitmap(str(caminho_ico))
            except Exception:
                pass

        self.config_salva = carregar_config()
        self.pasta_padrao = self.config_salva.get("pasta_padrao", "")
        tema_salvo = self.config_salva.get("tema", "Escuro")

        # Estado da aba Unir/Comprimir PDF(s)
        # Cada item: {"path": Path, "paginas": int, "tamanho": int}
        self.arquivos_unir: list[dict] = []
        self.selecao_unir: set[int] = set()
        self.ultimo_arquivo_gerado_unir: Path | None = None
        self._drag_source_idx: int | None = None
        self._drag_target_idx: int | None = None
        self._drag_active: bool = False
        self._drag_start_y: int = 0
        self._drag_ghost: ctk.CTkToplevel | None = None
        self._row_widgets_unir: list[ctk.CTkFrame] = []

        # Estado da aba Comprimir PDF(s)
        self.arquivos_comprimir: list[Path] = []
        self.selecao_comprimir: set[int] = set()
        self.ultimo_arquivo_gerado_comp: Path | None = None

        self._construir_layout(tema_salvo)

    # ==========================================================================
    # LAYOUT PRINCIPAL E CABEÇALHO
    # ==========================================================================
    def _construir_layout(self, tema_inicial: str):
        # 1. Cabeçalho Superior (Card limpo estilo styles.css)
        header = ctk.CTkFrame(
            self,
            height=80,
            corner_radius=0,
            fg_color=THEME["card_bg"],
            border_width=1,
            border_color=THEME["card_border"],
        )
        header.pack(fill="x", side="top")

        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="both", expand=True, padx=20, pady=8)

        # Marca / Título com Logo Oficial do Suite PDF
        caminho_logo = obter_caminho_recurso("assets/app_icon.png")
        if caminho_logo.exists():
            try:
                pil_logo = Image.open(caminho_logo)
                self.logo_image = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(56, 56))
                lbl_logo = ctk.CTkLabel(header_inner, image=self.logo_image, text="")
                lbl_logo.pack(side="left", padx=(0, 12))
            except Exception:
                badge_icon = ctk.CTkLabel(
                    header_inner,
                    text="PDF",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                    fg_color=THEME["primary"],
                    text_color=THEME["primary_text"],
                    corner_radius=6,
                    width=42,
                    height=28,
                )
                badge_icon.pack(side="left", padx=(0, 10))
        else:
            badge_icon = ctk.CTkLabel(
                header_inner,
                text="PDF",
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                fg_color=THEME["primary"],
                text_color=THEME["primary_text"],
                corner_radius=6,
                width=42,
                height=28,
            )
            badge_icon.pack(side="left", padx=(0, 10))

        lbl_titulo = ctk.CTkLabel(
            header_inner,
            text="Suite PDF",
            font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
            text_color=THEME["text_primary"],
        )
        lbl_titulo.pack(side="left")

        lbl_sub = ctk.CTkLabel(
            header_inner,
            text="União e Compressão Inteligente de Documentos",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=THEME["text_muted"],
        )
        lbl_sub.pack(side="left", padx=14)

        # Seletor de Tema (Modo Claro / Escuro / Sistema)
        box_tema = ctk.CTkFrame(header_inner, fg_color="transparent")
        box_tema.pack(side="right")

        lbl_tema = ctk.CTkLabel(
            box_tema,
            text=" Aparência:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_secondary"],
        )
        lbl_tema.pack(side="left", padx=(0, 8))

        self.seletor_tema = ctk.CTkOptionMenu(
            box_tema,
            values=["Escuro", "Claro", "Sistema"],
            width=110,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["secondary_bg"],
            button_color=THEME["secondary_hover"],
            button_hover_color=THEME["primary"],
            text_color=THEME["text_primary"],
            dropdown_fg_color=THEME["card_bg"],
            dropdown_text_color=THEME["text_primary"],
            dropdown_hover_color=THEME["row_sel_bg"],
            command=self._alterar_tema,
        )
        if tema_inicial not in ("Escuro", "Claro", "Sistema"):
            tema_inicial = "Escuro"
        self.seletor_tema.set(tema_inicial)
        self._aplicar_modo_aparencia(tema_inicial)
        self.seletor_tema.pack(side="right")

        # 2. Navegação de Abas (Segmented Button estilizado com Emerald)
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=THEME["card_bg"],
            border_width=1,
            border_color=THEME["card_border"],
            segmented_button_fg_color=THEME["header_table_bg"],
            segmented_button_selected_color=THEME["primary"],
            segmented_button_selected_hover_color=THEME["primary_hover"],
            segmented_button_unselected_color=THEME["header_table_bg"],
            segmented_button_unselected_hover_color=THEME["secondary_hover"],
            text_color=THEME["primary_text"],
            corner_radius=10,
            command=self._atualizar_cores_abas,
        )
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(12, 18))

        # Estilizar fonte do botão segmentado das abas
        try:
            self.tabview._segmented_button.configure(
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                height=36,
            )
        except Exception:
            pass

        # Ordem de Seções: 1ª Unir/Comprimir PDF(s), 2ª Comprimir PDF(s)
        self.tab_unir = self.tabview.add("   🔗  Unir / Comprimir PDF(s)   ")
        self.tab_comprimir = self.tabview.add("   ⚡  Comprimir PDF(s)   ")

        self._construir_aba_unir()
        self._construir_aba_comprimir()
        self._atualizar_cores_abas()

    def _aplicar_modo_aparencia(self, escolha: str):
        mapa = {"Escuro": "Dark", "Claro": "Light", "Sistema": "System"}
        ctk.set_appearance_mode(mapa.get(escolha, "Dark"))

    def _alterar_tema(self, escolha: str):
        self._aplicar_modo_aparencia(escolha)
        self.config_salva["tema"] = escolha
        salvar_config(self.config_salva)
        self._atualizar_cores_abas()
        self._atualizar_lista_unir_ui()
        self._atualizar_lista_comprimir_ui()

    def _atualizar_cores_abas(self):
        """Garante contraste legível nos botões das abas tanto no modo Claro quanto no Escuro."""
        try:
            modo = ctk.get_appearance_mode()
            for valor, btn in self.tabview._segmented_button._buttons_dict.items():
                if valor == self.tabview.get():
                    btn.configure(text_color="#f8fafc")
                else:
                    btn.configure(text_color="#334155" if modo == "Light" else "#cbd5e1")
        except Exception:
            pass

    # ==========================================================================
    # ABA 1: UNIR / COMPRIMIR PDF(s)
    # ==========================================================================
    def _construir_aba_unir(self):
        self.tab_unir.grid_columnconfigure(0, weight=3)
        self.tab_unir.grid_columnconfigure(1, weight=2)
        self.tab_unir.grid_rowconfigure(1, weight=1)

        # --- BARRA DE FERRAMENTAS SUPERIOR (Limpa e sem botões repetidos) ---
        top_bar = ctk.CTkFrame(self.tab_unir, fg_color="transparent")
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 8))

        self.btn_add_unir = ctk.CTkButton(
            top_bar,
            text="➕ Adicionar PDF(s)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            text_color=THEME["primary_text"],
            height=36,
            width=165,
            corner_radius=6,
            command=self._selecionar_arquivos_unir,
        )
        self.btn_add_unir.pack(side="left", padx=(0, 8))

        # Botão Contextual Único: "Remover Selecionados (N)" OU "Limpar Lista"
        self.btn_acao_lista_unir = ctk.CTkButton(
            top_bar,
            text="🗑️ Limpar Lista",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["danger_bg"],
            hover_color=THEME["danger_hover"],
            text_color=THEME["danger_text"],
            border_width=1,
            border_color=THEME["danger_border"],
            height=36,
            width=160,
            corner_radius=6,
            state="disabled",
            command=self._acao_contextual_remover_unir,
        )
        self.btn_acao_lista_unir.pack(side="left", padx=4)

        # Botões compactos de ordenação (Subir / Descer) agrupados na barra da lista
        self.btn_subir_unir = ctk.CTkButton(
            top_bar,
            text="▲ Subir",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["secondary_bg"],
            hover_color=THEME["secondary_hover"],
            text_color=THEME["secondary_text"],
            border_width=1,
            border_color=THEME["secondary_border"],
            height=36,
            width=82,
            corner_radius=6,
            state="disabled",
            command=self._mover_selecionados_cima,
        )
        self.btn_subir_unir.pack(side="left", padx=(12, 4))

        self.btn_descer_unir = ctk.CTkButton(
            top_bar,
            text="▼ Descer",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["secondary_bg"],
            hover_color=THEME["secondary_hover"],
            text_color=THEME["secondary_text"],
            border_width=1,
            border_color=THEME["secondary_border"],
            height=36,
            width=86,
            corner_radius=6,
            state="disabled",
            command=self._mover_selecionados_baixo,
        )
        self.btn_descer_unir.pack(side="left", padx=4)

        self.lbl_unir_resumo = ctk.CTkLabel(
            top_bar,
            text="0 arquivo(s) na fila",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_muted"],
        )
        self.lbl_unir_resumo.pack(side="right", padx=6)

        # --- COLUNA ESQUERDA: TABELA ESTILO AG-GRID ALPINE ---
        table_container = ctk.CTkFrame(
            self.tab_unir,
            fg_color=THEME["subcard_bg"],
            border_width=1,
            border_color=THEME["card_border"],
            corner_radius=8,
        )
        table_container.grid(row=1, column=0, sticky="nsew", padx=(12, 8), pady=4)
        table_container.grid_rowconfigure(1, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # Cabeçalho da Tabela (Estilo .ag-header de styles.css)
        header_row = ctk.CTkFrame(
            table_container,
            height=38,
            fg_color=THEME["header_table_bg"],
            corner_radius=6,
        )
        header_row.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))

        self.var_master_unir = tk.BooleanVar(value=False)
        self.chk_master_unir = ctk.CTkCheckBox(
            header_row,
            text="",
            width=20,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            border_color=THEME["input_border"],
            variable=self.var_master_unir,
            command=self._toggle_selecionar_todos_unir,
        )
        self.chk_master_unir.pack(side="left", padx=(10, 6), pady=8)

        lbl_col_ordem = ctk.CTkLabel(
            header_row,
            text="ORDEM",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=THEME["text_secondary"],
            width=54,
            anchor="w",
        )
        lbl_col_ordem.pack(side="left", padx=(2, 4))

        lbl_col_nome = ctk.CTkLabel(
            header_row,
            text="ARQUIVO PDF  (Arraste ⠿ para ordenar)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=THEME["text_secondary"],
            anchor="w",
        )
        lbl_col_nome.pack(side="left", padx=4, fill="x", expand=True)

        lbl_col_acoes = ctk.CTkLabel(
            header_row,
            text="AÇÕES",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=THEME["text_secondary"],
            width=96,
            anchor="e",
        )
        lbl_col_acoes.pack(side="right", padx=14)

        # Corpo rolável da Tabela
        self.scroll_unir = ctk.CTkScrollableFrame(
            table_container,
            fg_color="transparent",
            corner_radius=0,
        )
        self.scroll_unir.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

        self._atualizar_lista_unir_ui()

        # --- COLUNA DIREITA: PAINEL DE CONFIGURAÇÕES DA JUNÇÃO ---
        right_panel = ctk.CTkFrame(
            self.tab_unir,
            fg_color=THEME["subcard_bg"],
            border_width=1,
            border_color=THEME["card_border"],
            corner_radius=8,
        )
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(8, 12), pady=4)

        lbl_cfg = ctk.CTkLabel(
            right_panel,
            text="CONFIGURAÇÕES DE SAÍDA",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_secondary"],
        )
        lbl_cfg.pack(anchor="w", padx=16, pady=(14, 8))

        # Nome do arquivo final
        lbl_nome = ctk.CTkLabel(
            right_panel,
            text="Nome do arquivo PDF final:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_primary"],
        )
        lbl_nome.pack(anchor="w", padx=16, pady=(2, 2))

        self.entry_nome_unir = ctk.CTkEntry(
            right_panel,
            placeholder_text="Ex: relatorio_unificado.pdf",
            height=34,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["input_bg"],
            border_color=THEME["input_border"],
            text_color=THEME["text_primary"],
        )
        self.entry_nome_unir.insert(0, "documento_unificado.pdf")
        self.entry_nome_unir.pack(fill="x", padx=16, pady=(0, 12))

        # Switch: Comprimir após unir + Nível de Compressão
        box_comp_opt = ctk.CTkFrame(
            right_panel,
            fg_color=THEME["card_bg"],
            border_width=1,
            border_color=THEME["card_border"],
            corner_radius=6,
        )
        box_comp_opt.pack(fill="x", padx=16, pady=(0, 12))

        self.var_comprimir_apos_unir = tk.BooleanVar(value=True)
        self.chk_comprimir_unir = ctk.CTkSwitch(
            box_comp_opt,
            text="Comprimir e otimizar após unir",
            variable=self.var_comprimir_apos_unir,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_primary"],
            progress_color=THEME["primary"],
            button_color=("#f8fafc", "#e2e8f0"),
            button_hover_color=("#e2e8f0", "#cbd5e1"),
            command=self._ao_alternar_switch_compressao_unir,
        )
        self.chk_comprimir_unir.pack(anchor="w", padx=12, pady=(10, 6))

        self.lbl_perfil_unir = ctk.CTkLabel(
            box_comp_opt,
            text="Nível de Compressão:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=THEME["text_secondary"],
        )
        self.lbl_perfil_unir.pack(anchor="w", padx=12, pady=(2, 2))

        self.combo_perfil_unir = ctk.CTkOptionMenu(
            box_comp_opt,
            values=[
                "Equilibrado (Recomendado - ~850px / Q68)",
                "Extremo (Menor Tamanho - ~720px / Q55)",
                "Alta Fidelidade ( textos finos - ~1200px / Q82)",
            ],
            height=30,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=THEME["secondary_bg"],
            button_color=THEME["secondary_hover"],
            button_hover_color=THEME["primary"],
            text_color=THEME["text_primary"],
            dropdown_fg_color=THEME["card_bg"],
            dropdown_text_color=THEME["text_primary"],
            dropdown_hover_color=THEME["row_sel_bg"],
        )
        self.combo_perfil_unir.pack(fill="x", padx=12, pady=(0, 10))

        # Pasta de Destino
        lbl_pasta = ctk.CTkLabel(
            right_panel,
            text="Pasta de destino:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_primary"],
        )
        lbl_pasta.pack(anchor="w", padx=16, pady=(2, 2))

        frame_pasta = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_pasta.pack(fill="x", padx=16, pady=(0, 4))

        self.entry_pasta_unir = ctk.CTkEntry(
            frame_pasta,
            placeholder_text="Mesma pasta do 1º arquivo",
            height=34,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["input_bg"],
            border_color=THEME["input_border"],
            text_color=THEME["text_primary"],
        )
        if self.pasta_padrao:
            self.entry_pasta_unir.insert(0, self.pasta_padrao)
        self.entry_pasta_unir.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_escolher_pasta_unir = ctk.CTkButton(
            frame_pasta,
            text="📁 Procurar",
            width=92,
            height=34,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["secondary_bg"],
            hover_color=THEME["secondary_hover"],
            text_color=THEME["secondary_text"],
            border_width=1,
            border_color=THEME["secondary_border"],
            command=lambda: self._escolher_pasta(self.entry_pasta_unir),
        )
        btn_escolher_pasta_unir.pack(side="right")

        self.var_fixar_pasta_unir = tk.BooleanVar(value=bool(self.pasta_padrao))
        chk_fixar = ctk.CTkCheckBox(
            right_panel,
            text="Lembrar pasta de destino como padrão",
            variable=self.var_fixar_pasta_unir,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=THEME["text_secondary"],
            checkbox_width=18,
            checkbox_height=18,
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            command=lambda: self._salvar_preferencia_pasta(self.entry_pasta_unir.get(), self.var_fixar_pasta_unir.get()),
        )
        chk_fixar.pack(anchor="w", padx=16, pady=(4, 10))

        # Botão de Ação Principal (CTA Emerald)
        self.btn_executar_unir = ctk.CTkButton(
            right_panel,
            text="🔗 Unir e Comprimir PDF(s)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            text_color=THEME["primary_text"],
            height=44,
            corner_radius=8,
            command=self._iniciar_uniao,
        )
        self.btn_executar_unir.pack(fill="x", padx=16, pady=(6, 12), side="bottom")

        # --- RODAPÉ DE STATUS E AÇÕES PÓS-PROCESSAMENTO ---
        bottom_bar = ctk.CTkFrame(
            self.tab_unir,
            fg_color=THEME["subcard_bg"],
            border_width=1,
            border_color=THEME["card_border"],
            corner_radius=8,
        )
        bottom_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(6, 8))

        status_row = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        status_row.pack(fill="x", padx=14, pady=(8, 4))

        self.lbl_status_unir = ctk.CTkLabel(
            status_row,
            text="Pronto. Adicione 2 ou mais arquivos PDF para unir.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_secondary"],
        )
        self.lbl_status_unir.pack(side="left")

        self.box_resultado_unir = ctk.CTkFrame(status_row, fg_color="transparent")
        self.btn_abrir_arquivo_unir = ctk.CTkButton(
            self.box_resultado_unir,
            text="📄 Abrir PDF",
            width=115,
            height=30,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            text_color=THEME["primary_text"],
            command=self._abrir_ultimo_arquivo_unir,
        )
        self.btn_abrir_pasta_unir = ctk.CTkButton(
            self.box_resultado_unir,
            text="📂 Abrir Pasta",
            width=118,
            height=30,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["secondary_bg"],
            hover_color=THEME["secondary_hover"],
            text_color=THEME["secondary_text"],
            border_width=1,
            border_color=THEME["secondary_border"],
            command=self._abrir_ultima_pasta_unir,
        )

        self.progresso_unir = ctk.CTkProgressBar(
            bottom_bar,
            height=8,
            corner_radius=4,
            fg_color=THEME["header_table_bg"],
            progress_color=THEME["primary"],
        )
        self.progresso_unir.pack(fill="x", padx=14, pady=(2, 10))
        self.progresso_unir.set(0)

    def _ao_alternar_switch_compressao_unir(self):
        ativo = self.var_comprimir_apos_unir.get()
        if ativo:
            self.combo_perfil_unir.configure(state="normal")
            self.btn_executar_unir.configure(text="🔗 Unir e Comprimir PDF(s)")
        else:
            self.combo_perfil_unir.configure(state="disabled")
            self.btn_executar_unir.configure(text="🔗 Unir PDF(s)")

    # ==========================================================================
    # ABA 2: COMPRIMIR PDF(s)
    # ==========================================================================
    def _construir_aba_comprimir(self):
        self.tab_comprimir.grid_columnconfigure(0, weight=3)
        self.tab_comprimir.grid_columnconfigure(1, weight=2)
        self.tab_comprimir.grid_rowconfigure(1, weight=1)

        # --- BARRA DE FERRAMENTAS SUPERIOR (Idêntica à Aba 1 para consistência) ---
        top_bar = ctk.CTkFrame(self.tab_comprimir, fg_color="transparent")
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 8))

        self.btn_add_comp = ctk.CTkButton(
            top_bar,
            text="➕ Adicionar PDF(s)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            text_color=THEME["primary_text"],
            height=36,
            width=165,
            corner_radius=6,
            command=self._selecionar_arquivos_comprimir,
        )
        self.btn_add_comp.pack(side="left", padx=(0, 8))

        self.btn_acao_lista_comp = ctk.CTkButton(
            top_bar,
            text="🗑️ Limpar Lista",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["danger_bg"],
            hover_color=THEME["danger_hover"],
            text_color=THEME["danger_text"],
            border_width=1,
            border_color=THEME["danger_border"],
            height=36,
            width=160,
            corner_radius=6,
            state="disabled",
            command=self._acao_contextual_remover_comp,
        )
        self.btn_acao_lista_comp.pack(side="left", padx=4)

        self.lbl_comp_qtd = ctk.CTkLabel(
            top_bar,
            text="0 arquivo(s) na fila",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_muted"],
        )
        self.lbl_comp_qtd.pack(side="right", padx=6)

        # --- COLUNA ESQUERDA: TABELA ESTILO AG-GRID ALPINE ---
        table_container = ctk.CTkFrame(
            self.tab_comprimir,
            fg_color=THEME["subcard_bg"],
            border_width=1,
            border_color=THEME["card_border"],
            corner_radius=8,
        )
        table_container.grid(row=1, column=0, sticky="nsew", padx=(12, 8), pady=4)
        table_container.grid_rowconfigure(1, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        header_row = ctk.CTkFrame(
            table_container,
            height=38,
            fg_color=THEME["header_table_bg"],
            corner_radius=6,
        )
        header_row.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))

        self.var_master_comp = tk.BooleanVar(value=False)
        self.chk_master_comp = ctk.CTkCheckBox(
            header_row,
            text="",
            width=20,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            border_color=THEME["input_border"],
            variable=self.var_master_comp,
            command=self._toggle_selecionar_todos_comp,
        )
        self.chk_master_comp.pack(side="left", padx=(10, 6), pady=8)

        lbl_col_idx = ctk.CTkLabel(
            header_row,
            text="#",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=THEME["text_secondary"],
            width=36,
            anchor="w",
        )
        lbl_col_idx.pack(side="left", padx=(2, 4))

        lbl_col_arq = ctk.CTkLabel(
            header_row,
            text="ARQUIVO PDF",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=THEME["text_secondary"],
            anchor="w",
        )
        lbl_col_arq.pack(side="left", padx=4, fill="x", expand=True)

        lbl_col_rem = ctk.CTkLabel(
            header_row,
            text="REMOVER",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=THEME["text_secondary"],
            width=70,
            anchor="e",
        )
        lbl_col_rem.pack(side="right", padx=14)

        self.scroll_comp = ctk.CTkScrollableFrame(
            table_container,
            fg_color="transparent",
            corner_radius=0,
        )
        self.scroll_comp.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

        self._atualizar_lista_comprimir_ui()

        # --- COLUNA DIREITA: PAINEL DE CONFIGURAÇÕES DE COMPRESSÃO ---
        right_panel = ctk.CTkFrame(
            self.tab_comprimir,
            fg_color=THEME["subcard_bg"],
            border_width=1,
            border_color=THEME["card_border"],
            corner_radius=8,
        )
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(8, 12), pady=4)

        lbl_cfg = ctk.CTkLabel(
            right_panel,
            text="CONFIGURAÇÕES DE COMPRESSÃO",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_secondary"],
        )
        lbl_cfg.pack(anchor="w", padx=16, pady=(14, 8))

        lbl_perfil = ctk.CTkLabel(
            right_panel,
            text="Nível de Compressão:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_primary"],
        )
        lbl_perfil.pack(anchor="w", padx=16, pady=(2, 2))

        self.combo_perfil = ctk.CTkOptionMenu(
            right_panel,
            values=[
                "Equilibrado (Recomendado - ~850px / Q68)",
                "Extremo (Menor Tamanho - ~720px / Q55)",
                "Alta Fidelidade (Textos finos - ~1200px / Q82)",
            ],
            height=34,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["secondary_bg"],
            button_color=THEME["secondary_hover"],
            button_hover_color=THEME["primary"],
            text_color=THEME["text_primary"],
            dropdown_fg_color=THEME["card_bg"],
            dropdown_text_color=THEME["text_primary"],
            dropdown_hover_color=THEME["row_sel_bg"],
        )
        self.combo_perfil.pack(fill="x", padx=16, pady=(0, 12))

        lbl_nome = ctk.CTkLabel(
            right_panel,
            text="Nome de saída (para 1 arquivo):",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_primary"],
        )
        lbl_nome.pack(anchor="w", padx=16, pady=(2, 2))

        self.entry_nome_comp = ctk.CTkEntry(
            right_panel,
            placeholder_text="Padrão: <nome_original>_otimizado.pdf",
            height=34,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["input_bg"],
            border_color=THEME["input_border"],
            text_color=THEME["text_primary"],
        )
        self.entry_nome_comp.pack(fill="x", padx=16, pady=(0, 12))

        lbl_pasta = ctk.CTkLabel(
            right_panel,
            text="Pasta de destino:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_primary"],
        )
        lbl_pasta.pack(anchor="w", padx=16, pady=(2, 2))

        frame_pasta = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_pasta.pack(fill="x", padx=16, pady=(0, 4))

        self.entry_pasta_comp = ctk.CTkEntry(
            frame_pasta,
            placeholder_text="Mesma pasta do arquivo original",
            height=34,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["input_bg"],
            border_color=THEME["input_border"],
            text_color=THEME["text_primary"],
        )
        if self.pasta_padrao:
            self.entry_pasta_comp.insert(0, self.pasta_padrao)
        self.entry_pasta_comp.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_escolher_pasta_comp = ctk.CTkButton(
            frame_pasta,
            text="📁 Procurar",
            width=92,
            height=34,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["secondary_bg"],
            hover_color=THEME["secondary_hover"],
            text_color=THEME["secondary_text"],
            border_width=1,
            border_color=THEME["secondary_border"],
            command=lambda: self._escolher_pasta(self.entry_pasta_comp),
        )
        btn_escolher_pasta_comp.pack(side="right")

        self.var_fixar_pasta_comp = tk.BooleanVar(value=bool(self.pasta_padrao))
        chk_fixar_comp = ctk.CTkCheckBox(
            right_panel,
            text="Lembrar pasta de destino como padrão",
            variable=self.var_fixar_pasta_comp,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=THEME["text_secondary"],
            checkbox_width=18,
            checkbox_height=18,
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            command=lambda: self._salvar_preferencia_pasta(self.entry_pasta_comp.get(), self.var_fixar_pasta_comp.get()),
        )
        chk_fixar_comp.pack(anchor="w", padx=16, pady=(4, 10))

        self.btn_executar_comp = ctk.CTkButton(
            right_panel,
            text="⚡ Comprimir PDF(s)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            text_color=THEME["primary_text"],
            height=44,
            corner_radius=8,
            command=self._iniciar_compressao,
        )
        self.btn_executar_comp.pack(fill="x", padx=16, pady=(6, 12), side="bottom")

        # --- RODAPÉ DE STATUS E AÇÕES PÓS-PROCESSAMENTO ---
        bottom_bar = ctk.CTkFrame(
            self.tab_comprimir,
            fg_color=THEME["subcard_bg"],
            border_width=1,
            border_color=THEME["card_border"],
            corner_radius=8,
        )
        bottom_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(6, 8))

        status_row = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        status_row.pack(fill="x", padx=14, pady=(8, 4))

        self.lbl_status_comp = ctk.CTkLabel(
            status_row,
            text="Pronto. Adicione um ou mais PDFs para comprimir.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_secondary"],
        )
        self.lbl_status_comp.pack(side="left")

        self.box_resultado_comp = ctk.CTkFrame(status_row, fg_color="transparent")
        self.btn_abrir_arquivo_comp = ctk.CTkButton(
            self.box_resultado_comp,
            text="📄 Abrir PDF",
            width=115,
            height=30,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            text_color=THEME["primary_text"],
            command=self._abrir_ultimo_arquivo_comp,
        )
        self.btn_abrir_pasta_comp = ctk.CTkButton(
            self.box_resultado_comp,
            text="📂 Abrir Pasta",
            width=118,
            height=30,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["secondary_bg"],
            hover_color=THEME["secondary_hover"],
            text_color=THEME["secondary_text"],
            border_width=1,
            border_color=THEME["secondary_border"],
            command=self._abrir_ultima_pasta_comp,
        )

        self.progresso_comp = ctk.CTkProgressBar(
            bottom_bar,
            height=8,
            corner_radius=4,
            fg_color=THEME["header_table_bg"],
            progress_color=THEME["primary"],
        )
        self.progresso_comp.pack(fill="x", padx=14, pady=(2, 10))
        self.progresso_comp.set(0)

    # ==========================================================================
    # MÉTODOS AUXILIARES DE PASTA
    # ==========================================================================
    def _escolher_pasta(self, entry_widget: ctk.CTkEntry):
        pasta = filedialog.askdirectory(title="Selecione a Pasta de Destino")
        if pasta:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, pasta)
            if self.var_fixar_pasta_unir.get() or self.var_fixar_pasta_comp.get():
                self._salvar_preferencia_pasta(pasta, True)

    def _salvar_preferencia_pasta(self, caminho_pasta: str, fixar: bool):
        if fixar and caminho_pasta.strip():
            self.config_salva["pasta_padrao"] = caminho_pasta.strip()
        else:
            self.config_salva.pop("pasta_padrao", None)
        salvar_config(self.config_salva)

    # ==========================================================================
    # LÓGICA E EVENTOS DA ABA 1: UNIR / COMPRIMIR PDF(s)
    # ==========================================================================
    def _selecionar_arquivos_unir(self):
        caminhos = filedialog.askopenfilenames(
            title="Adicionar PDFs para Unir/Comprimir",
            filetypes=[("Arquivos PDF", "*.pdf")],
        )
        if not caminhos:
            return

        for c in caminhos:
            p = Path(c)
            if p.exists():
                paginas = obter_qtd_paginas(p)
                tamanho = p.stat().st_size
                self.arquivos_unir.append({"path": p, "paginas": paginas, "tamanho": tamanho})

        self._atualizar_lista_unir_ui()

    def _toggle_selecionar_todos_unir(self):
        if not self.arquivos_unir:
            self.var_master_unir.set(False)
            return
        if self.var_master_unir.get():
            self.selecao_unir = set(range(len(self.arquivos_unir)))
        else:
            self.selecao_unir.clear()
        self._atualizar_lista_unir_ui()

    def _acao_contextual_remover_unir(self):
        """Remove os itens selecionados ou limpa toda a lista se nenhum estiver marcado."""
        if not self.arquivos_unir:
            return
        if self.selecao_unir:
            self.arquivos_unir = [
                item for idx, item in enumerate(self.arquivos_unir) if idx not in self.selecao_unir
            ]
            self.selecao_unir.clear()
        else:
            self.arquivos_unir.clear()
            self.selecao_unir.clear()
        self._atualizar_lista_unir_ui()

    def _atualizar_barra_contextual_unir(self):
        total = len(self.arquivos_unir)
        sel = len(self.selecao_unir)

        # Sincronizar checkbox mestre do cabeçalho
        self.var_master_unir.set(total > 0 and sel == total)

        # Botão contextual único
        if total == 0:
            self.btn_acao_lista_unir.configure(text="🗑️ Limpar Lista", state="disabled")
            self.btn_subir_unir.configure(state="disabled")
            self.btn_descer_unir.configure(state="disabled")
        elif sel > 0:
            self.btn_acao_lista_unir.configure(text=f"🗑️ Remover ({sel})", state="normal")
            self.btn_subir_unir.configure(state="normal")
            self.btn_descer_unir.configure(state="normal")
        else:
            self.btn_acao_lista_unir.configure(text="🗑️ Limpar Lista", state="normal")
            self.btn_subir_unir.configure(state="disabled")
            self.btn_descer_unir.configure(state="disabled")

    def _atualizar_lista_unir_ui(self):
        for widget in self.scroll_unir.winfo_children():
            widget.destroy()
        self._row_widgets_unir.clear()

        self._atualizar_barra_contextual_unir()

        total_arqs = len(self.arquivos_unir)
        total_pags = sum(x["paginas"] for x in self.arquivos_unir)
        total_bytes = sum(x["tamanho"] for x in self.arquivos_unir)

        if total_arqs == 0:
            self.lbl_unir_resumo.configure(text="0 arquivo(s) na fila")
            box_vazio = ctk.CTkFrame(self.scroll_unir, fg_color="transparent")
            box_vazio.pack(fill="both", expand=True, pady=48)

            lbl_icone = ctk.CTkLabel(
                box_vazio,
                text="📄",
                font=ctk.CTkFont(family=FONT_FAMILY, size=32),
            )
            lbl_icone.pack(pady=(0, 6))

            lbl_vazio = ctk.CTkLabel(
                box_vazio,
                text="Nenhum arquivo na fila de união.\nClique em '➕ Adicionar PDF(s)' acima para começar.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                text_color=THEME["text_muted"],
                justify="center",
            )
            lbl_vazio.pack()
            return

        sel_count = len(self.selecao_unir)
        sel_str = f" • {sel_count} marcado(s)" if sel_count > 0 else ""
        self.lbl_unir_resumo.configure(
            text=f"{total_arqs} PDF(s) • {total_pags} pág. • {formatar_tamanho(total_bytes)}{sel_str}"
        )

        for idx, item in enumerate(self.arquivos_unir):
            selecionado = idx in self.selecao_unir
            bg_color = THEME["row_sel_bg"] if selecionado else THEME["row_bg"]
            border_color = THEME["row_sel_border"] if selecionado else THEME["row_border"]

            row = ctk.CTkFrame(
                self.scroll_unir,
                fg_color=bg_color,
                border_width=1,
                border_color=border_color,
                corner_radius=6,
                height=42,
            )
            row.pack(fill="x", padx=4, pady=3)
            row.pack_propagate(False)
            self._row_widgets_unir.append(row)

            # Checkbox de seleção individual
            var_chk = tk.BooleanVar(value=selecionado)
            chk = ctk.CTkCheckBox(
                row,
                text="",
                width=20,
                checkbox_width=18,
                checkbox_height=18,
                corner_radius=4,
                fg_color=THEME["primary"],
                hover_color=THEME["primary_hover"],
                border_color=THEME["input_border"],
                variable=var_chk,
                command=lambda i=idx, v=var_chk: self._toggle_item_selecao_unir(i, v.get()),
            )
            chk.pack(side="left", padx=(8, 4))

            # Handle de arraste + Badge de Ordem
            lbl_drag = ctk.CTkLabel(
                row,
                text=f"⠿  #{idx + 1:02d}",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                text_color=THEME["text_emerald"] if selecionado else THEME["text_secondary"],
                width=54,
                anchor="w",
                cursor="fleur",
            )
            lbl_drag.pack(side="left", padx=(2, 6))

            # Nome do arquivo + Metadados (Páginas e Tamanho)
            nome_arq = item["path"].name
            if len(nome_arq) > 40:
                nome_arq = nome_arq[:37] + "..."

            info_texto = f"{nome_arq}   ({item['paginas']} pág. • {formatar_tamanho(item['tamanho'])})"
            lbl_nome = ctk.CTkLabel(
                row,
                text=info_texto,
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold" if selecionado else "normal"),
                text_color=THEME["text_primary"],
                anchor="w",
                cursor="fleur",
            )
            lbl_nome.pack(side="left", padx=4, fill="x", expand=True)

            # Bindings de Drag-and-Drop na linha, handle e rótulo
            for w in (row, lbl_drag, lbl_nome):
                w.bind("<ButtonPress-1>", lambda e, i=idx: self._iniciar_drag_unir(e, i))
                w.bind("<B1-Motion>", self._mover_drag_unir)
                w.bind("<ButtonRelease-1>", self._finalizar_drag_unir)

            # Botões de ação rápida na linha (Remover, Descer, Subir)
            btn_rem = ctk.CTkButton(
                row,
                text="✖",
                width=28,
                height=26,
                corner_radius=5,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                fg_color=THEME["danger_bg"],
                hover_color=THEME["danger_hover"],
                text_color=THEME["danger_text"],
                command=lambda i=idx: self._remover_item_unir(i),
            )
            btn_rem.pack(side="right", padx=(2, 8))

            btn_down = ctk.CTkButton(
                row,
                text="▼",
                width=26,
                height=26,
                corner_radius=5,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                fg_color=THEME["secondary_bg"],
                hover_color=THEME["secondary_hover"],
                text_color=THEME["secondary_text"],
                state="normal" if idx < total_arqs - 1 else "disabled",
                command=lambda i=idx: self._trocar_posicao_unir(i, i + 1),
            )
            btn_down.pack(side="right", padx=2)

            btn_up = ctk.CTkButton(
                row,
                text="▲",
                width=26,
                height=26,
                corner_radius=5,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                fg_color=THEME["secondary_bg"],
                hover_color=THEME["secondary_hover"],
                text_color=THEME["secondary_text"],
                state="normal" if idx > 0 else "disabled",
                command=lambda i=idx: self._trocar_posicao_unir(i, i - 1),
            )
            btn_up.pack(side="right", padx=2)

    def _iniciar_drag_unir(self, event, idx: int):
        self._drag_source_idx = idx
        self._drag_target_idx = idx
        self._drag_active = False
        self._drag_start_y = event.y_root

    def _criar_ghost_drag(self, idx: int, x_root: int, y_root: int):
        if self._drag_ghost is not None:
            return
        nome_arq = self.arquivos_unir[idx]["path"].name
        if len(nome_arq) > 38:
            nome_arq = nome_arq[:35] + "..."

        ghost = ctk.CTkToplevel(self)
        ghost.overrideredirect(True)
        ghost.attributes("-topmost", True)
        try:
            ghost.attributes("-alpha", 0.90)
        except Exception:
            pass

        frame = ctk.CTkFrame(
            ghost,
            fg_color=THEME["row_sel_bg"],
            corner_radius=8,
            border_width=2,
            border_color=THEME["primary"],
        )
        frame.pack(fill="both", expand=True)

        lbl = ctk.CTkLabel(
            frame,
            text=f"⠿  Movendo #{idx + 1:02d}: {nome_arq}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_emerald"],
            padx=14,
            pady=6,
        )
        lbl.pack()
        ghost.geometry(f"+{x_root + 16}+{y_root - 14}")
        self._drag_ghost = ghost

    def _destruir_ghost_drag(self):
        if self._drag_ghost is not None:
            try:
                self._drag_ghost.destroy()
            except Exception:
                pass
            self._drag_ghost = None

    def _destacar_alvo_drag(self, target_idx: int):
        """Realça visualmente a linha de destino do soltar (drop) com a paleta Emerald."""
        for i, row in enumerate(self._row_widgets_unir):
            if not row.winfo_exists():
                continue
            if i == target_idx and i != self._drag_source_idx:
                row.configure(
                    fg_color=THEME["row_drop_bg"],
                    border_width=2,
                    border_color=THEME["row_drop_border"],
                )
            elif i == self._drag_source_idx:
                row.configure(
                    fg_color=THEME["header_table_bg"],
                    border_width=1,
                    border_color=THEME["primary"],
                )
            else:
                selecionado = i in self.selecao_unir
                row.configure(
                    fg_color=THEME["row_sel_bg"] if selecionado else THEME["row_bg"],
                    border_width=1,
                    border_color=THEME["row_sel_border"] if selecionado else THEME["row_border"],
                )

    def _mover_drag_unir(self, event):
        if self._drag_source_idx is None or len(self.arquivos_unir) < 2:
            return

        if not self._drag_active:
            if abs(event.y_root - self._drag_start_y) < 5:
                return
            self._drag_active = True
            self._criar_ghost_drag(self._drag_source_idx, event.x_root, event.y_root)

        if self._drag_ghost is not None:
            self._drag_ghost.geometry(f"+{event.x_root + 16}+{event.y_root - 14}")

        y_mouse = event.y_root
        alvo = self._drag_target_idx if self._drag_target_idx is not None else self._drag_source_idx

        for i, row in enumerate(self._row_widgets_unir):
            if not row.winfo_exists():
                continue
            ry = row.winfo_rooty()
            rh = row.winfo_height()
            if ry <= y_mouse <= ry + rh:
                alvo = i
                break
        else:
            if self._row_widgets_unir:
                first_y = self._row_widgets_unir[0].winfo_rooty()
                last_row = self._row_widgets_unir[-1]
                last_bottom = last_row.winfo_rooty() + last_row.winfo_height()
                if y_mouse < first_y:
                    alvo = 0
                elif y_mouse > last_bottom:
                    alvo = len(self._row_widgets_unir) - 1

        if alvo != self._drag_target_idx:
            self._drag_target_idx = alvo
            self._destacar_alvo_drag(alvo)

            if self._drag_ghost is not None:
                for child in self._drag_ghost.winfo_children():
                    for sub in child.winfo_children():
                        if isinstance(sub, ctk.CTkLabel):
                            nome_arq = self.arquivos_unir[self._drag_source_idx]["path"].name
                            if len(nome_arq) > 32:
                                nome_arq = nome_arq[:29] + "..."
                            sub.configure(text=f"⠿  Soltar na posição #{alvo + 1:02d}  ({nome_arq})")

    def _finalizar_drag_unir(self, _event):
        self._destruir_ghost_drag()
        origem = self._drag_source_idx
        destino = self._drag_target_idx
        foi_arrastado = self._drag_active

        self._drag_source_idx = None
        self._drag_target_idx = None
        self._drag_active = False

        if foi_arrastado and origem is not None and destino is not None and origem != destino:
            item = self.arquivos_unir.pop(origem)
            self.arquivos_unir.insert(destino, item)
            self.selecao_unir = {destino}
            self._atualizar_lista_unir_ui()
        elif foi_arrastado:
            self._atualizar_lista_unir_ui()

    def _toggle_item_selecao_unir(self, idx: int, marcado: bool):
        if marcado:
            self.selecao_unir.add(idx)
        else:
            self.selecao_unir.discard(idx)
        self._atualizar_lista_unir_ui()

    def _trocar_posicao_unir(self, i1: int, i2: int):
        if 0 <= i1 < len(self.arquivos_unir) and 0 <= i2 < len(self.arquivos_unir):
            self.arquivos_unir[i1], self.arquivos_unir[i2] = self.arquivos_unir[i2], self.arquivos_unir[i1]
            nova_sel = set()
            for s in self.selecao_unir:
                if s == i1:
                    nova_sel.add(i2)
                elif s == i2:
                    nova_sel.add(i1)
                else:
                    nova_sel.add(s)
            self.selecao_unir = nova_sel
            self._atualizar_lista_unir_ui()

    def _mover_selecionados_cima(self):
        if not self.selecao_unir:
            return
        indices = sorted(self.selecao_unir)
        if indices[0] == 0:
            return
        nova_sel = set()
        for i in indices:
            self.arquivos_unir[i - 1], self.arquivos_unir[i] = self.arquivos_unir[i], self.arquivos_unir[i - 1]
            nova_sel.add(i - 1)
        self.selecao_unir = nova_sel
        self._atualizar_lista_unir_ui()

    def _mover_selecionados_baixo(self):
        if not self.selecao_unir:
            return
        indices = sorted(self.selecao_unir, reverse=True)
        if indices[0] == len(self.arquivos_unir) - 1:
            return
        nova_sel = set()
        for i in indices:
            self.arquivos_unir[i + 1], self.arquivos_unir[i] = self.arquivos_unir[i], self.arquivos_unir[i + 1]
            nova_sel.add(i + 1)
        self.selecao_unir = nova_sel
        self._atualizar_lista_unir_ui()

    def _remover_item_unir(self, idx: int):
        if 0 <= idx < len(self.arquivos_unir):
            self.arquivos_unir.pop(idx)
            self.selecao_unir.clear()
            self._atualizar_lista_unir_ui()

    def _iniciar_uniao(self):
        if len(self.arquivos_unir) < 2:
            messagebox.showwarning("Aviso", "Adicione pelo menos 2 arquivos PDF para realizar a união.")
            return

        nome_saida = self.entry_nome_unir.get().strip() or "documento_unificado.pdf"
        if not nome_saida.lower().endswith(".pdf"):
            nome_saida += ".pdf"

        pasta_str = self.entry_pasta_unir.get().strip()
        if pasta_str:
            pasta_destino = Path(pasta_str)
            if not pasta_destino.exists():
                messagebox.showerror("Erro", f"A pasta de destino informada não existe:\n{pasta_destino}")
                return
        else:
            pasta_destino = self.arquivos_unir[0]["path"].parent

        caminho_final = pasta_destino / nome_saida
        comprimir_depois = self.var_comprimir_apos_unir.get()
        qualidade, max_dim = extrair_parametros_perfil(self.combo_perfil_unir.get())

        self.btn_executar_unir.configure(state="disabled")
        self.btn_add_unir.configure(state="disabled")
        self.btn_acao_lista_unir.configure(state="disabled")
        self.progresso_unir.set(0.05)
        self.box_resultado_unir.pack_forget()

        caminhos_entrada = [x["path"] for x in self.arquivos_unir]

        def worker():
            try:
                tamanho_soma_orig_kb = sum(p.stat().st_size for p in caminhos_entrada if p.exists()) / 1024

                def cb_prog(pct: float, msg: str):
                    self.after(0, lambda: self._atualizar_status_unir(pct, msg))

                res_merge = unir_pdfs(
                    arquivos=caminhos_entrada,
                    caminho_saida=caminho_final,
                    comprimir_apos_unir=comprimir_depois,
                    qualidade=qualidade,
                    dimensao_maxima=max_dim,
                    callback_progresso=cb_prog,
                )

                tam_final_kb = res_merge.get("tamanho_final", caminho_final.stat().st_size / 1024)
                reducao_pct = (
                    (1.0 - (tam_final_kb / tamanho_soma_orig_kb)) * 100.0 if tamanho_soma_orig_kb > 0 else 0.0
                )

                res_final = {
                    "caminho_saida": Path(res_merge.get("caminho_saida", caminho_final)),
                    "total_paginas": res_merge["total_paginas"],
                    "tamanho_antes_kb": tamanho_soma_orig_kb,
                    "tamanho_final_kb": tam_final_kb,
                    "reducao_pct": reducao_pct,
                    "comprimido": comprimir_depois,
                }

                self.after(0, lambda: self._finalizar_uniao_sucesso(res_final))
            except Exception as e:
                self.after(0, lambda: self._finalizar_uniao_erro(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _atualizar_status_unir(self, pct: float, msg: str):
        self.progresso_unir.set(pct)
        self.lbl_status_unir.configure(text=msg)

    def _finalizar_uniao_sucesso(self, res: dict):
        self.btn_executar_unir.configure(state="normal")
        self.btn_add_unir.configure(state="normal")
        self._atualizar_barra_contextual_unir()
        self.progresso_unir.set(1.0)

        self.ultimo_arquivo_gerado_unir = res["caminho_saida"]
        antes_kb = res["tamanho_antes_kb"]
        depois_kb = res["tamanho_final_kb"]
        red_pct = res["reducao_pct"]

        if res["comprimido"]:
            resumo_status = (
                f"✔ Concluído! {res['total_paginas']} pág. • "
                f"{antes_kb:.1f} KB → {depois_kb:.1f} KB ({red_pct:.1f}% de redução)"
            )
            detalhe_msg = (
                f"✔ União e Compressão Concluídas!\n\n"
                f"• Total de páginas: {res['total_paginas']}\n"
                f"• Tamanho Antes:    {antes_kb:.1f} KB\n"
                f"• Tamanho Agora:    {depois_kb:.1f} KB\n"
                f"• Redução Obtida:   {red_pct:.1f}%\n\n"
                f"Salvo em:\n{res['caminho_saida']}"
            )
        else:
            resumo_status = f"✔ PDF Unificado! {res['total_paginas']} pág. ({depois_kb:.1f} KB)"
            detalhe_msg = (
                f"✔ União de PDFs Concluída!\n\n"
                f"• Total de páginas: {res['total_paginas']}\n"
                f"• Tamanho Antes:    {antes_kb:.1f} KB\n"
                f"• Tamanho Agora:    {depois_kb:.1f} KB\n\n"
                f"Salvo em:\n{res['caminho_saida']}"
            )

        self.lbl_status_unir.configure(text=resumo_status)

        self.btn_abrir_arquivo_unir.pack(side="left", padx=4)
        self.btn_abrir_pasta_unir.pack(side="left", padx=4)
        self.box_resultado_unir.pack(side="right")

        messagebox.showinfo("Operação Concluída", detalhe_msg)

    def _finalizar_uniao_erro(self, msg_erro: str):
        self.btn_executar_unir.configure(state="normal")
        self.btn_add_unir.configure(state="normal")
        self._atualizar_barra_contextual_unir()
        self.progresso_unir.set(0)
        self.lbl_status_unir.configure(text=f"Erro ao unir PDFs: {msg_erro}")
        messagebox.showerror("Erro na União", f"Ocorreu um erro ao unir os arquivos:\n{msg_erro}")

    def _abrir_ultimo_arquivo_unir(self):
        if self.ultimo_arquivo_gerado_unir:
            abrir_arquivo_padrao(self.ultimo_arquivo_gerado_unir)

    def _abrir_ultima_pasta_unir(self):
        if self.ultimo_arquivo_gerado_unir:
            abrir_no_explorer(self.ultimo_arquivo_gerado_unir)

    # ==========================================================================
    # LÓGICA E EVENTOS DA ABA 2: COMPRIMIR PDF(s)
    # ==========================================================================
    def _selecionar_arquivos_comprimir(self):
        caminhos = filedialog.askopenfilenames(
            title="Adicionar PDF(s) para Comprimir",
            filetypes=[("Arquivos PDF", "*.pdf")],
        )
        if not caminhos:
            return

        novos = [Path(c) for c in caminhos if Path(c).exists()]
        for n in novos:
            if n not in self.arquivos_comprimir:
                self.arquivos_comprimir.append(n)

        self._atualizar_lista_comprimir_ui()

    def _toggle_selecionar_todos_comp(self):
        if not self.arquivos_comprimir:
            self.var_master_comp.set(False)
            return
        if self.var_master_comp.get():
            self.selecao_comprimir = set(range(len(self.arquivos_comprimir)))
        else:
            self.selecao_comprimir.clear()
        self._atualizar_lista_comprimir_ui()

    def _acao_contextual_remover_comp(self):
        if not self.arquivos_comprimir:
            return
        if self.selecao_comprimir:
            self.arquivos_comprimir = [
                item for idx, item in enumerate(self.arquivos_comprimir) if idx not in self.selecao_comprimir
            ]
            self.selecao_comprimir.clear()
        else:
            self.arquivos_comprimir.clear()
            self.selecao_comprimir.clear()
            self.entry_nome_comp.delete(0, tk.END)
        self._atualizar_lista_comprimir_ui()

    def _atualizar_barra_contextual_comp(self):
        total = len(self.arquivos_comprimir)
        sel = len(self.selecao_comprimir)
        self.var_master_comp.set(total > 0 and sel == total)

        if total == 0:
            self.btn_acao_lista_comp.configure(text="🗑️ Limpar Lista", state="disabled")
        elif sel > 0:
            self.btn_acao_lista_comp.configure(text=f"🗑️ Remover ({sel})", state="normal")
        else:
            self.btn_acao_lista_comp.configure(text="🗑️ Limpar Lista", state="normal")

    def _atualizar_lista_comprimir_ui(self):
        for w in self.scroll_comp.winfo_children():
            w.destroy()

        self._atualizar_barra_contextual_comp()

        total = len(self.arquivos_comprimir)
        if total == 0:
            self.lbl_comp_qtd.configure(text="0 arquivo(s) na fila")
            box_vazio = ctk.CTkFrame(self.scroll_comp, fg_color="transparent")
            box_vazio.pack(fill="both", expand=True, pady=48)

            lbl_icone = ctk.CTkLabel(
                box_vazio,
                text="⚡",
                font=ctk.CTkFont(family=FONT_FAMILY, size=32),
            )
            lbl_icone.pack(pady=(0, 6))

            lbl_vazio = ctk.CTkLabel(
                box_vazio,
                text="Nenhum PDF na fila de compressão.\nClique em '➕ Adicionar PDF(s)' acima para selecionar.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                text_color=THEME["text_muted"],
                justify="center",
            )
            lbl_vazio.pack()
            return

        total_bytes = sum(p.stat().st_size for p in self.arquivos_comprimir if p.exists())
        sel_count = len(self.selecao_comprimir)
        sel_texto = f" • {sel_count} marcado(s)" if sel_count > 0 else ""
        self.lbl_comp_qtd.configure(text=f"{total} PDF(s) • Total: {formatar_tamanho(total_bytes)}{sel_texto}")

        if total == 1:
            primeiro = self.arquivos_comprimir[0]
            if not self.entry_nome_comp.get().strip():
                self.entry_nome_comp.delete(0, tk.END)
                self.entry_nome_comp.insert(0, f"{primeiro.stem}_otimizado.pdf")

        for idx, item in enumerate(self.arquivos_comprimir):
            selecionado = idx in self.selecao_comprimir
            bg_color = THEME["row_sel_bg"] if selecionado else THEME["row_bg"]
            border_color = THEME["row_sel_border"] if selecionado else THEME["row_border"]

            row = ctk.CTkFrame(
                self.scroll_comp,
                fg_color=bg_color,
                border_width=1,
                border_color=border_color,
                corner_radius=6,
                height=42,
            )
            row.pack(fill="x", padx=4, pady=3)
            row.pack_propagate(False)

            var_chk = tk.BooleanVar(value=selecionado)
            chk = ctk.CTkCheckBox(
                row,
                text="",
                width=20,
                checkbox_width=18,
                checkbox_height=18,
                corner_radius=4,
                fg_color=THEME["primary"],
                hover_color=THEME["primary_hover"],
                border_color=THEME["input_border"],
                variable=var_chk,
                command=lambda i=idx, v=var_chk: self._toggle_item_selecao_comp(i, v.get()),
            )
            chk.pack(side="left", padx=(8, 4))

            lbl_idx = ctk.CTkLabel(
                row,
                text=f"#{idx + 1:02d}",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                text_color=THEME["text_emerald"] if selecionado else THEME["text_secondary"],
                width=36,
                anchor="w",
            )
            lbl_idx.pack(side="left", padx=(2, 6))

            tam_str = formatar_tamanho(item.stat().st_size) if item.exists() else "0 KB"
            lbl_info = ctk.CTkLabel(
                row,
                text=f"{item.name}   ({tam_str})",
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold" if selecionado else "normal"),
                text_color=THEME["text_primary"],
                anchor="w",
            )
            lbl_info.pack(side="left", padx=4, fill="x", expand=True)

            btn_del = ctk.CTkButton(
                row,
                text="✖",
                width=28,
                height=26,
                corner_radius=5,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                fg_color=THEME["danger_bg"],
                hover_color=THEME["danger_hover"],
                text_color=THEME["danger_text"],
                command=lambda p=item: self._remover_item_comprimir(p),
            )
            btn_del.pack(side="right", padx=8)

    def _toggle_item_selecao_comp(self, idx: int, marcado: bool):
        if marcado:
            self.selecao_comprimir.add(idx)
        else:
            self.selecao_comprimir.discard(idx)
        self._atualizar_lista_comprimir_ui()

    def _remover_item_comprimir(self, p: Path):
        if p in self.arquivos_comprimir:
            self.arquivos_comprimir.remove(p)
            self.selecao_comprimir.clear()
            self._atualizar_lista_comprimir_ui()

    def _iniciar_compressao(self):
        if not self.arquivos_comprimir:
            messagebox.showwarning("Aviso", "Adicione ao menos um arquivo PDF para comprimir.")
            return

        qualidade, max_dim = extrair_parametros_perfil(self.combo_perfil.get())
        pasta_destino = self.entry_pasta_comp.get().strip()
        nome_customizado = self.entry_nome_comp.get().strip()

        self.btn_executar_comp.configure(state="disabled")
        self.btn_add_comp.configure(state="disabled")
        self.btn_acao_lista_comp.configure(state="disabled")
        self.progresso_comp.set(0.0)
        self.box_resultado_comp.pack_forget()

        def worker():
            total = len(self.arquivos_comprimir)
            resultados = []

            for i, p_in in enumerate(self.arquivos_comprimir, start=1):
                pct_base = (i - 1) / total

                if pasta_destino and Path(pasta_destino).is_dir():
                    dest_dir = Path(pasta_destino)
                else:
                    dest_dir = p_in.parent

                if total == 1 and nome_customizado:
                    nome_final = (
                        nome_customizado if nome_customizado.lower().endswith(".pdf") else f"{nome_customizado}.pdf"
                    )
                else:
                    nome_final = f"{p_in.stem}_otimizado.pdf"

                p_out = dest_dir / nome_final

                def cb_prog(sub_pct: float, msg: str):
                    global_pct = pct_base + (sub_pct / total)
                    self.after(0, lambda: self._atualizar_status_comp(global_pct, f"[{i}/{total}] {msg}"))

                try:
                    res = comprimir_pdf(
                        caminho_entrada=p_in,
                        caminho_saida=p_out,
                        qualidade=qualidade,
                        dimensao_maxima=max_dim,
                        callback_progresso=cb_prog,
                    )
                    res["arquivo_entrada"] = p_in.name
                    resultados.append(res)
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror("Erro", f"Erro ao comprimir {p_in.name}:\n{e}"))

            self.after(0, lambda: self._finalizar_compressao(resultados, total))

        threading.Thread(target=worker, daemon=True).start()

    def _atualizar_status_comp(self, pct: float, msg: str):
        self.progresso_comp.set(pct)
        self.lbl_status_comp.configure(text=msg)

    def _finalizar_compressao(self, resultados: list[dict], total: int):
        self.btn_executar_comp.configure(state="normal")
        self.btn_add_comp.configure(state="normal")
        self._atualizar_barra_contextual_comp()
        self.progresso_comp.set(1.0)

        sucessos = len(resultados)
        if sucessos > 0:
            ultimo_saida = resultados[-1].get("caminho_saida")
            self.ultimo_arquivo_gerado_comp = ultimo_saida

            self.btn_abrir_arquivo_comp.pack(side="left", padx=4)
            self.btn_abrir_pasta_comp.pack(side="left", padx=4)
            self.box_resultado_comp.pack(side="right")

            soma_orig = sum(r.get("tamanho_original", 0.0) for r in resultados)
            soma_final = sum(r.get("tamanho_final", 0.0) for r in resultados)
            reducao_total = (1.0 - (soma_final / soma_orig)) * 100.0 if soma_orig > 0 else 0.0

            self.lbl_status_comp.configure(
                text=f"✔ Concluído! {soma_orig:.1f} KB → {soma_final:.1f} KB ({reducao_total:.1f}% de redução)"
            )

            if total == 1:
                r = resultados[0]
                msg_box = (
                    f"✔ Compressão Concluída com Sucesso!\n\n"
                    f"• Arquivo:          {r.get('arquivo_entrada')}\n"
                    f"• Tamanho Antes:    {r.get('tamanho_original', 0.0):.1f} KB\n"
                    f"• Tamanho Depois:   {r.get('tamanho_final', 0.0):.1f} KB\n"
                    f"• Redução Obtida:   {r.get('reducao_pct', 0.0):.1f}%\n\n"
                    f"Arquivo salvo em:\n{ultimo_saida}"
                )
            else:
                msg_box = (
                    f"✔ Compressão em Lote Concluída!\n\n"
                    f"• Total de arquivos:    {sucessos}/{total}\n"
                    f"• Tamanho Total Antes:  {soma_orig:.1f} KB\n"
                    f"• Tamanho Total Depois: {soma_final:.1f} KB\n"
                    f"• Redução Média:        {reducao_total:.1f}%\n\n"
                    f"Arquivos salvos em:\n{Path(ultimo_saida).parent}"
                )

            messagebox.showinfo("Compressão Concluída", msg_box)
        else:
            self.lbl_status_comp.configure(text=f"Processamento finalizado com falhas ({sucessos}/{total}).")

    def _abrir_ultimo_arquivo_comp(self):
        if self.ultimo_arquivo_gerado_comp:
            abrir_arquivo_padrao(self.ultimo_arquivo_gerado_comp)

    def _abrir_ultima_pasta_comp(self):
        if self.ultimo_arquivo_gerado_comp:
            abrir_no_explorer(self.ultimo_arquivo_gerado_comp)


def iniciar_interface():
    app = AppPDFMaster()
    app.mainloop()


if __name__ == "__main__":
    iniciar_interface()
