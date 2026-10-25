"""
Modal de Busca Rápida de Produtos no Estoque (PDV)
Arquivo: views/product_search_modal.py

Permite ao operador/caixa localizar produtos manualmente por nome,
código de barras ou categoria, verificando estoque e preço instantaneamente,
ideal para quando o estabelecimento ainda não possui leitor óptico USB.
"""

import re
import tkinter as tk
from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk

import theme
import database as db


def formatar_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class ProductSearchModal(ctk.CTkToplevel):
    """Modal de pesquisa e seleção ágil de produtos para o caixa PDV."""

    def __init__(
        self,
        parent,
        on_produto_selecionado: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_select_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        *args,
        **kwargs,
    ):
        super().__init__(parent)
        self.parent = parent
        self.on_produto_selecionado = on_produto_selecionado or on_select_callback

        self.title("🔍 Buscar Produto no Estoque (PDV)")
        self.geometry("700x560")
        self.resizable(False, False)
        self.configure(fg_color=theme.MODAL_BG)

        # Modalidade exclusiva
        self.transient(parent)
        self.grab_set()

        self.todos_produtos: List[Dict[str, Any]] = []
        self.produtos_filtrados: List[Dict[str, Any]] = []

        self._centralizar()
        self._criar_layout()
        self._carregar_produtos()

        # Atalhos
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self._selecionar_primeiro())

        # Foco imediato no campo de busca
        self.after(80, lambda: self.entry_busca.focus_set())

    def _centralizar(self):
        theme.centralizar_toplevel(self, 720, 560)

    def _criar_layout(self):
        card = ctk.CTkFrame(self, corner_radius=14, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # Cabeçalho
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 10))

        ctk.CTkLabel(
            head,
            text="🔍 Localizar Produto no Estoque",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            head,
            text="Digite o nome, código de barras ou categoria para buscar. Clique em 'Selecionar' ou tecle Enter.",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        # Campo de Busca com auto-filtro
        busca_row = ctk.CTkFrame(card, fg_color="transparent")
        busca_row.pack(fill="x", padx=20, pady=(0, 10))

        self.entry_busca = ctk.CTkEntry(
            busca_row,
            placeholder_text="Digite para buscar produto no estoque...",
            height=40,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ACCENT_BLUE,
            border_width=1,
            text_color=theme.ENTRY_TEXT,
            font=ctk.CTkFont(size=13),
        )
        self.entry_busca.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_busca.bind("<KeyRelease>", self._ao_digitar_busca)

        btn_limpar = ctk.CTkButton(
            busca_row,
            text="Limpar",
            width=75,
            height=40,
            corner_radius=8,
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._limpar_busca,
        )
        btn_limpar.pack(side="right")

        # Cabeçalho da Lista
        col_header = ctk.CTkFrame(card, height=30, fg_color=theme.INNER_CARD_BG, corner_radius=6)
        col_header.pack(fill="x", padx=20, pady=(0, 6))

        ctk.CTkLabel(col_header, text="PRODUTO / CATEGORIA", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(side="left", padx=12)
        ctk.CTkLabel(col_header, text="AÇÃO", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY, width=90).pack(side="right", padx=12)
        ctk.CTkLabel(col_header, text="PREÇO", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY, width=95).pack(side="right", padx=6)
        ctk.CTkLabel(col_header, text="ESTOQUE", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY, width=85).pack(side="right", padx=6)

        # Container com Scroll para os Produtos
        self.scroll_produtos = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.scroll_produtos.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Rodapé com contador e atalho de fechar
        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 12))

        self.lbl_contador = ctk.CTkLabel(
            footer,
            text="Carregando produtos...",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_MUTED,
        )
        self.lbl_contador.pack(side="left")

        btn_fechar = ctk.CTkButton(
            footer,
            text="Fechar (Esc)",
            width=110,
            height=34,
            corner_radius=6,
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self.destroy,
        )
        btn_fechar.pack(side="right")

    def _carregar_produtos(self):
        try:
            self.todos_produtos = db.listar_produtos()
            self._filtrar_e_renderizar()
        except Exception as e:
            print(f"Erro ao carregar produtos na busca: {e}")

    def _ao_digitar_busca(self, event=None):
        if hasattr(self, "_debounce_timer") and self._debounce_timer:
            self.after_cancel(self._debounce_timer)
        self._debounce_timer = self.after(150, self._filtrar_e_renderizar)

    def _limpar_busca(self):
        if hasattr(self, "_debounce_timer") and self._debounce_timer:
            self.after_cancel(self._debounce_timer)
            self._debounce_timer = None
        self.entry_busca.delete(0, tk.END)
        self._filtrar_e_renderizar()
        self.entry_busca.focus_set()

    def _filtrar_e_renderizar(self):
        if hasattr(self, "_debounce_timer") and self._debounce_timer:
            self.after_cancel(self._debounce_timer)
            self._debounce_timer = None

        termo = self.entry_busca.get().strip().lower()
        termo_limpo = re.sub(r"[^\w\s]", " ", termo)
        tokens = [t for t in termo_limpo.split() if t]

        if not tokens:
            self.produtos_filtrados = list(self.todos_produtos)
        else:
            self.produtos_filtrados = []
            frase = " ".join(tokens)
            for p in self.todos_produtos:
                raw_text = f"{p['nome']} {p.get('codigo_barras', '')} {p.get('categoria', '')}".lower()
                clean_text = re.sub(r"[^\w\s]", " ", raw_text)

                # 1. Correspondência por frase completa
                if frase in clean_text:
                    self.produtos_filtrados.append(p)
                    continue

                # 2. Correspondência por tokens (com limite de palavra para tokens curtos)
                match_all = True
                for t in tokens:
                    if len(t) <= 2:
                        if not re.search(rf"\b{re.escape(t)}\b", clean_text):
                            match_all = False
                            break
                    else:
                        if t not in clean_text:
                            match_all = False
                            break
                if match_all:
                    self.produtos_filtrados.append(p)

        # Limpa widgets anteriores
        for w in self.scroll_produtos.winfo_children():
            w.destroy()

        total = len(self.produtos_filtrados)
        self.lbl_contador.configure(text=f"Exibindo {total} produto(s) encontrado(s)")

        if not self.produtos_filtrados:
            ctk.CTkLabel(
                self.scroll_produtos,
                text="Nenhum produto corresponde aos termos da pesquisa.",
                font=ctk.CTkFont(size=12),
                text_color=theme.TEXT_MUTED,
            ).pack(pady=40)
            return

        for idx, p in enumerate(self.produtos_filtrados[:50]):  # Limite de 50 para máxima performance
            estoque = p.get("estoque", 0)
            preco = p.get("preco", 0.0)
            esgotado = estoque <= 0

            row = ctk.CTkFrame(
                self.scroll_produtos,
                fg_color=theme.INNER_CARD_BG,
                corner_radius=8,
                border_width=1,
                border_color=theme.BORDER_COLOR,
            )
            row.pack(fill="x", pady=3)

            # Coluna 1: Nome e Detalhes
            info_col = ctk.CTkFrame(row, fg_color="transparent")
            info_col.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=6)

            ctk.CTkLabel(
                info_col,
                text=p["nome"],
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=theme.TEXT_PRIMARY if not esgotado else theme.TEXT_MUTED,
                anchor="w",
            ).pack(fill="x")

            sub_txt = f"Cód: {p.get('codigo_barras') or 'S/ CÓDIGO'} | Cat: {p.get('categoria') or 'Geral'}"
            ctk.CTkLabel(
                info_col,
                text=sub_txt,
                font=ctk.CTkFont(size=10),
                text_color=theme.TEXT_SECONDARY,
                anchor="w",
            ).pack(fill="x")

            # Coluna 2: Botão Selecionar
            btn_sel = ctk.CTkButton(
                row,
                text="Selecionar" if not esgotado else "Esgotado",
                width=85,
                height=30,
                corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=theme.ACCENT_GREEN if not esgotado else theme.BTN_SECONDARY_BG,
                hover_color=theme.ACCENT_GREEN_HOVER if not esgotado else theme.BTN_SECONDARY_BG,
                text_color="#FFFFFF" if not esgotado else theme.TEXT_MUTED,
                state="normal" if not esgotado else "disabled",
                command=lambda prod=p: self._selecionar(prod),
            )
            btn_sel.pack(side="right", padx=(4, 12), pady=6)

            # Coluna 3: Preço
            ctk.CTkLabel(
                row,
                text=formatar_moeda(preco),
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=theme.PRICE_COLOR if not esgotado else theme.TEXT_MUTED,
                width=90,
                anchor="e",
            ).pack(side="right", padx=6)

            # Coluna 4: Estoque
            cor_estoque = theme.STOCK_COLOR[1] if estoque > 5 else (theme.WARNING_COLOR[1] if estoque > 0 else theme.ACCENT_RED[1])
            txt_est = f"{estoque} un" if estoque > 0 else "0 un"
            ctk.CTkLabel(
                row,
                text=txt_est,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=cor_estoque,
                width=80,
                anchor="center",
            ).pack(side="right", padx=6)

    def _selecionar_primeiro(self):
        if hasattr(self, "_debounce_timer") and self._debounce_timer:
            self.after_cancel(self._debounce_timer)
            self._debounce_timer = None
            self._filtrar_e_renderizar()
        if self.produtos_filtrados:
            for p in self.produtos_filtrados:
                if p.get("estoque", 0) > 0:
                    self._selecionar(p)
                    return

    def _selecionar(self, produto: Dict[str, Any]):
        if self.on_produto_selecionado:
            self.on_produto_selecionado(produto)
        self.destroy()
