"""
Módulo de Visualização: Cadastrar Novo Produto
Arquivo: views/product_form_view.py

Tela dedicada exclusivamente ao cadastro de novos itens no estoque,
com suporte a leitor de código de barras USB, campo de preço de custo,
botões de incremento rápido de quantidade e histórico dos últimos itens adicionados.
"""

import tkinter as tk
from typing import Callable, Optional, Dict, Any
import customtkinter as ctk

import database as db
import theme


class ProductFormView(ctk.CTkFrame):
    """Tela dedicada exclusivamente ao formulário de cadastro de produtos."""

    def __init__(self, parent, on_product_added_callback: Optional[Callable] = None, on_goto_catalogo: Optional[Callable] = None):
        super().__init__(parent, fg_color="transparent")
        self.on_product_added_callback = on_product_added_callback
        self.on_goto_catalogo = on_goto_catalogo
        self.produto_em_edicao: Optional[Dict[str, Any]] = None

        self._criar_layout()
        self.recarregar_dados()

    def _criar_layout(self):
        # 1. Cabeçalho
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(16, 12))

        col_tit = ctk.CTkFrame(header_frame, fg_color="transparent")
        col_tit.pack(side="left")

        lbl_titulo = ctk.CTkLabel(
            col_tit,
            text="➕ Cadastrar / Repor Produto",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        lbl_titulo.pack(anchor="w")

        lbl_subtitulo = ctk.CTkLabel(
            col_tit,
            text="Bipe com o leitor óptico USB ou digite o código de barras, nome e valores para cadastro ou reposição.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        )
        lbl_subtitulo.pack(anchor="w")

        if self.on_goto_catalogo:
            btn_ver_cat = ctk.CTkButton(
                header_frame,
                text="🏷️ Ver Catálogo Completo",
                font=ctk.CTkFont(size=12, weight="bold"),
                height=38,
                corner_radius=8,
                fg_color=theme.BTN_SECONDARY_BG,
                hover_color=theme.BTN_SECONDARY_HOVER,
                text_color=theme.BTN_SECONDARY_TEXT,
                command=self.on_goto_catalogo,
            )
            btn_ver_cat.pack(side="right")

        # 2. Corpo Dividido em Duas Colunas: Formulário à Esquerda, Últimos Cadastrados à Direita
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        # Coluna Esquerda: Formulário de Cadastro
        form_card = ctk.CTkFrame(body, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        form_card.pack(side="left", fill="both", expand=True, padx=(0, 12))

        ctk.CTkLabel(
            form_card,
            text="📝 Formulário de Registro",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=24, pady=(20, 14))

        # Campo: Código de Barras (com leitor USB)
        ctk.CTkLabel(
            form_card,
            text="Código de Barras (Bipe com o leitor ou digite) *",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=24, pady=(2, 2))

        self.entry_codigo_barras = ctk.CTkEntry(
            form_card,
            placeholder_text="Bipe aqui ou digite o EAN (ex: 7891000315507)",
            height=40,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
            font=ctk.CTkFont(size=13),
        )
        self.entry_codigo_barras.pack(fill="x", padx=24, pady=(0, 10))
        self.entry_codigo_barras.bind("<Return>", self._ao_bipar_ou_digitar_codigo_barras)
        self.entry_codigo_barras.bind("<KP_Enter>", self._ao_bipar_ou_digitar_codigo_barras)

        # Campo: Nome
        ctk.CTkLabel(
            form_card,
            text="Nome do Produto *",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=24, pady=(2, 2))

        self.entry_nome = ctk.CTkEntry(
            form_card,
            placeholder_text="Ex: Cabo HDMI 2.1 Ultra HD 2 Metros",
            height=40,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
            font=ctk.CTkFont(size=13),
        )
        self.entry_nome.pack(fill="x", padx=24, pady=(0, 10))

        # Grid para Preço de Custo e Preço de Venda
        grid_precos = ctk.CTkFrame(form_card, fg_color="transparent")
        grid_precos.pack(fill="x", padx=24, pady=(0, 10))

        col_custo = ctk.CTkFrame(grid_precos, fg_color="transparent")
        col_custo.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkLabel(
            col_custo,
            text="Preço de Custo (R$)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 2))

        self.entry_custo = ctk.CTkEntry(
            col_custo,
            placeholder_text="Ex: 25.00",
            height=40,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
            font=ctk.CTkFont(size=13),
        )
        self.entry_custo.pack(fill="x")

        col_venda = ctk.CTkFrame(grid_precos, fg_color="transparent")
        col_venda.pack(side="left", fill="x", expand=True, padx=(8, 0))

        ctk.CTkLabel(
            col_venda,
            text="Preço de Venda Unitário (R$) *",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 2))

        self.entry_preco = ctk.CTkEntry(
            col_venda,
            placeholder_text="Ex: 59.90",
            height=40,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
            font=ctk.CTkFont(size=13),
        )
        self.entry_preco.pack(fill="x")

        # Campo: Quantidade Inicial / A Repor
        ctk.CTkLabel(
            form_card,
            text="Quantidade em Estoque *",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=24, pady=(2, 2))

        self.entry_estoque = ctk.CTkEntry(
            form_card,
            placeholder_text="Ex: 25",
            height=40,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
            font=ctk.CTkFont(size=13),
        )
        self.entry_estoque.pack(fill="x", padx=24, pady=(0, 6))

        # Botões de Incremento Rápido de Estoque
        pills_estoque = ctk.CTkFrame(form_card, fg_color="transparent")
        pills_estoque.pack(fill="x", padx=24, pady=(0, 14))

        ctk.CTkLabel(pills_estoque, text="Atalhos rápidos:", font=ctk.CTkFont(size=10), text_color=theme.TEXT_MUTED).pack(side="left", padx=(0, 8))
        for val in [5, 10, 25, 50, 100]:
            btn_pill = ctk.CTkButton(
                pills_estoque,
                text=f"+{val}",
                width=45,
                height=26,
                corner_radius=6,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=theme.INNER_CARD_BG,
                text_color=theme.TEXT_SECONDARY,
                hover_color=theme.BTN_SECONDARY_HOVER,
                border_width=1,
                border_color=theme.BORDER_COLOR,
                command=lambda v=val: self._somar_estoque(v),
            )
            btn_pill.pack(side="left", padx=2)

        # Botões de Ação
        btn_frame = ctk.CTkFrame(form_card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(4, 10))

        self.btn_salvar = ctk.CTkButton(
            btn_frame,
            text="✔ SALVAR PRODUTO NO ESTOQUE",
            height=44,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            command=self._salvar_produto,
        )
        self.btn_salvar.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_limpar = ctk.CTkButton(
            btn_frame,
            text="Limpar",
            width=90,
            height=44,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._limpar_campos,
        )
        btn_limpar.pack(side="right")

        # Feedback Banner
        self.lbl_feedback = ctk.CTkLabel(
            form_card,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.ACCENT_GREEN[1],
            wraplength=440,
        )
        self.lbl_feedback.pack(anchor="w", padx=24, pady=(0, 12))

        # Coluna Direita: Últimos Cadastrados
        recent_card = ctk.CTkFrame(body, width=340, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        recent_card.pack(side="right", fill="both", expand=False, padx=(12, 0))
        recent_card.pack_propagate(False)

        ctk.CTkLabel(
            recent_card,
            text="📋 Últimos Adicionados",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=18, pady=(20, 4))

        ctk.CTkLabel(
            recent_card,
            text="Confira os itens cadastrados ou atualizados recentemente:",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=18, pady=(0, 12))

        self.scroll_recentes = ctk.CTkScrollableFrame(recent_card, fg_color="transparent")
        self.scroll_recentes.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def _ao_bipar_ou_digitar_codigo_barras(self, event=None):
        """Ao bipar ou pressionar Enter no código de barras, busca o produto no banco."""
        cod = self.entry_codigo_barras.get().strip()
        if not cod:
            self.entry_nome.focus_set()
            return

        prod = db.obter_produto_por_codigo_barras(cod)
        if prod:
            self.produto_em_edicao = prod
            self.entry_nome.delete(0, tk.END)
            self.entry_nome.insert(0, prod["nome"])

            self.entry_preco.delete(0, tk.END)
            self.entry_preco.insert(0, f"{prod['preco']:.2f}")

            self.entry_custo.delete(0, tk.END)
            custo_val = prod.get("preco_custo", 0.0) or 0.0
            self.entry_custo.insert(0, f"{custo_val:.2f}")

            self.entry_estoque.delete(0, tk.END)
            self.entry_estoque.insert(0, str(prod["estoque"]))

            self.btn_salvar.configure(text=f"🔄 ATUALIZAR '{prod['nome'][:20]}...'")
            self._mostrar_feedback(
                f"Produto '{prod['nome']}' localizado! Dados carregados para edição ou reposição.",
                sucesso=True,
            )
            self.entry_estoque.focus_set()
            self.entry_estoque.select_range(0, tk.END)
        else:
            self.produto_em_edicao = None
            self.btn_salvar.configure(text="✔ SALVAR PRODUTO NO ESTOQUE")
            self._mostrar_feedback("Código de barras novo. Prossiga informando o nome e valores.", sucesso=True)
            self.entry_nome.focus_set()

    def _somar_estoque(self, incremento: int):
        atual = self.entry_estoque.get().strip()
        try:
            val = int(atual)
            novo = val + incremento
        except ValueError:
            novo = incremento
        self.entry_estoque.delete(0, tk.END)
        self.entry_estoque.insert(0, str(novo))

    def _limpar_campos(self):
        self.produto_em_edicao = None
        self.entry_codigo_barras.delete(0, tk.END)
        self.entry_nome.delete(0, tk.END)
        self.entry_custo.delete(0, tk.END)
        self.entry_preco.delete(0, tk.END)
        self.entry_estoque.delete(0, tk.END)
        self.btn_salvar.configure(text="✔ SALVAR PRODUTO NO ESTOQUE")
        self.entry_codigo_barras.focus_set()

    def _mostrar_feedback(self, msg: str, sucesso: bool = True):
        cor = theme.ACCENT_GREEN[1] if sucesso else theme.ACCENT_RED[1]
        self.lbl_feedback.configure(text=msg, text_color=cor)
        self.after(5000, lambda: self.lbl_feedback.configure(text=""))

    def _salvar_produto(self):
        cod_barras = self.entry_codigo_barras.get().strip()
        nome = self.entry_nome.get().strip()
        custo_str = self.entry_custo.get().strip().replace(",", ".")
        preco_str = self.entry_preco.get().strip().replace(",", ".")
        estoque_str = self.entry_estoque.get().strip()

        if not nome:
            self._mostrar_feedback("O nome do produto é obrigatório.", sucesso=False)
            return

        preco_custo = 0.0
        if custo_str:
            try:
                preco_custo = float(custo_str)
                if preco_custo < 0:
                    raise ValueError
            except ValueError:
                self._mostrar_feedback("Informe um preço de custo válido (ex: 25.50).", sucesso=False)
                return

        try:
            preco = float(preco_str)
            if preco <= 0:
                raise ValueError
        except ValueError:
            self._mostrar_feedback("Informe um preço de venda unitário válido maior que zero (ex: 39.90).", sucesso=False)
            return

        try:
            estoque = int(estoque_str)
            if estoque < 0:
                raise ValueError
        except ValueError:
            self._mostrar_feedback("Informe uma quantidade de estoque válida maior ou igual a zero.", sucesso=False)
            return

        if self.produto_em_edicao:
            sucesso, msg = db.atualizar_produto(
                produto_id=self.produto_em_edicao["id"],
                nome=nome,
                preco=preco,
                estoque=estoque,
                codigo_barras=cod_barras if cod_barras else None,
                preco_custo=preco_custo,
            )
        else:
            sucesso, msg = db.adicionar_produto(
                nome=nome,
                preco=preco,
                estoque=estoque,
                codigo_barras=cod_barras if cod_barras else None,
                preco_custo=preco_custo,
            )

        self._mostrar_feedback(msg, sucesso=sucesso)

        if sucesso:
            self._limpar_campos()
            self.recarregar_dados()
            if self.on_product_added_callback:
                self.on_product_added_callback()

    def recarregar_dados(self):
        """Atualiza a lista lateral com os 10 últimos produtos cadastrados."""
        for w in self.scroll_recentes.winfo_children():
            w.destroy()

        produtos = db.listar_produtos()
        # Ordena pelos IDs maiores (mais recentes)
        recentes = sorted(produtos, key=lambda x: x["id"], reverse=True)[:10]

        if not recentes:
            lbl_vazio = ctk.CTkLabel(
                self.scroll_recentes,
                text="Nenhum produto cadastrado ainda.",
                font=ctk.CTkFont(size=11, slant="italic"),
                text_color=theme.TEXT_MUTED,
            )
            lbl_vazio.pack(pady=30)
            return

        for p in recentes:
            card = ctk.CTkFrame(self.scroll_recentes, height=52, fg_color=theme.INNER_CARD_BG, corner_radius=6, border_width=1, border_color=theme.BORDER_COLOR)
            card.pack(fill="x", pady=3)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(6, 2))

            ctk.CTkLabel(top_row, text=p["nome"], font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_PRIMARY, anchor="w").pack(side="left", fill="x", expand=True)

            preco_fmt = f"R$ {p['preco']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            ctk.CTkLabel(top_row, text=preco_fmt, font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.PRICE_COLOR).pack(side="right")

            bot_row = ctk.CTkFrame(card, fg_color="transparent")
            bot_row.pack(fill="x", padx=10, pady=(0, 6))

            cod_txt = f"EAN: {p['codigo_barras']}" if p.get("codigo_barras") else f"ID #{p['id']}"
            ctk.CTkLabel(bot_row, text=f"Estoque: {p['estoque']} un  •  {cod_txt}", font=ctk.CTkFont(size=10), text_color=theme.TEXT_SECONDARY).pack(side="left")

    def focar_cadastro(self):
        """Foca no campo de código de barras ao abrir a tela."""
        self.entry_codigo_barras.focus_set()
