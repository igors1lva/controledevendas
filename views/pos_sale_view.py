"""
Módulo de Visualização: Nova Venda Balcão (PDV)
Arquivo: views/pos_sale_view.py

Tela dedicada exclusivamente à realização de novas vendas no balcão,
com suporte a leitor de código de barras USB, seleção rápida de produtos,
cálculo instantâneo de totais, tecla de atalho F2/Enter e baixa atômica de estoque.
"""

import os
import re
import tempfile
import subprocess
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk

import database as db
import reports
import theme
import clipboard_utils as clip


from views.cash_closure_modal import CashClosureModal
from views.product_search_modal import ProductSearchModal
from views.payment_modal import PaymentModal


def formatar_moeda(valor: float) -> str:
    """Formata valor numérico para padrão monetário brasileiro R$ 0,00."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class POSSaleView(ctk.CTkFrame):
    """Tela de checkout dedicada para realizar novas vendas no PDV."""

    def __init__(
        self,
        parent,
        on_sale_completed_callback: Optional[Callable] = None,
        on_goto_historico: Optional[Callable] = None,
        on_cash_closed_callback: Optional[Callable] = None,
    ):
        super().__init__(parent, fg_color="transparent")
        self.on_sale_completed_callback = on_sale_completed_callback
        self.on_goto_historico = on_goto_historico
        self.on_cash_closed_callback = on_cash_closed_callback

        self.produtos_disponiveis: List[Dict[str, Any]] = []
        self.mapa_produtos: Dict[str, Dict[str, Any]] = {}
        self.produto_selecionado: Optional[Dict[str, Any]] = None
        self.ultima_venda_info: Optional[Dict[str, Any]] = None
        self.forma_pagamento_selecionada: str = "DINHEIRO"
        self.botoes_pgto = {}
        self.carrinho: List[Dict[str, Any]] = []
        self.modo_painel_direito: str = "carrinho"
        self._debounce_timer = None
        self._necessita_recarregar = True

        self._criar_layout()
        self._renderizar_carrinho()
        self.recarregar_dados()

    def _criar_layout(self):
        # 1. Cabeçalho
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(16, 12))

        col_tit = ctk.CTkFrame(header_frame, fg_color="transparent")
        col_tit.pack(side="left")

        lbl_titulo = ctk.CTkLabel(
            col_tit,
            text="⚡ Nova Venda Balcão (PDV)",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        lbl_titulo.pack(anchor="w")

        lbl_subtitulo = ctk.CTkLabel(
            col_tit,
            text="Bipe o código de barras com o leitor USB ou selecione o produto, confira os valores e confirme no F2.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        )
        lbl_subtitulo.pack(anchor="w")

        actions_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions_box.pack(side="right")

        btn_fechar_caixa = ctk.CTkButton(
            actions_box,
            text="🔒 Fechar Caixa",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=38,
            corner_radius=8,
            fg_color="#D97706",
            hover_color="#B45309",
            text_color="#FFFFFF",
            command=self._abrir_modal_fechamento_caixa,
        )
        btn_fechar_caixa.pack(side="right", padx=(8, 0))

        self.btn_abrir_excel_pdv = ctk.CTkButton(
            actions_box,
            text="📊 Abrir Excel",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=38,
            corner_radius=8,
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            command=self._abrir_excel_rapido,
        )
        self.btn_abrir_excel_pdv.pack(side="right", padx=(8, 0))

        if self.on_goto_historico:
            btn_hist = ctk.CTkButton(
                actions_box,
                text="🕒 Ver Histórico de Vendas",
                font=ctk.CTkFont(size=12, weight="bold"),
                height=38,
                corner_radius=8,
                fg_color=theme.BTN_SECONDARY_BG,
                hover_color=theme.BTN_SECONDARY_HOVER,
                text_color=theme.BTN_SECONDARY_TEXT,
                command=self.on_goto_historico,
            )
            btn_hist.pack(side="right")

        # 2. Corpo Dividido em Duas Colunas
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        # Coluna Esquerda: Terminal de Operação com contorno destacado (sem barra de rolagem visual)
        op_card = ctk.CTkScrollableFrame(body, corner_radius=12, fg_color=theme.CARD_BG, border_width=2, border_color="#3B82F6")
        op_card.pack(side="left", fill="both", expand=True, padx=(0, 12))
        if hasattr(op_card, "_scrollbar"):
            op_card._scrollbar.grid_forget()
            op_card._parent_frame.grid_columnconfigure(1, weight=0, minsize=0)
            op_card._parent_canvas.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=0, pady=0)

        # Cabeçalho do Card com Título e Tag Não-Fiscal
        op_head = ctk.CTkFrame(op_card, fg_color="transparent")
        op_head.pack(fill="x", padx=24, pady=(20, 10))

        ctk.CTkLabel(
            op_head,
            text="🛒 Caixa Operacional",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            op_head,
            text="Operação Gerencial / Não-Fiscal",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color=theme.TEXT_MUTED,
        ).pack(side="right")

        # Campo de Bipagem por Código de Barras (Leitor USB)
        ctk.CTkLabel(
            op_card,
            text="🏷️ Bipar Código de Barras (Leitor USB):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=24, pady=(2, 2))

        self.entry_bipar = ctk.CTkEntry(
            op_card,
            placeholder_text="Bipe o código com o leitor óptico USB ou digite e tecle Enter...",
            height=42,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
            font=ctk.CTkFont(size=13),
        )
        self.entry_bipar.pack(fill="x", padx=24, pady=(0, 12))
        self.entry_bipar.bind("<Return>", self._ao_bipar_codigo_barras)
        self.entry_bipar.bind("<KP_Enter>", self._ao_bipar_codigo_barras)

        # Seleção e Busca de Produto em Estoque (Filtro por Palavras-Chave)
        head_sel = ctk.CTkFrame(op_card, fg_color="transparent")
        head_sel.pack(fill="x", padx=24, pady=(2, 2))

        ctk.CTkLabel(
            head_sel,
            text="🔍 Digitar / Buscar Produto em Estoque:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        self.lbl_busca_contador = ctk.CTkLabel(
            head_sel,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.PRICE_COLOR[1] if isinstance(theme.PRICE_COLOR, tuple) else theme.PRICE_COLOR,
        )
        self.lbl_busca_contador.pack(side="right")

        # Linha 1: Campo de digitação de palavras-chave + Botão de Catálogo (F3)
        row_busca = ctk.CTkFrame(op_card, fg_color="transparent")
        row_busca.pack(fill="x", padx=24, pady=(0, 6))

        self.entry_busca_produto = ctk.CTkEntry(
            row_busca,
            placeholder_text="Digite palavras-chave (ex: anel de prata 925 azul)...",
            height=42,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
            font=ctk.CTkFont(size=13),
        )
        self.entry_busca_produto.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_busca_produto.bind("<KeyRelease>", self._ao_digitar_busca_produto)
        self.entry_busca_produto.bind("<Return>", self._ao_confirmar_busca_produto)
        self.entry_busca_produto.bind("<KP_Enter>", self._ao_confirmar_busca_produto)

        self.btn_buscar_estoque = ctk.CTkButton(
            row_busca,
            text="🔍 Catálogo (F3)",
            width=135,
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            command=self._abrir_modal_busca_estoque,
        )
        self.btn_buscar_estoque.pack(side="right")

        # Linha 2: Dropdown de seleção rápida dos produtos filtrados e botão limpar
        row_sel_prod = ctk.CTkFrame(op_card, fg_color="transparent")
        row_sel_prod.pack(fill="x", padx=24, pady=(0, 14))

        self.combo_produtos = ctk.CTkComboBox(
            row_sel_prod,
            values=["Nenhum produto disponível"],
            height=38,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            button_color=theme.ACCENT_BLUE,
            button_hover_color=theme.ACCENT_BLUE_HOVER,
            dropdown_fg_color=theme.CARD_BG,
            dropdown_hover_color=theme.INNER_CARD_BG,
            font=ctk.CTkFont(size=12),
            command=self._ao_selecionar_produto,
        )
        self.combo_produtos.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_limpar_busca = ctk.CTkButton(
            row_sel_prod,
            text="✖ Limpar",
            width=80,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._limpar_busca_produto,
        )
        self.btn_limpar_busca.pack(side="right")

        # Indicadores do Produto
        grid_info = ctk.CTkFrame(op_card, fg_color="transparent")
        grid_info.pack(fill="x", padx=24, pady=(0, 14))

        # Preço Unitário
        card_p = ctk.CTkFrame(grid_info, corner_radius=8, fg_color=theme.INNER_CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        card_p.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=4)
        ctk.CTkLabel(card_p, text="VALOR UNITÁRIO", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(8, 2))
        self.lbl_preco = ctk.CTkLabel(card_p, text="R$ 0,00", font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.PRICE_COLOR)
        self.lbl_preco.pack(pady=(0, 8))

        # Estoque
        card_e = ctk.CTkFrame(grid_info, corner_radius=8, fg_color=theme.INNER_CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        card_e.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
        ctk.CTkLabel(card_e, text="ESTOQUE DISPONÍVEL", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(8, 2))
        self.lbl_estoque = ctk.CTkLabel(card_e, text="0 un", font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.STOCK_COLOR)
        self.lbl_estoque.pack(pady=(0, 8))

        # Quantidade
        ctk.CTkLabel(op_card, text="Quantidade:", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=24, pady=(4, 2))

        qtd_box = ctk.CTkFrame(op_card, fg_color="transparent")
        qtd_box.pack(fill="x", padx=24, pady=(0, 8))

        ctk.CTkButton(
            qtd_box,
            text="-",
            width=46,
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(size=18, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._diminuir_qtd,
        ).pack(side="left", padx=(0, 8))

        self.entry_qtd = ctk.CTkEntry(
            qtd_box,
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(size=16, weight="bold"),
            justify="center",
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
        )
        self.entry_qtd.insert(0, "1")
        self.entry_qtd.pack(side="left", fill="x", expand=True)
        self.entry_qtd.bind("<KeyRelease>", lambda event: self._atualizar_subtotal())
        self.entry_qtd.bind("<Return>", self._ao_teclar_enter_qtd)
        self.entry_qtd.bind("<KP_Enter>", self._ao_teclar_enter_qtd)

        ctk.CTkButton(
            qtd_box,
            text="+",
            width=46,
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(size=18, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._aumentar_qtd,
        ).pack(side="left", padx=(8, 0))

        # Atalhos rápidos de quantidade (soma progressiva ao clicar)
        pills_qtd = ctk.CTkFrame(op_card, fg_color="transparent")
        pills_qtd.pack(fill="x", padx=24, pady=(0, 10))
        for q in [1, 2, 3, 5, 10]:
            ctk.CTkButton(
                pills_qtd,
                text=f"{q}x",
                width=45,
                height=26,
                corner_radius=6,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=theme.INNER_CARD_BG,
                text_color=theme.TEXT_SECONDARY,
                hover_color=theme.BTN_SECONDARY_HOVER,
                border_width=1,
                border_color=theme.BORDER_COLOR,
                command=lambda v=q: self._somar_qtd(v),
            ).pack(side="left", padx=2)

        # Botão Prominente: Adicionar ao Carrinho de Compras
        self.btn_adicionar_carrinho = ctk.CTkButton(
            op_card,
            text="🛒 + Adicionar ao Carrinho (F4)",
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            command=self._adicionar_ao_carrinho,
        )
        self.btn_adicionar_carrinho.pack(fill="x", padx=24, pady=(0, 12))
        self.btn_adicionar_carrinho.bind("<Return>", lambda e: self._adicionar_ao_carrinho())
        self.btn_adicionar_carrinho.bind("<KP_Enter>", lambda e: self._adicionar_ao_carrinho())

        # Vincula atalhos de adicionar ao carrinho
        self.bind("<F4>", lambda e: self._adicionar_ao_carrinho())
        self.entry_busca_produto.bind("<F4>", lambda e: (self._adicionar_ao_carrinho(), "break")[1])
        self.entry_qtd.bind("<F4>", lambda e: (self._adicionar_ao_carrinho(), "break")[1])
        self.entry_bipar.bind("<F4>", lambda e: (self._adicionar_ao_carrinho(), "break")[1])

        # Visor de Subtotal / Total da Venda
        total_card = ctk.CTkFrame(op_card, corner_radius=10, fg_color=theme.INNER_CARD_BG, border_width=1, border_color=theme.ACCENT_BLUE)
        total_card.pack(fill="x", padx=24, pady=(0, 14))

        self.lbl_subtotal_titulo = ctk.CTkLabel(total_card, text="SUBTOTAL DA VENDA", font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_SECONDARY)
        self.lbl_subtotal_titulo.pack(pady=(12, 2))
        self.lbl_subtotal = ctk.CTkLabel(total_card, text="R$ 0,00", font=ctk.CTkFont(size=28, weight="bold"), text_color=theme.PRICE_COLOR)
        self.lbl_subtotal.pack(pady=(0, 12))

        # Botão Confirmar (com atalho F2 - abre modal de pagamento)
        self.btn_confirmar = ctk.CTkButton(
            op_card,
            text="✔ CONFIRMAR VENDA (F2)",
            height=48,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            border_width=1,
            border_color="#10B981",
            command=self._confirmar_venda,
        )
        self.btn_confirmar.pack(fill="x", padx=24, pady=(4, 8))

        # Feedback Banner
        self.lbl_feedback = ctk.CTkLabel(
            op_card,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.ACCENT_GREEN[1],
            wraplength=440,
        )
        self.lbl_feedback.pack(padx=24, pady=(0, 16))

        # Coluna Direita: Painel Lateral (Carrinho de Compras Interativo & Comprovante)
        recibo_card = ctk.CTkFrame(body, width=410, corner_radius=12, fg_color=theme.CARD_BG, border_width=2, border_color=theme.BORDER_COLOR)
        recibo_card.pack(side="right", fill="both", expand=False, padx=(12, 0))
        recibo_card.pack_propagate(False)

        # Seletor Superior de Abas (Carrinho vs Cupom)
        tabs_frame = ctk.CTkFrame(recibo_card, fg_color="transparent")
        tabs_frame.pack(fill="x", padx=16, pady=(16, 10))

        self.btn_tab_carrinho = ctk.CTkButton(
            tabs_frame,
            text="🛒 Carrinho (0)",
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            command=lambda: self._alternar_aba_lateral("carrinho"),
        )
        self.btn_tab_carrinho.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_tab_recibo = ctk.CTkButton(
            tabs_frame,
            text="🧾 Último Cupom",
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=theme.INNER_CARD_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.TEXT_SECONDARY,
            command=lambda: self._alternar_aba_lateral("recibo"),
        )
        self.btn_tab_recibo.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # --- CONTAINER 1: CARRINHO DE COMPRAS ---
        self.container_carrinho = ctk.CTkFrame(recibo_card, fg_color="transparent")
        self.container_carrinho.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Barra de Ações do Carrinho
        row_carrinho_acoes = ctk.CTkFrame(self.container_carrinho, fg_color="transparent")
        row_carrinho_acoes.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            row_carrinho_acoes,
            text="Itens Acumulados:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        self.btn_limpar_carrinho = ctk.CTkButton(
            row_carrinho_acoes,
            text="🗑️ Limpar Tudo",
            width=95,
            height=26,
            corner_radius=6,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.ACCENT_RED[0] if isinstance(theme.ACCENT_RED, tuple) else "#7F1D1D",
            text_color=theme.BTN_SECONDARY_TEXT,
            state="disabled",
            command=self._limpar_carrinho,
        )
        self.btn_limpar_carrinho.pack(side="right")

        # Lista com Scroll dos Itens do Carrinho (sem barra de rolagem visual)
        self.scroll_carrinho = ctk.CTkScrollableFrame(
            self.container_carrinho,
            corner_radius=10,
            fg_color=theme.INNER_CARD_BG,
            border_width=1,
            border_color=theme.BORDER_COLOR,
        )
        self.scroll_carrinho.pack(fill="both", expand=True, pady=(0, 10))
        if hasattr(self.scroll_carrinho, "_scrollbar"):
            self.scroll_carrinho._scrollbar.grid_forget()
            self.scroll_carrinho._parent_frame.grid_columnconfigure(1, weight=0, minsize=0)
            self.scroll_carrinho._parent_canvas.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=0, pady=0)

        # Rodapé de Totais do Carrinho
        card_resumo_carrinho = ctk.CTkFrame(
            self.container_carrinho,
            corner_radius=8,
            fg_color=theme.INNER_CARD_BG,
            border_width=1,
            border_color=theme.BORDER_COLOR,
        )
        card_resumo_carrinho.pack(fill="x", pady=(0, 0))

        row_res_1 = ctk.CTkFrame(card_resumo_carrinho, fg_color="transparent")
        row_res_1.pack(fill="x", padx=12, pady=(8, 2))

        ctk.CTkLabel(
            row_res_1,
            text="TOTAL DO CARRINHO:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(side="left")

        self.lbl_carrinho_resumo = ctk.CTkLabel(
            row_res_1,
            text="0 itens",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_MUTED,
        )
        self.lbl_carrinho_resumo.pack(side="right")

        self.lbl_carrinho_total_destaque = ctk.CTkLabel(
            card_resumo_carrinho,
            text="R$ 0,00",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.PRICE_COLOR,
        )
        self.lbl_carrinho_total_destaque.pack(anchor="e", padx=12, pady=(0, 8))

        # --- CONTAINER 2: COMPROVANTE DA ÚLTIMA VENDA ---
        self.container_recibo = ctk.CTkFrame(recibo_card, fg_color="transparent")

        self.box_recibo = ctk.CTkFrame(self.container_recibo, fg_color=theme.INNER_CARD_BG, corner_radius=10, border_width=1, border_color=theme.BORDER_COLOR)
        self.box_recibo.pack(fill="both", expand=True, pady=(0, 10))

        self.lbl_recibo_detalhes = ctk.CTkLabel(
            self.box_recibo,
            text="Nenhuma venda finalizada nesta sessão ainda.\n\nAssim que você confirmar uma venda, os detalhes do cupom aparecerão aqui.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_MUTED,
            justify="center",
            wraplength=320,
        )
        self.lbl_recibo_detalhes.pack(expand=True, padx=14, pady=20)

        # Botão Imprimir Comprovante (para impressora térmica ou padrão)
        self.btn_imprimir = ctk.CTkButton(
            self.container_recibo,
            text="🖨️ Imprimir Comprovante",
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            state="disabled",
            command=self._imprimir_comprovante,
        )
        self.btn_imprimir.pack(fill="x")

    def _ao_bipar_codigo_barras(self, event=None):
        """Disparado quando o leitor óptico USB bipa e envia o código de barras + Enter."""
        cod = self.entry_bipar.get().strip()
        if not cod:
            return "break"

        prod_encontrado = None
        chave_combo = None

        # Procura no mapa em memória dos produtos disponíveis
        for k, p in self.mapa_produtos.items():
            if p.get("codigo_barras") and str(p["codigo_barras"]).strip() == cod:
                prod_encontrado = p
                chave_combo = k
                break

        # Se não encontrou no mapa em memória, busca diretamente no banco
        if not prod_encontrado:
            prod_db = db.obter_produto_por_codigo_barras(cod)
            if prod_db:
                if prod_db["estoque"] <= 0:
                    self._mostrar_feedback(f"Produto '{prod_db['nome']}' encontrado, mas o estoque está ESGOTADO.", sucesso=False)
                    self.entry_bipar.select_range(0, tk.END)
                    return "break"
                else:
                    self.recarregar_dados()
                    for k, p in self.mapa_produtos.items():
                        if p["id"] == prod_db["id"]:
                            prod_encontrado = p
                            chave_combo = k
                            break

        if prod_encontrado and chave_combo:
            self.combo_produtos.set(chave_combo)
            self._ao_selecionar_produto(chave_combo)
            # Garante que a quantidade para bipagem é no mínimo 1
            try:
                qtd_bip = int(self.entry_qtd.get().strip())
                if qtd_bip <= 0:
                    qtd_bip = 1
                    self._definir_qtd(1)
            except ValueError:
                qtd_bip = 1
                self._definir_qtd(1)

            # Inclusão automática no carrinho ao bipar com leitor de código de barras
            self._adicionar_ao_carrinho()
            self._mostrar_feedback(f"✔ Bipado e adicionado ao carrinho: {qtd_bip}x '{prod_encontrado['nome']}' ({formatar_moeda(prod_encontrado['preco'])})", sucesso=True)
            self.entry_bipar.delete(0, tk.END)
            self.entry_bipar.focus_set()
        else:
            self._mostrar_feedback(f"Código de barras '{cod}' não localizado.", sucesso=False)
            self.entry_bipar.select_range(0, tk.END)

        return "break"

    def _mostrar_feedback(self, msg: str, sucesso: bool = True):
        cor = theme.ACCENT_GREEN[1] if sucesso else theme.ACCENT_RED[1]
        self.lbl_feedback.configure(text=msg, text_color=cor)
        self.after(5000, lambda: self.lbl_feedback.configure(text=""))

    def _diminuir_qtd(self):
        try:
            val = int(self.entry_qtd.get().strip())
            if val > 1:
                self._definir_qtd(val - 1)
        except ValueError:
            self._definir_qtd(1)

    def _aumentar_qtd(self):
        try:
            val = int(self.entry_qtd.get().strip())
            if self.produto_selecionado and val >= self.produto_selecionado["estoque"]:
                self._mostrar_feedback(f"Estoque máximo disponível: {self.produto_selecionado['estoque']} un.", sucesso=False)
                return
            self._definir_qtd(val + 1)
        except ValueError:
            self._definir_qtd(1)

    def _definir_qtd(self, valor: int):
        self.entry_qtd.delete(0, tk.END)
        self.entry_qtd.insert(0, str(valor))
        self._atualizar_subtotal()

    def _somar_qtd(self, incremento: int):
        """Soma o valor pré-definido à quantidade já selecionada, respeitando o estoque máximo."""
        try:
            val = int(self.entry_qtd.get().strip())
        except ValueError:
            val = 0
        nova_qtd = max(1, val + incremento)
        if self.produto_selecionado and nova_qtd > self.produto_selecionado["estoque"]:
            self._mostrar_feedback(f"Estoque máximo disponível: {self.produto_selecionado['estoque']} un.", sucesso=False)
            nova_qtd = self.produto_selecionado["estoque"]
        self._definir_qtd(nova_qtd)

    def _ao_selecionar_produto(self, escolha: str):
        if escolha in self.mapa_produtos:
            self.produto_selecionado = self.mapa_produtos[escolha]
            preco = self.produto_selecionado["preco"]
            estoque = self.produto_selecionado["estoque"]

            self.lbl_preco.configure(text=formatar_moeda(preco))
            self.lbl_estoque.configure(
                text=f"{estoque} un",
                text_color=theme.STOCK_COLOR[1] if estoque > 5 else (theme.WARNING_COLOR[1] if estoque > 0 else theme.ACCENT_RED[1]),
            )
            self._atualizar_subtotal()
        else:
            self.produto_selecionado = None
            self.lbl_preco.configure(text="R$ 0,00")
            self.lbl_estoque.configure(text="0 un", text_color=theme.TEXT_SECONDARY)
            self.lbl_subtotal.configure(text="R$ 0,00")

    def _obter_total_carrinho(self) -> float:
        """Retorna o somatório financeiro dos itens no carrinho."""
        return round(sum(item["valor_total"] for item in self.carrinho), 2)

    def _obter_subtotal_atual(self) -> float:
        """Retorna o valor total ativo: total do carrinho (se houver itens) ou subtotal do item selecionado."""
        if self.carrinho:
            return self._obter_total_carrinho()
        if not self.produto_selecionado:
            return 0.0
        try:
            qtd = int(self.entry_qtd.get().strip())
            if qtd <= 0:
                return 0.0
            return round(qtd * self.produto_selecionado["preco"], 2)
        except ValueError:
            return 0.0

    def _ao_teclar_enter_qtd(self, event=None):
        """Ao pressionar Enter na quantidade, atualiza o subtotal e direciona foco para adicionar."""
        self._ao_alterar_quantidade()
        if hasattr(self, "btn_adicionar_carrinho"):
            self.btn_adicionar_carrinho.focus_set()
        return "break"

    def _adicionar_ao_carrinho(self):
        """Adiciona o produto selecionado com a quantidade especificada ao carrinho de compras."""
        if not self.produto_selecionado:
            self._mostrar_feedback("Selecione um produto para adicionar ao carrinho.", sucesso=False)
            return

        try:
            qtd = int(self.entry_qtd.get().strip())
            if qtd <= 0:
                raise ValueError
        except ValueError:
            self._mostrar_feedback("Informe uma quantidade válida maior que zero.", sucesso=False)
            return

        prod_id = self.produto_selecionado["id"]
        prod_nome = self.produto_selecionado["nome"]
        preco = self.produto_selecionado["preco"]
        estoque_disp = self.produto_selecionado["estoque"]

        # Verifica se o produto já se encontra no carrinho
        item_existente = None
        for item in self.carrinho:
            if item["produto_id"] == prod_id:
                item_existente = item
                break

        qtd_acumulada = (item_existente["quantidade"] if item_existente else 0) + qtd

        if qtd_acumulada > estoque_disp:
            self._mostrar_feedback(
                f"Estoque insuficiente para '{prod_nome}'. Disponível: {estoque_disp} un, Solicitado no total: {qtd_acumulada} un.",
                sucesso=False,
            )
            return

        if item_existente:
            item_existente["quantidade"] = qtd_acumulada
            item_existente["valor_total"] = round(qtd_acumulada * preco, 2)
        else:
            self.carrinho.append({
                "produto_id": prod_id,
                "produto_nome": prod_nome,
                "preco_unitario": preco,
                "quantidade": qtd,
                "valor_total": round(qtd * preco, 2),
                "estoque_max": estoque_disp,
                "codigo_barras": self.produto_selecionado.get("codigo_barras", ""),
            })

        self._renderizar_carrinho()
        self._alternar_aba_lateral("carrinho")
        self._atualizar_subtotal()
        self._mostrar_feedback(f"✔ Adicionado ao carrinho: {qtd}x '{prod_nome}'!", sucesso=True)

        # Reseta quantidade para 1
        self._definir_qtd(1)

        # Transfere foco para leitura do próximo código de barras
        if hasattr(self, "entry_bipar"):
            self.entry_bipar.focus_set()
            self.entry_bipar.delete(0, tk.END)

    def _remover_item_carrinho(self, index: int):
        """Remove um item específico do carrinho antes da confirmação da venda."""
        if 0 <= index < len(self.carrinho):
            removido = self.carrinho.pop(index)
            self._renderizar_carrinho()
            self._atualizar_subtotal()
            self._mostrar_feedback(f"Item '{removido['produto_nome']}' removido do carrinho.", sucesso=True)

    def _ajustar_qtd_carrinho(self, index: int, delta: int):
        """Altera a quantidade de um item no carrinho com validação atômica de estoque."""
        if 0 <= index < len(self.carrinho):
            item = self.carrinho[index]
            nova_qtd = item["quantidade"] + delta
            if nova_qtd <= 0:
                self._remover_item_carrinho(index)
                return

            prod_atual = db.obter_produto_por_id(item["produto_id"])
            est_max = prod_atual["estoque"] if prod_atual else item.get("estoque_max", 999)

            if nova_qtd > est_max:
                self._mostrar_feedback(
                    f"Estoque máximo de '{item['produto_nome']}': {est_max} un.",
                    sucesso=False,
                )
                return

            item["quantidade"] = nova_qtd
            item["valor_total"] = round(nova_qtd * item["preco_unitario"], 2)
            self._renderizar_carrinho()
            self._atualizar_subtotal()

    def _limpar_carrinho(self):
        """Esvazia todos os itens do carrinho de compras."""
        if not self.carrinho:
            return
        self.carrinho.clear()
        self._renderizar_carrinho()
        self._atualizar_subtotal()
        self._mostrar_feedback("Carrinho de compras esvaziado.", sucesso=True)

    def _alternar_aba_lateral(self, aba: str):
        """Alterna a exibição entre o Carrinho de Compras e o Comprovante da Última Venda."""
        self.modo_painel_direito = aba
        if aba == "carrinho":
            if hasattr(self, "container_recibo"):
                self.container_recibo.pack_forget()
            if hasattr(self, "container_carrinho"):
                self.container_carrinho.pack(fill="both", expand=True, padx=16, pady=(0, 16))
            if hasattr(self, "btn_tab_carrinho"):
                self.btn_tab_carrinho.configure(
                    fg_color=theme.ACCENT_BLUE,
                    hover_color=theme.ACCENT_BLUE_HOVER,
                    text_color="#FFFFFF",
                )
            if hasattr(self, "btn_tab_recibo"):
                self.btn_tab_recibo.configure(
                    fg_color=theme.INNER_CARD_BG,
                    hover_color=theme.BTN_SECONDARY_HOVER,
                    text_color=theme.TEXT_SECONDARY,
                )
        else:
            if hasattr(self, "container_carrinho"):
                self.container_carrinho.pack_forget()
            if hasattr(self, "container_recibo"):
                self.container_recibo.pack(fill="both", expand=True, padx=16, pady=(0, 16))
            if hasattr(self, "btn_tab_recibo"):
                self.btn_tab_recibo.configure(
                    fg_color=theme.ACCENT_BLUE,
                    hover_color=theme.ACCENT_BLUE_HOVER,
                    text_color="#FFFFFF",
                )
            if hasattr(self, "btn_tab_carrinho"):
                self.btn_tab_carrinho.configure(
                    fg_color=theme.INNER_CARD_BG,
                    hover_color=theme.BTN_SECONDARY_HOVER,
                    text_color=theme.TEXT_SECONDARY,
                )

    def _renderizar_carrinho(self):
        """Atualiza os itens e totais do carrinho na interface gráfica."""
        if not hasattr(self, "scroll_carrinho"):
            return

        for w in self.scroll_carrinho.winfo_children():
            w.destroy()

        qtd_total_itens = sum(it["quantidade"] for it in self.carrinho)
        total_reais = sum(it["valor_total"] for it in self.carrinho)

        if hasattr(self, "btn_tab_carrinho"):
            self.btn_tab_carrinho.configure(text=f"🛒 Carrinho ({len(self.carrinho)})")

        if not self.carrinho:
            card_vazio = ctk.CTkFrame(self.scroll_carrinho, fg_color="transparent")
            card_vazio.pack(expand=True, fill="both", pady=40)

            ctk.CTkLabel(card_vazio, text="🛒", font=ctk.CTkFont(size=36)).pack(pady=(0, 6))
            ctk.CTkLabel(
                card_vazio,
                text="O carrinho está vazio.\n\nAdicione itens usando o botão\n'+ Adicionar ao Carrinho (F4)'\nou bipe o código de barras.",
                font=ctk.CTkFont(size=12),
                text_color=theme.TEXT_MUTED,
                justify="center",
            ).pack()

            if hasattr(self, "lbl_carrinho_resumo"):
                self.lbl_carrinho_resumo.configure(text="0 itens")
            if hasattr(self, "lbl_carrinho_total_destaque"):
                self.lbl_carrinho_total_destaque.configure(text="R$ 0,00")
            if hasattr(self, "btn_limpar_carrinho"):
                self.btn_limpar_carrinho.configure(state="disabled")
            return

        if hasattr(self, "btn_limpar_carrinho"):
            self.btn_limpar_carrinho.configure(state="normal")

        for idx, item in enumerate(self.carrinho):
            card_item = ctk.CTkFrame(
                self.scroll_carrinho,
                fg_color=theme.CARD_BG,
                corner_radius=8,
                border_width=1,
                border_color=theme.BORDER_COLOR,
            )
            card_item.pack(fill="x", padx=4, pady=4)

            # Linha superior: Botão Excluir (sempre visível à direita) e Nome do Produto com quebra de linha
            row_top = ctk.CTkFrame(card_item, fg_color="transparent")
            row_top.pack(fill="x", padx=10, pady=(8, 2))

            # 1. Botão de Lixeira empacotado primeiro à direita para reservar espaço fixo e nunca ser ocultado
            btn_del = ctk.CTkButton(
                row_top,
                text="🗑",
                width=32,
                height=28,
                corner_radius=6,
                font=ctk.CTkFont(size=13),
                fg_color="#DC2626",
                hover_color="#B91C1C",
                text_color="#FFFFFF",
                command=lambda i=idx: self._remover_item_carrinho(i),
            )
            btn_del.pack(side="right", padx=(8, 0))

            # 2. Rótulo com o Nome do Produto (com quebra dinâmica de linha)
            lbl_nome = ctk.CTkLabel(
                row_top,
                text=item["produto_nome"],
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=theme.TEXT_PRIMARY,
                anchor="w",
                justify="left",
                wraplength=270,
            )
            lbl_nome.pack(side="left", fill="x", expand=True)

            # Linha inferior: Controles de quantidade e subtotal do item
            row_bottom = ctk.CTkFrame(card_item, fg_color="transparent")
            row_bottom.pack(fill="x", padx=10, pady=(2, 8))

            # Controles de quantidade: [-] Qtd [+]
            box_qtd = ctk.CTkFrame(row_bottom, fg_color="transparent")
            box_qtd.pack(side="left")

            btn_menos = ctk.CTkButton(
                box_qtd,
                text="-",
                width=24,
                height=24,
                corner_radius=4,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=theme.INNER_CARD_BG,
                hover_color=theme.BTN_SECONDARY_HOVER,
                text_color=theme.TEXT_PRIMARY,
                command=lambda i=idx: self._ajustar_qtd_carrinho(i, -1),
            )
            btn_menos.pack(side="left", padx=(0, 4))

            lbl_q = ctk.CTkLabel(
                box_qtd,
                text=f"{item['quantidade']} un",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.TEXT_PRIMARY,
                width=45,
            )
            lbl_q.pack(side="left")

            btn_mais = ctk.CTkButton(
                box_qtd,
                text="+",
                width=24,
                height=24,
                corner_radius=4,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=theme.INNER_CARD_BG,
                hover_color=theme.BTN_SECONDARY_HOVER,
                text_color=theme.TEXT_PRIMARY,
                command=lambda i=idx: self._ajustar_qtd_carrinho(i, 1),
            )
            btn_mais.pack(side="left", padx=(4, 8))

            # Preço unitário e subtotal do item
            lbl_precos = ctk.CTkLabel(
                row_bottom,
                text=f"{formatar_moeda(item['preco_unitario'])} → {formatar_moeda(item['valor_total'])}",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.PRICE_COLOR,
                anchor="e",
            )
            lbl_precos.pack(side="right")

        if hasattr(self, "lbl_carrinho_resumo"):
            self.lbl_carrinho_resumo.configure(text=f"{qtd_total_itens} peça(s)")
        if hasattr(self, "lbl_carrinho_total_destaque"):
            self.lbl_carrinho_total_destaque.configure(text=formatar_moeda(total_reais))

    def _converter_texto_para_float(self, texto: str) -> Optional[float]:
        limpo = texto.strip().replace("R$", "").replace(" ", "")
        if not limpo:
            return None
        try:
            if "," in limpo and "." in limpo:
                limpo = limpo.replace(".", "").replace(",", ".")
            else:
                limpo = limpo.replace(",", ".")
            return float(limpo)
        except ValueError:
            return None

    def _ao_digitar_recebido(self):
        """Quando o vendedor altera o valor que o cliente deu, calcula o troco final."""
        if getattr(self, "_sincronizando_troco", False):
            return
        self._sincronizando_troco = True
        try:
            if not hasattr(self, "entry_recebido") or not hasattr(self, "entry_troco"):
                return
            subtotal = self._obter_subtotal_atual()
            recebido = self._converter_texto_para_float(self.entry_recebido.get())

            if recebido is None:
                self.entry_troco.delete(0, tk.END)
                self.lbl_status_troco.configure(
                    text="Aguardando valor do cliente..." if subtotal > 0 else "Nenhum produto selecionado",
                    text_color=theme.TEXT_MUTED,
                )
                return

            if subtotal <= 0:
                self.entry_troco.delete(0, tk.END)
                self.entry_troco.insert(0, f"{recebido:.2f}".replace(".", ","))
                self.lbl_status_troco.configure(text="Selecione um produto para calcular o troco", text_color=theme.TEXT_MUTED)
                return

            troco = round(recebido - subtotal, 2)
            self.entry_troco.delete(0, tk.END)

            if troco >= 0:
                self.entry_troco.insert(0, f"{troco:.2f}".replace(".", ","))
                self.entry_troco.configure(text_color=theme.STOCK_COLOR[1])
                if troco == 0:
                    self.lbl_status_troco.configure(
                        text="✔ Pagamento exato (sem troco a devolver)",
                        text_color=theme.STOCK_COLOR[1],
                    )
                else:
                    self.lbl_status_troco.configure(
                        text=f"✔ Devolver {formatar_moeda(troco)} de troco ao cliente",
                        text_color=theme.STOCK_COLOR[1],
                    )
            else:
                falta = abs(troco)
                self.entry_troco.insert(0, f"-{falta:.2f}".replace(".", ","))
                self.entry_troco.configure(text_color=theme.ACCENT_RED[1])
                self.lbl_status_troco.configure(
                    text=f"⚠️ Falta {formatar_moeda(falta)} para o total de {formatar_moeda(subtotal)}",
                    text_color=theme.ACCENT_RED[1],
                )
        finally:
            self._sincronizando_troco = False

    def _ao_digitar_troco(self):
        """Quando o vendedor altera manualmente o troco final, ajusta o valor entregue."""
        if getattr(self, "_sincronizando_troco", False):
            return
        self._sincronizando_troco = True
        try:
            if not hasattr(self, "entry_recebido") or not hasattr(self, "entry_troco"):
                return
            subtotal = self._obter_subtotal_atual()
            troco = self._converter_texto_para_float(self.entry_troco.get())

            if troco is None:
                self.lbl_status_troco.configure(text="Informe o troco ou o valor recebido", text_color=theme.TEXT_MUTED)
                return

            novo_recebido = max(0.0, round(subtotal + troco, 2))
            self.entry_recebido.delete(0, tk.END)
            self.entry_recebido.insert(0, f"{novo_recebido:.2f}".replace(".", ","))

            if troco >= 0:
                self.entry_troco.configure(text_color=theme.STOCK_COLOR[1])
                self.lbl_status_troco.configure(
                    text=f"✔ Troco definido: {formatar_moeda(troco)} (Cliente entregou {formatar_moeda(novo_recebido)})",
                    text_color=theme.STOCK_COLOR[1],
                )
            else:
                self.entry_troco.configure(text_color=theme.ACCENT_RED[1])
                self.lbl_status_troco.configure(
                    text=f"⚠️ Troco negativo ({formatar_moeda(troco)})",
                    text_color=theme.ACCENT_RED[1],
                )
        finally:
            self._sincronizando_troco = False

    def _definir_valor_recebido(self, valor: float):
        """Preenche o campo de valor recebido com uma cédula ou valor pré-determinado."""
        if hasattr(self, "entry_recebido"):
            self.entry_recebido.delete(0, tk.END)
            self.entry_recebido.insert(0, f"{valor:.2f}".replace(".", ","))
            self._ao_digitar_recebido()

    def _definir_valor_recebido_exato(self):
        """Define o valor recebido exatamente igual ao subtotal da venda."""
        subtotal = self._obter_subtotal_atual()
        if subtotal > 0 and hasattr(self, "entry_recebido"):
            self.entry_recebido.delete(0, tk.END)
            self.entry_recebido.insert(0, f"{subtotal:.2f}".replace(".", ","))
            self._ao_digitar_recebido()

    def _ao_digitar_cpf(self, event=None):
        """Formata e mascara o CPF do consumidor em tempo real (000.000.000-00)."""
        if not hasattr(self, "entry_cpf"):
            return
        texto = self.entry_cpf.get()
        import re
        nums = re.sub(r"\D", "", texto)[:11]

        if len(nums) <= 3:
            formatado = nums
        elif len(nums) <= 6:
            formatado = f"{nums[:3]}.{nums[3:]}"
        elif len(nums) <= 9:
            formatado = f"{nums[:3]}.{nums[3:6]}.{nums[6:]}"
        else:
            formatado = f"{nums[:3]}.{nums[3:6]}.{nums[6:9]}-{nums[9:]}"

        if formatado != texto:
            self.entry_cpf.delete(0, tk.END)
            self.entry_cpf.insert(0, formatado)

    def _limpar_cpf(self):
        """Limpa o campo de CPF do consumidor."""
        if hasattr(self, "entry_cpf"):
            self.entry_cpf.delete(0, tk.END)

    def _abrir_excel_rapido(self):
        """Abre a planilha Excel do dia diretamente pelo PDV com auto-geração imediata se necessário."""
        from datetime import datetime
        hoje_iso = datetime.now().strftime("%Y-%m-%d")

        # 1. Se houver vendas ou cancelamentos hoje, regenera/atualiza o Excel do dia para garantir dados em tempo real
        try:
            resumo = db.obter_resumo_dia()
            canc = db.obter_vendas_canceladas_dia(hoje_iso)
            if (resumo and resumo.get("total_vendas", 0) > 0) or canc:
                reports.gerar_relatorio_diario_excel(data_str=hoje_iso)
        except Exception as e_gen:
            print(f"Aviso ao sincronizar Excel diário: {e_gen}")

        # 2. Localiza o relatório mais recente gerado
        caminho = reports.obter_ultimo_relatorio_excel_gerado()

        tem_senha = db.existe_senha_admin()
        dica_senha = "sua Senha de Administrador personalizada" if tem_senha else "a Senha Padrão ('Central@2026')"

        if not caminho or not os.path.exists(caminho):
            messagebox.showinfo(
                "Planilha Diária Excel",
                "Ainda não há vendas ou movimentações registradas hoje para gerar o relatório diário.\n\n"
                "Ao realizar a primeira venda do dia ou ao fechar o caixa, a planilha será gerada e atualizada automaticamente.",
            )
            return

        nome_arq = os.path.basename(caminho)

        # 3. Tenta abrir a planilha no programa padrão (Excel / LibreOffice)
        sucesso, msg = reports.abrir_arquivo_planilha(caminho)

        if sucesso:
            self._mostrar_feedback(f"✔ Planilha '{nome_arq}' aberta! Senha: {dica_senha}", sucesso=True)
            messagebox.showinfo(
                "Planilha Aberta com Sucesso",
                f"A planilha mais recente foi enviada ao Microsoft Excel / LibreOffice:\n\n"
                f"📄 Arquivo: {nome_arq}\n\n"
                f"🔒 SENHA PARA DESBLOQUEAR O ARQUIVO NO EXCEL:\n"
                f"👉 {dica_senha}\n\n"
                f"Caso o programa abra em segundo plano, clique no ícone do Excel na barra de tarefas do Windows para visualizá-lo.",
            )
        else:
            # Fallback com abertura da pasta no Explorer
            try:
                subprocess.Popen(f'explorer /select,"{os.path.abspath(caminho)}"')
                self._mostrar_feedback(f"📁 Pasta aberta com a planilha '{nome_arq}' selecionada! Senha: {dica_senha}", sucesso=True)
                messagebox.showinfo(
                    "Pasta da Planilha Aberta",
                    f"A pasta foi aberta no Windows Explorer com o relatório selecionado:\n\n"
                    f"📄 Arquivo: {nome_arq}\n\n"
                    f"🔒 SENHA PARA DESBLOQUEAR:\n"
                    f"👉 {dica_senha}",
                )
            except Exception as e_exp:
                messagebox.showerror(
                    "Erro ao Abrir Planilha",
                    f"Não foi possível abrir o arquivo ou a pasta:\n{msg}\n{e_exp}",
                )

    def _abrir_modal_busca_estoque(self):
        """Abre o modal avançado de busca no estoque com filtro em tempo real (F3)."""
        ProductSearchModal(self, on_select_callback=self._selecionar_produto_da_busca)

    def _selecionar_produto_da_busca(self, produto: Dict[str, Any]):
        """Callback acionado ao selecionar um item no modal de busca rápida de estoque."""
        if not produto:
            return
        self.recarregar_dados()
        chave_combo = None
        for k, p in self.mapa_produtos.items():
            if p["id"] == produto["id"]:
                chave_combo = k
                break

        if hasattr(self, "entry_busca_produto"):
            self.entry_busca_produto.delete(0, tk.END)
            self.entry_busca_produto.insert(0, produto["nome"])
            if hasattr(self, "lbl_busca_contador"):
                self.lbl_busca_contador.configure(text="(Item selecionado)")

        if chave_combo:
            self.combo_produtos.set(chave_combo)
            self._ao_selecionar_produto(chave_combo)
        else:
            self.produto_selecionado = produto
            self.lbl_preco.configure(text=formatar_moeda(produto.get("preco", 0.0)))
            self.lbl_estoque.configure(text=f"{produto.get('estoque', 0)} un")
            self._atualizar_subtotal()

        self.entry_qtd.focus_set()
        self.entry_qtd.select_range(0, tk.END)

    def _ao_digitar_busca_produto(self, event=None):
        """Debounce ágil para busca fluida de produtos no PDV."""
        if hasattr(self, "_debounce_timer") and self._debounce_timer:
            self.after_cancel(self._debounce_timer)
        self._debounce_timer = self.after(120, self._executar_busca_produto)

    def _executar_busca_produto(self):
        """Filtra os produtos disponíveis em tempo real com correspondência por frase e tokens inteligentes."""
        if hasattr(self, "_debounce_timer") and self._debounce_timer:
            self.after_cancel(self._debounce_timer)
            self._debounce_timer = None

        if not hasattr(self, "entry_busca_produto"):
            return

        termo = self.entry_busca_produto.get().strip().lower()

        if not termo:
            opcoes = list(self.mapa_produtos.keys())
            if opcoes:
                self.combo_produtos.configure(values=opcoes)
                if hasattr(self, "lbl_busca_contador"):
                    self.lbl_busca_contador.configure(text=f"({len(opcoes)} disponíveis)")
                if self.produto_selecionado:
                    for k, p in self.mapa_produtos.items():
                        if p["id"] == self.produto_selecionado["id"]:
                            self.combo_produtos.set(k)
                            break
                else:
                    self.combo_produtos.set(opcoes[0])
                    self._ao_selecionar_produto(opcoes[0])
                self.btn_confirmar.configure(state="normal")
            return

        termo_limpo = re.sub(r"[^\w\s]", " ", termo)
        tokens = [t for t in termo_limpo.split() if t]
        opcoes_filtradas = []
        frase = " ".join(tokens)

        for k, p in self.mapa_produtos.items():
            texto_completo = f"{p['nome']} {p.get('codigo_barras') or ''} {p.get('categoria') or ''}".lower()
            texto_limpo = re.sub(r"[^\w\s]", " ", texto_completo)

            # 1. Correspondência por frase completa
            if frase in texto_limpo:
                opcoes_filtradas.append(k)
                continue

            # 2. Correspondência inteligente por tokens
            match_all = True
            for t in tokens:
                if len(t) <= 2:
                    if not re.search(rf"\b{re.escape(t)}\b", texto_limpo):
                        match_all = False
                        break
                else:
                    if t not in texto_limpo:
                        match_all = False
                        break
            if match_all:
                opcoes_filtradas.append(k)

        if opcoes_filtradas:
            self.combo_produtos.configure(values=opcoes_filtradas)
            self.combo_produtos.set(opcoes_filtradas[0])
            self._ao_selecionar_produto(opcoes_filtradas[0])
            if hasattr(self, "lbl_busca_contador"):
                self.lbl_busca_contador.configure(text=f"({len(opcoes_filtradas)} encontrado(s))")
            self.btn_confirmar.configure(state="normal")
        else:
            self.combo_produtos.configure(values=["Nenhum produto correspondente"])
            self.combo_produtos.set("Nenhum produto correspondente")
            if hasattr(self, "lbl_busca_contador"):
                self.lbl_busca_contador.configure(text="(0 encontrado)")
            self.produto_selecionado = None
            self.lbl_preco.configure(text="R$ 0,00")
            self.lbl_estoque.configure(text="0 un", text_color=theme.ACCENT_RED[1])
            self.lbl_subtotal.configure(text="R$ 0,00")
            self.btn_confirmar.configure(state="disabled")

    def _ao_confirmar_busca_produto(self, event=None):
        """Ao teclar Enter no campo de busca, aplica a busca imediatamente e foca na quantidade."""
        self._executar_busca_produto()
        if hasattr(self, "entry_qtd"):
            self.entry_qtd.focus_set()
            self.entry_qtd.select_range(0, tk.END)
        return "break"

    def _limpar_busca_produto(self):
        """Limpa o campo de pesquisa e reexibe todos os produtos em estoque."""
        if hasattr(self, "entry_busca_produto"):
            self.entry_busca_produto.delete(0, tk.END)
            self._ao_digitar_busca_produto()
            self.entry_busca_produto.focus_set()

    def _selecionar_forma_pagamento(self, cod: str):
        """Alterna a forma de pagamento ativa da venda."""
        self.forma_pagamento_selecionada = cod
        for c, btn in self.botoes_pgto.items():
            if c == cod:
                btn.configure(fg_color=theme.ACCENT_BLUE, text_color="#FFFFFF")
            else:
                btn.configure(fg_color=theme.INNER_CARD_BG, text_color=theme.TEXT_SECONDARY)

        sub = self._obter_subtotal_atual()
        if cod == "DINHEIRO":
            if hasattr(self, "card_digital"):
                self.card_digital.pack_forget()
            if hasattr(self, "card_troco"):
                self.card_troco.pack(fill="x")
            self._ao_digitar_recebido()
        else:
            if hasattr(self, "card_troco"):
                self.card_troco.pack_forget()
            if hasattr(self, "card_digital"):
                self.card_digital.pack(fill="x")

            if cod == "PIX":
                self.lbl_digital_titulo.configure(text="📱 Pagamento Instantâneo Pix")
                self.lbl_digital_info.configure(
                    text=f"Aguardando confirmação Pix ({formatar_moeda(sub)}) • Valor exato sem troco.",
                    text_color=theme.STOCK_COLOR[1],
                )
                if hasattr(self, "frame_campos_cartao"):
                    self.frame_campos_cartao.pack_forget()
            elif cod in ("CARTAO_DEBITO", "CARTAO_CREDITO"):
                tipo_txt = "Débito" if cod == "CARTAO_DEBITO" else "Crédito"
                self.lbl_digital_titulo.configure(text=f"💳 Cartão de {tipo_txt} (Maquininha POS / TEF)")
                self.lbl_digital_info.configure(
                    text=f"Insira ou aproxime o cartão na maquininha ({formatar_moeda(sub)}) • Sem troco.",
                    text_color=theme.ACCENT_BLUE[1] if isinstance(theme.ACCENT_BLUE, tuple) else theme.ACCENT_BLUE,
                )
                if hasattr(self, "frame_campos_cartao"):
                    self.frame_campos_cartao.pack(fill="x", padx=16, pady=(0, 16))

            if hasattr(self, "entry_recebido"):
                self.entry_recebido.delete(0, tk.END)
                if sub > 0:
                    self.entry_recebido.insert(0, f"{sub:.2f}".replace(".", ","))
            if hasattr(self, "entry_troco"):
                self.entry_troco.delete(0, tk.END)
                self.entry_troco.insert(0, "0,00")

    def _abrir_modal_fechamento_caixa(self):
        """Abre o modal de conferência e fechamento oficial do caixa com geração de planilha."""
        def _apos_fechamento():
            self.recarregar_dados()
            if self.on_cash_closed_callback:
                try:
                    self.on_cash_closed_callback()
                except Exception:
                    pass

        CashClosureModal(self, on_fechamento_concluido=_apos_fechamento)

    def _limpar_troco(self):
        """Limpa os campos de troco e valor recebido."""
        if hasattr(self, "entry_recebido"):
            self.entry_recebido.delete(0, tk.END)
        if hasattr(self, "entry_troco"):
            self.entry_troco.delete(0, tk.END)
        if hasattr(self, "lbl_status_troco"):
            self.lbl_status_troco.configure(text="Aguardando valor do cliente...", text_color=theme.TEXT_MUTED)

    def _atualizar_subtotal(self):
        if self.carrinho:
            total_carrinho = self._obter_total_carrinho()
            total_pecas = sum(it["quantidade"] for it in self.carrinho)
            if hasattr(self, "lbl_subtotal_titulo"):
                self.lbl_subtotal_titulo.configure(text=f"TOTAL DO CARRINHO ({total_pecas} ITENS)")
            if hasattr(self, "lbl_subtotal"):
                self.lbl_subtotal.configure(text=formatar_moeda(total_carrinho))
            if hasattr(self, "btn_confirmar"):
                self.btn_confirmar.configure(
                    text=f"✔ FINALIZAR CARRINHO ({formatar_moeda(total_carrinho)}) (F2)",
                    state="normal",
                )
        else:
            sub = self._obter_subtotal_atual()
            if hasattr(self, "lbl_subtotal_titulo"):
                self.lbl_subtotal_titulo.configure(text="SUBTOTAL DA VENDA")
            if hasattr(self, "lbl_subtotal"):
                self.lbl_subtotal.configure(text=formatar_moeda(sub))
            if hasattr(self, "btn_confirmar"):
                self.btn_confirmar.configure(text="✔ CONFIRMAR VENDA (F2)")

        if hasattr(self, "entry_recebido"):
            self._ao_digitar_recebido()

    def recarregar_dados(self):
        """Atualiza a lista de produtos disponíveis para venda."""
        self._necessita_recarregar = False
        todos = db.listar_produtos()
        self.produtos_disponiveis = [p for p in todos if p["estoque"] > 0]
        self.mapa_produtos.clear()

        opcoes = []
        for p in self.produtos_disponiveis:
            cod_txt = f" [{p['codigo_barras']}]" if p.get("codigo_barras") else ""
            chave = f"{p['nome']}{cod_txt} (Estoque: {p['estoque']} | {formatar_moeda(p['preco'])})"
            self.mapa_produtos[chave] = p
            opcoes.append(chave)

        # Se houver busca em andamento no campo, reaplica o filtro
        if hasattr(self, "entry_busca_produto") and self.entry_busca_produto.get().strip():
            self._ao_digitar_busca_produto()
            return

        if opcoes:
            self.combo_produtos.configure(values=opcoes)
            if hasattr(self, "lbl_busca_contador"):
                self.lbl_busca_contador.configure(text=f"({len(opcoes)} disponíveis)")
            if self.produto_selecionado:
                novo_selecionado = None
                for k, p in self.mapa_produtos.items():
                    if p["id"] == self.produto_selecionado["id"]:
                        novo_selecionado = k
                        break
                if novo_selecionado:
                    self.combo_produtos.set(novo_selecionado)
                    self._ao_selecionar_produto(novo_selecionado)
                else:
                    self.combo_produtos.set(opcoes[0])
                    self._ao_selecionar_produto(opcoes[0])
            else:
                self.combo_produtos.set(opcoes[0])
                self._ao_selecionar_produto(opcoes[0])
            self.btn_confirmar.configure(state="normal")
        else:
            self.combo_produtos.configure(values=["Nenhum produto disponível"])
            self.combo_produtos.set("Nenhum produto disponível")
            if hasattr(self, "lbl_busca_contador"):
                self.lbl_busca_contador.configure(text="(Estoque vazio)")
            self.produto_selecionado = None
            self.lbl_preco.configure(text="R$ 0,00")
            self.lbl_estoque.configure(text="0 un", text_color=theme.ACCENT_RED[1])
            self.lbl_subtotal.configure(text="R$ 0,00")
            self.btn_confirmar.configure(state="disabled")

        # Se houver vendas recentes hoje e o comprovante estiver vazio, carrega a última
        if not self.ultima_venda_info and hasattr(self, "btn_imprimir"):
            try:
                recentes = db.obter_vendas_recentes_do_dia(limite=1)
                if recentes and recentes[0].get("status") != "CANCELADA":
                    v = recentes[0]
                    p_atual = db.obter_produto_por_id(v.get("produto_id", 0))
                    est_atual = p_atual["estoque"] if p_atual else 0
                    self.ultima_venda_info = {
                        "venda_id": v["id"],
                        "produto_id": v.get("produto_id", 0),
                        "produto_nome": v["produto_nome"],
                        "quantidade": v["quantidade"],
                        "preco_unitario": v["preco_unitario"],
                        "valor_total": v["valor_total"],
                        "data_hora": v["data_hora"],
                        "estoque_restante": est_atual,
                    }
                    self._atualizar_comprovante(self.ultima_venda_info)
            except Exception:
                pass

    def confirmar_venda_atalho(self, event=None):
        """Dispara a confirmação da venda via atalho de teclado (F2 ou Enter)."""
        if self.btn_confirmar.cget("state") != "disabled":
            self._confirmar_venda()
        return "break"

    def _confirmar_venda(self):
        """Valida a venda atual e abre o PaymentModal para definir forma de pagamento e CPF."""
        if getattr(self, "_processando_venda", False):
            return

        if self.carrinho:
            itens_venda = list(self.carrinho)
            total_venda = self._obter_total_carrinho()
        else:
            if not self.produto_selecionado:
                self._mostrar_feedback("Nenhum produto selecionado ou no carrinho para venda.", sucesso=False)
                return

            qtd_str = self.entry_qtd.get().strip()
            try:
                qtd = int(qtd_str)
                if qtd <= 0:
                    raise ValueError
            except ValueError:
                self._mostrar_feedback("Informe uma quantidade válida maior que zero.", sucesso=False)
                return

            estoque_disp = self.produto_selecionado.get("estoque", 0)
            if qtd > estoque_disp:
                self._mostrar_feedback(
                    f"Quantidade solicitada ({qtd}) maior que o estoque disponível ({estoque_disp} un).",
                    sucesso=False,
                )
                return

            preco_unit = float(self.produto_selecionado.get("preco", 0.0))
            total_venda = round(qtd * preco_unit, 2)
            itens_venda = [{
                "produto_id": self.produto_selecionado["id"],
                "produto_nome": self.produto_selecionado["nome"],
                "quantidade": qtd,
                "preco_unitario": preco_unit,
                "valor_total": total_venda,
            }]

        if total_venda <= 0:
            self._mostrar_feedback("O valor total da venda deve ser maior que zero.", sucesso=False)
            return

        # Abre a Janela Modal de Pagamento & Conclusão (F2)
        PaymentModal(
            parent=self,
            valor_total=total_venda,
            itens=itens_venda,
            on_confirm_callback=self._concluir_venda_apos_pagamento,
        )

    def _concluir_venda_apos_pagamento(self, dados_pgto: dict):
        """Callback acionado após o operador definir a forma de pagamento e confirmar (F2) no PaymentModal."""
        if getattr(self, "_processando_venda", False):
            return
        self._processando_venda = True
        try:
            forma_pgto = dados_pgto.get("forma_pagamento", "DINHEIRO")
            val_recebido = dados_pgto.get("valor_recebido", 0.0)
            troco_val = dados_pgto.get("troco", 0.0)
            bandeira = dados_pgto.get("bandeira", "Mastercard")
            nsu = dados_pgto.get("nsu", "")
            cpf_formatado = dados_pgto.get("cpf_cliente", "")
            cpf_nums = dados_pgto.get("cpf_nums", "")

            eh_carrinho = bool(self.carrinho)

            if eh_carrinho:
                sucesso, msg, info_venda = db.registrar_venda_carrinho(
                    self.carrinho,
                    forma_pagamento=forma_pgto,
                    cpf_cliente=cpf_formatado,
                )
            else:
                if not self.produto_selecionado:
                    self._mostrar_feedback("Nenhum produto selecionado para venda.", sucesso=False)
                    return

                qtd_str = self.entry_qtd.get().strip()
                try:
                    qtd = int(qtd_str)
                    if qtd <= 0:
                        raise ValueError
                except ValueError:
                    self._mostrar_feedback("Informe uma quantidade válida maior que zero.", sucesso=False)
                    return

                sucesso, msg, info_venda = db.registrar_venda(
                    self.produto_selecionado["id"],
                    qtd,
                    forma_pagamento=forma_pgto,
                    cpf_cliente=cpf_formatado,
                )

            if sucesso and info_venda:
                # Preenche informações financeiras completas para o comprovante
                info_venda["forma_pagamento"] = forma_pgto
                info_venda["valor_recebido"] = val_recebido
                info_venda["troco"] = troco_val
                info_venda["bandeira"] = bandeira
                info_venda["nsu"] = nsu
                info_venda["cpf_cliente"] = cpf_formatado

                # Processamento Fiscal (respeita modo Não-Fiscal vs Fiscal NFC-e com contingência e CPF na nota)
                try:
                    from fiscal.fiscal_service import FiscalService
                    f_svc = FiscalService()
                    mapa_acbr = {
                        "DINHEIRO": "01",
                        "PIX": "17",
                        "CARTAO_DEBITO": "04",
                        "CARTAO_CREDITO": "03",
                    }
                    itens_fiscal = info_venda.get("itens") if info_venda.get("itens") else [info_venda]
                    v_id_ref = info_venda.get("venda_id") or (info_venda.get("vendas_ids")[0] if info_venda.get("vendas_ids") else 0)
                    res_fiscal = f_svc.emitir_venda_pdv(
                        venda_id=v_id_ref,
                        itens=itens_fiscal,
                        valor_total=info_venda["valor_total"],
                        forma_pagamento=mapa_acbr.get(forma_pgto, "01"),
                        troco=troco_val,
                        valor_recebido=val_recebido,
                        cpf_consumidor=cpf_nums,
                    )
                    info_venda["fiscal"] = res_fiscal
                    if res_fiscal.get("contingencia"):
                        msg += "\n⚠️ NFC-e gerada em CONTINGÊNCIA OFFLINE (Sincronização em segundo plano)."
                except Exception as ef:
                    print(f"Erro na camada fiscal: {ef}")

                # ATUALIZAÇÃO AUTOMÁTICA DA PLANILHA EXCEL DO DIA
                try:
                    reports.gerar_relatorio_diario_excel()
                except Exception as e_excel:
                    print(f"Aviso ao sincronizar Excel diário após venda: {e_excel}")

                if eh_carrinho:
                    self.carrinho.clear()
                    self._renderizar_carrinho()

                self.ultima_venda_info = info_venda
                self._mostrar_feedback(msg, sucesso=True)
                self._atualizar_comprovante(info_venda)
                self._alternar_aba_lateral("recibo")
                self._definir_qtd(1)
                self.recarregar_dados()

                if self.on_sale_completed_callback:
                    self.on_sale_completed_callback()

                # Volta foco para o leitor de código de barras para o próximo item
                self.entry_bipar.focus_set()
                self.entry_bipar.select_range(0, tk.END)
            else:
                self._mostrar_feedback(msg, sucesso=False)
        finally:
            self.after(300, lambda: setattr(self, "_processando_venda", False))

    def _atualizar_comprovante(self, info: dict):
        forma = info.get("forma_pagamento", "DINHEIRO")
        if forma == "DINHEIRO":
            bloco_financeiro = (
                f"Forma: DINHEIRO FÍSICO\n"
                f"TOTAL PAGO: {formatar_moeda(info['valor_total'])}\n"
            )
            if info.get("valor_recebido", 0) > 0:
                bloco_financeiro += (
                    f"Valor Recebido: {formatar_moeda(info['valor_recebido'])}\n"
                    f"Troco Devolvido: {formatar_moeda(info.get('troco', 0.0))}\n"
                )
        elif forma == "PIX":
            bloco_financeiro = (
                f"Forma: PIX INSTANTÂNEO\n"
                f"TOTAL PAGO: {formatar_moeda(info['valor_total'])}\n"
                f"Status: Confirmado (Sem Troco)\n"
            )
        elif forma in ("CARTAO_DEBITO", "CARTAO_CREDITO"):
            tipo_c = "DÉBITO" if forma == "CARTAO_DEBITO" else "CRÉDITO"
            band = info.get("bandeira", "Mastercard")
            nsu = info.get("nsu", "")
            bloco_financeiro = (
                f"Forma: CARTÃO DE {tipo_c}\n"
                f"Bandeira: {band}\n"
            )
            if nsu:
                bloco_financeiro += f"Aut/NSU: {nsu}\n"
            bloco_financeiro += (
                f"TOTAL PAGO: {formatar_moeda(info['valor_total'])}\n"
                f"Status: Aprovado na Maquininha\n"
            )
        else:
            bloco_financeiro = f"TOTAL PAGO: {formatar_moeda(info['valor_total'])}\n"

        f_info = info.get("fiscal", {})
        eh_modo_fiscal = (f_info.get("modo") == "FISCAL_NFCE")
        eh_autorizada = eh_modo_fiscal and f_info.get("sucesso") and (f_info.get("status") == "AUTORIZADA")
        eh_contingencia = eh_modo_fiscal and f_info.get("contingencia", False)

        if eh_modo_fiscal:
            if eh_autorizada:
                header_txt = (
                    "*** CUPOM FISCAL ELETRÔNICO (NFC-e) ***\n\n"
                    f"NFC-e nº: {f_info.get('numero_nfce', '-')}\n"
                    f"Protocolo: {f_info.get('protocolo', '-')}\n"
                    f"Chave: {f_info.get('chave', '')[:28]}..."
                )
                footer_txt = "Autorizado o uso da NF-e pela SEFAZ"
                cor_recibo = theme.PRICE_COLOR[1]
            elif eh_contingencia:
                header_txt = (
                    "*** NFC-e EMITIDA EM CONTINGÊNCIA ***\n"
                    "*** PENDENTE DE AUTORIZAÇÃO SEFAZ ***\n\n"
                    f"NFC-e nº: {f_info.get('numero_nfce', '-')}\n"
                    f"Chave: {f_info.get('chave', '')[:28]}..."
                )
                footer_txt = "EMITIDA EM CONTINGÊNCIA - Pendente de sincronização"
                cor_recibo = theme.WARNING_COLOR[1]
            else:
                motivo = f_info.get("mensagem") or "Configuração fiscal incompleta"
                header_txt = (
                    "*** COMPROVANTE NÃO FISCAL (CONTROLE INTERNO) ***\n\n"
                    f"⚠️ Aviso Fiscal: {motivo}"
                )
                footer_txt = "Documento sem valor fiscal - Controle Interno"
                cor_recibo = theme.WARNING_COLOR[1]
        else:
            header_txt = "*** COMPROVANTE NÃO FISCAL - CONTROLE INTERNO ***\n"
            footer_txt = "Documento sem valor fiscal - Controle Interno"
            cor_recibo = theme.ACCENT_GREEN[1]

        itens = info.get("itens")
        if itens:
            linhas_itens = ["ITENS DA VENDA:"]
            for idx_it, it in enumerate(itens, 1):
                linhas_itens.append(f"{idx_it}. {it['produto_nome']}")
                linhas_itens.append(f"   {it['quantidade']} un x {formatar_moeda(it['preco_unitario'])} = {formatar_moeda(it['valor_total'])}")
            bloco_itens = "\n".join(linhas_itens)
            v_ids = info.get("vendas_ids", [])
            id_txt = f"Venda ID: #{v_ids[0]} a #{v_ids[-1]}" if len(v_ids) > 1 else (f"Venda ID: #{v_ids[0]}" if v_ids else "Venda ID: -")
        else:
            bloco_itens = (
                f"Item: {info.get('produto_nome', '')}\n"
                f"Quantidade: {info.get('quantidade', 1)} un\n"
                f"Preço Unitário: {formatar_moeda(info.get('preco_unitario', 0.0))}"
            )
            id_txt = f"Venda ID: #{info.get('venda_id', '-')}"

        cpf_txt = f"Consumidor CPF: {info['cpf_cliente']}\n" if info.get("cpf_cliente") else "Consumidor: Não identificado\n"

        texto = (
            f"{header_txt}\n"
            f"{id_txt}\n"
            f"Horário: {info['data_hora']}\n"
            f"{cpf_txt}"
            "----------------------------------------\n"
            f"{bloco_itens}\n"
            "----------------------------------------\n"
            f"{bloco_financeiro}"
            "----------------------------------------\n"
            f"{footer_txt}"
        )
        self.lbl_recibo_detalhes.configure(
            text=texto,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=cor_recibo,
            justify="left",
        )
        if hasattr(self, "btn_imprimir"):
            self.btn_imprimir.configure(
                state="normal",
                fg_color=theme.ACCENT_BLUE,
                hover_color=theme.ACCENT_BLUE_HOVER,
                text_color=theme.ACCENT_BLUE_TEXT,
            )

    def _imprimir_comprovante(self):
        """
        Imprime o comprovante da última venda com suporte inteligente a ambos os modos:
        - Modo Fiscal: Cupom Fiscal Eletrônico (DANFE NFC-e) completo com dados tributários e SEFAZ.
        - Modo Não-Fiscal: Comprovante de Venda / Controle Interno Gerencial.
        Compatível com impressoras térmicas (58mm/80mm), impressoras padrão e sem travamentos.
        """
        if not self.ultima_venda_info:
            messagebox.showinfo("Aviso", "Nenhuma venda foi finalizada para imprimir comprovante.")
            return

        info = self.ultima_venda_info
        largura = 40
        div = "-" * largura
        div_dupla = "=" * largura

        f_info = info.get("fiscal", {})
        eh_modo_fiscal = (f_info.get("modo") == "FISCAL_NFCE")
        eh_autorizada = eh_modo_fiscal and f_info.get("sucesso") and (f_info.get("status") == "AUTORIZADA")
        eh_contingencia = eh_modo_fiscal and f_info.get("contingencia", False)

        itens = info.get("itens")
        if itens:
            v_ids = info.get("vendas_ids", [])
            id_txt = f"Venda ID : #{v_ids[0]} a #{v_ids[-1]}" if len(v_ids) > 1 else (f"Venda ID : #{v_ids[0]}" if v_ids else "Venda ID : -")
        else:
            id_txt = f"Venda ID : #{info.get('venda_id', '-')}"

        cpf_cliente = info.get("cpf_cliente", "").strip()
        cpf_cupom = f"Consumidor CPF: {cpf_cliente}" if cpf_cliente else "Consumidor: Não identificado"

        linhas = [div_dupla]

        if eh_modo_fiscal and (eh_autorizada or eh_contingencia):
            # -------------------------------------------------------------
            # CUPOM FISCAL ELETRÔNICO (DANFE NFC-e)
            # -------------------------------------------------------------
            cfg_fiscal = db.obter_configuracoes_fiscais()
            empresa_nome = cfg_fiscal.get("nome_fantasia") or cfg_fiscal.get("razao_social") or "CENTRAL DE VENDAS"
            cnpj_empresa = cfg_fiscal.get("cnpj", "")
            ie_empresa = cfg_fiscal.get("ie", "")

            linhas.extend([
                empresa_nome[:largura].center(largura),
                "DOCUMENTO AUXILIAR DA NOTA FISCAL DE".center(largura),
                "CONSUMIDOR ELETRONICA - DANFE NFC-e".center(largura),
                div_dupla,
            ])
            if cnpj_empresa:
                linhas.append(f"CNPJ: {cnpj_empresa}")
            if ie_empresa:
                linhas.append(f"Inscricao Estadual: {ie_empresa}")

            n_nfce = f_info.get("numero_nfce", 0)
            serie_nfce = cfg_fiscal.get("serie", 1)
            linhas.extend([
                div,
                f"NFC-e n : {n_nfce:09d}  Serie: {serie_nfce}",
                f"Emissao : {info['data_hora']}",
                cpf_cupom,
                div,
            ])
        else:
            # -------------------------------------------------------------
            # COMPROVANTE NÃO-FISCAL (CONTROLE INTERNO)
            # -------------------------------------------------------------
            linhas.extend([
                "CENTRAL DE VENDAS".center(largura),
                "CONTROLE INTERNO / GERENCIAL".center(largura),
                div_dupla,
                "*** COMPROVANTE NÃO FISCAL ***".center(largura),
                div,
                id_txt,
                f"Data/Hora: {info['data_hora']}",
                cpf_cupom,
                div,
            ])

        # Seção de Itens da Venda
        if itens:
            linhas.append("ITENS:")
            for idx_it, it in enumerate(itens, 1):
                linhas.append(f"{idx_it}. {it['produto_nome'][:36]}")
                linhas.append(f"   {it['quantidade']} un x {formatar_moeda(it['preco_unitario'])} = {formatar_moeda(it['valor_total'])}")
        else:
            linhas.append(f"Item: {info.get('produto_nome', '')[:34]}")
            linhas.append(f"Qtd : {info.get('quantidade', 1)} un x {formatar_moeda(info.get('preco_unitario', 0.0))} = {formatar_moeda(info.get('valor_total', 0.0))}")

        linhas.append(div)

        # Seção Financeira e Pagamento
        forma = info.get("forma_pagamento", "DINHEIRO")
        if forma == "DINHEIRO":
            linhas.append(f"Forma Pagto : DINHEIRO FISICO")
            linhas.append(f"TOTAL PAGO  : {formatar_moeda(info['valor_total'])}")
            if info.get("valor_recebido", 0) > 0:
                linhas.append(f"Valor Recebido : {formatar_moeda(info['valor_recebido'])}")
                linhas.append(f"Troco Devolvido: {formatar_moeda(info.get('troco', 0.0))}")
        elif forma == "PIX":
            linhas.append(f"Forma Pagto : PIX INSTANTANEO")
            linhas.append(f"TOTAL PAGO  : {formatar_moeda(info['valor_total'])}")
        elif forma in ("CARTAO_DEBITO", "CARTAO_CREDITO"):
            tipo_c = "CARTAO DE DEBITO" if forma == "CARTAO_DEBITO" else "CARTAO DE CREDITO"
            band = info.get("bandeira", "Mastercard")
            nsu = info.get("nsu", "")
            linhas.append(f"Forma Pagto : {tipo_c}")
            linhas.append(f"Bandeira    : {band}")
            if nsu:
                linhas.append(f"NSU / Aut   : {nsu}")
            linhas.append(f"TOTAL PAGO  : {formatar_moeda(info['valor_total'])}")
        else:
            linhas.append(f"TOTAL PAGO  : {formatar_moeda(info['valor_total'])}")

        linhas.append(div)

        # Rodapé e Dados de Auditoria / SEFAZ
        if eh_modo_fiscal and (eh_autorizada or eh_contingencia):
            chave = f_info.get("chave", "")
            chave_blocos = " ".join([chave[i:i+4] for i in range(0, len(chave), 4)]) if len(chave) == 44 else chave
            if eh_autorizada:
                linhas.append("EMITIDA EM MODO NORMAL - SEFAZ AUTORIZADA".center(largura))
                if f_info.get("protocolo"):
                    linhas.append(f"Protocolo: {f_info.get('protocolo')}")
            else:
                linhas.append("EMITIDA EM CONTINGENCIA OFFLINE".center(largura))
                linhas.append("Pendente de transmissao a SEFAZ".center(largura))

            if chave_blocos:
                linhas.extend([
                    "CHAVE DE ACESSO:".center(largura),
                    chave_blocos,
                ])
            linhas.extend([
                div,
                "Consulte pela Chave de Acesso no site da SEFAZ".center(largura),
                div_dupla,
                "\n\n\n",
            ])
        else:
            linhas.extend([
                "Documento sem valor fiscal".center(largura),
                "Uso interno e conferencia gerencial".center(largura),
                "Obrigado pela preferencia!".center(largura),
                div_dupla,
                "\n\n\n",
            ])

        conteudo_cupom = "\n".join(linhas)

        try:
            # 1. Copia sempre o comprovante para a área de transferência para agilidade
            try:
                clip.definir_texto_clipboard(conteudo_cupom, self)
            except Exception:
                pass

            # 2. Salva o comprovante em arquivo temporário (ex: cupom_venda_4.txt)
            temp_dir = tempfile.gettempdir()
            v_id_arq = info.get('venda_id') or (info.get('vendas_ids', [0])[0])
            caminho_cupom = os.path.join(temp_dir, f"cupom_venda_{v_id_arq}.txt")
            with open(caminho_cupom, "w", encoding="utf-8") as f:
                f.write(conteudo_cupom)

            impresso = False
            # 3. Dispara a impressão nativa via Spooler do Windows (os.startfile(..., "print"))
            # - Se a impressora padrão for física (térmica 58mm/80mm ou comum): imprime direto no papel
            # - Se a impressora padrão for Microsoft Print to PDF: abre o diálogo nativo do Windows para salvar diretamente em .PDF (ex: cupom_venda_X.pdf)
            if hasattr(os, "startfile"):
                try:
                    os.startfile(caminho_cupom, "print")
                    impresso = True
                except Exception as e_start:
                    print(f"Aviso os.startfile print: {e_start}")
                    impresso = False

            # 4. Fallback via PowerShell Out-Printer caso os.startfile falhe
            if not impresso:
                try:
                    cmd = f"Get-Content -Path '{caminho_cupom}' -Encoding UTF8 | Out-Printer"
                    res = subprocess.run(
                        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", cmd],
                        capture_output=True,
                        timeout=5,
                    )
                    if res.returncode == 0:
                        impresso = True
                except Exception:
                    impresso = False

            # 5. Se não conseguiu enviar ao spooler/gerador PDF, abre no Bloco de Notas
            if impresso:
                self._mostrar_feedback("🖨️ Comprovante enviado para a impressora / gerador de PDF!", sucesso=True)
            else:
                subprocess.Popen(["notepad.exe", caminho_cupom])
                self._mostrar_feedback(
                    "📄 Comprovante aberto para visualização e impressão (Ctrl+P)!\n(Copiado para a área de transferência)",
                    sucesso=True,
                )

        except Exception as e:
            messagebox.showwarning(
                "Aviso de Impressão",
                f"Erro ao processar comprovante:\n\n{str(e)}\n\nO texto foi copiado para a área de transferência."
            )

    def focar_nova_venda(self):
        """Foca no campo de bipagem por código de barras para nova venda."""
        self.entry_bipar.focus_set()
        self.entry_bipar.select_range(0, tk.END)
