"""
Módulo de Visualização: Nova Venda Balcão (PDV)
Arquivo: views/pos_sale_view.py

Tela dedicada exclusivamente à realização de novas vendas no balcão,
com suporte a leitor de código de barras USB, seleção rápida de produtos,
cálculo instantâneo de totais, tecla de atalho F2/Enter e baixa atômica de estoque.
"""

import os
import tempfile
import subprocess
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk

import database as db
import theme


def formatar_moeda(valor: float) -> str:
    """Formata valor numérico para padrão monetário brasileiro R$ 0,00."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class POSSaleView(ctk.CTkFrame):
    """Tela de checkout dedicada para realizar novas vendas no PDV."""

    def __init__(self, parent, on_sale_completed_callback: Optional[Callable] = None, on_goto_historico: Optional[Callable] = None):
        super().__init__(parent, fg_color="transparent")
        self.on_sale_completed_callback = on_sale_completed_callback
        self.on_goto_historico = on_goto_historico

        self.produtos_disponiveis: List[Dict[str, Any]] = []
        self.mapa_produtos: Dict[str, Dict[str, Any]] = {}
        self.produto_selecionado: Optional[Dict[str, Any]] = None
        self.ultima_venda_info: Optional[Dict[str, Any]] = None

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

        if self.on_goto_historico:
            btn_hist = ctk.CTkButton(
                header_frame,
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

        # Coluna Esquerda: Terminal de Operação
        op_card = ctk.CTkFrame(body, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        op_card.pack(side="left", fill="both", expand=True, padx=(0, 12))

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

        # Seleção Manual de Produto
        ctk.CTkLabel(
            op_card,
            text="Ou Selecione na Lista de Produtos em Estoque:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=24, pady=(2, 2))

        self.combo_produtos = ctk.CTkComboBox(
            op_card,
            values=["Nenhum produto disponível"],
            height=42,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            button_color=theme.ACCENT_BLUE,
            button_hover_color=theme.ACCENT_BLUE_HOVER,
            dropdown_fg_color=theme.CARD_BG,
            dropdown_hover_color=theme.INNER_CARD_BG,
            font=ctk.CTkFont(size=13),
            command=self._ao_selecionar_produto,
        )
        self.combo_produtos.pack(fill="x", padx=24, pady=(0, 14))

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
        self.entry_qtd.bind("<Return>", lambda event: self.confirmar_venda_atalho(event))
        self.entry_qtd.bind("<KP_Enter>", lambda event: self.confirmar_venda_atalho(event))

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

        # Atalhos rápidos de quantidade
        pills_qtd = ctk.CTkFrame(op_card, fg_color="transparent")
        pills_qtd.pack(fill="x", padx=24, pady=(0, 14))
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
                command=lambda v=q: self._definir_qtd(v),
            ).pack(side="left", padx=2)

        # Visor de Subtotal
        total_card = ctk.CTkFrame(op_card, corner_radius=10, fg_color=theme.INNER_CARD_BG, border_width=1, border_color=theme.ACCENT_BLUE)
        total_card.pack(fill="x", padx=24, pady=(4, 14))

        ctk.CTkLabel(total_card, text="SUBTOTAL DA VENDA", font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(12, 2))
        self.lbl_subtotal = ctk.CTkLabel(total_card, text="R$ 0,00", font=ctk.CTkFont(size=28, weight="bold"), text_color=theme.PRICE_COLOR)
        self.lbl_subtotal.pack(pady=(0, 12))

        # Botão Confirmar (com atalho F2)
        self.btn_confirmar = ctk.CTkButton(
            op_card,
            text="✔ CONFIRMAR VENDA (F2)",
            height=46,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            command=self._confirmar_venda,
        )
        self.btn_confirmar.pack(fill="x", padx=24, pady=(4, 6))

        # Feedback Banner
        self.lbl_feedback = ctk.CTkLabel(
            op_card,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.ACCENT_GREEN[1],
            wraplength=440,
        )
        self.lbl_feedback.pack(padx=24, pady=(0, 4))

        # 4. Calculadora de Troco (Abaixo do botão F2)
        card_troco = ctk.CTkFrame(
            op_card,
            corner_radius=10,
            fg_color=theme.INNER_CARD_BG,
            border_width=1,
            border_color=theme.BORDER_COLOR,
        )
        card_troco.pack(fill="x", padx=24, pady=(0, 10))

        # Cabeçalho da Calculadora de Troco
        head_troco = ctk.CTkFrame(card_troco, fg_color="transparent")
        head_troco.pack(fill="x", padx=16, pady=(10, 4))

        ctk.CTkLabel(
            head_troco,
            text="💵 Cálculo de Troco (Dinheiro)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        # Botões de Atalho no Cabeçalho
        btn_box_head = ctk.CTkFrame(head_troco, fg_color="transparent")
        btn_box_head.pack(side="right")

        ctk.CTkButton(
            btn_box_head,
            text="Valor Exato",
            width=70,
            height=24,
            corner_radius=6,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._definir_valor_recebido_exato,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_box_head,
            text="Limpar",
            width=55,
            height=24,
            corner_radius=6,
            font=ctk.CTkFont(size=10),
            fg_color=theme.CARD_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.TEXT_MUTED,
            border_width=1,
            border_color=theme.BORDER_COLOR,
            command=self._limpar_troco,
        ).pack(side="left")

        # Grid com 2 colunas: Valor Entregue e Troco Final
        grid_troco = ctk.CTkFrame(card_troco, fg_color="transparent")
        grid_troco.pack(fill="x", padx=16, pady=(4, 6))

        # Coluna 1: Valor Entregue pelo Cliente
        col_pago = ctk.CTkFrame(grid_troco, fg_color="transparent")
        col_pago.pack(side="left", fill="both", expand=True, padx=(0, 6))

        ctk.CTkLabel(
            col_pago,
            text="Valor Entregue pelo Cliente (R$):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, 2))

        self.entry_recebido = ctk.CTkEntry(
            col_pago,
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=15, weight="bold"),
            placeholder_text="0,00",
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
        )
        self.entry_recebido.pack(fill="x", pady=(0, 4))
        self.entry_recebido.bind("<KeyRelease>", lambda event: self._ao_digitar_recebido())
        self.entry_recebido.bind("<Return>", lambda event: self.confirmar_venda_atalho(event))

        # Pílulas de Cédulas Rápidas
        pills_cedulas = ctk.CTkFrame(col_pago, fg_color="transparent")
        pills_cedulas.pack(fill="x")
        for val_cedula in [20, 50, 100, 200]:
            ctk.CTkButton(
                pills_cedulas,
                text=f"R$ {val_cedula}",
                width=44,
                height=22,
                corner_radius=5,
                font=ctk.CTkFont(size=9, weight="bold"),
                fg_color=theme.CARD_BG,
                hover_color=theme.BTN_SECONDARY_HOVER,
                text_color=theme.TEXT_SECONDARY,
                border_width=1,
                border_color=theme.BORDER_COLOR,
                command=lambda v=val_cedula: self._definir_valor_recebido(v),
            ).pack(side="left", padx=1)

        # Coluna 2: Troco Final (Calculado e Alterável)
        col_troco = ctk.CTkFrame(grid_troco, fg_color="transparent")
        col_troco.pack(side="right", fill="both", expand=True, padx=(6, 0))

        ctk.CTkLabel(
            col_troco,
            text="Troco a Devolver ao Cliente (R$):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, 2))

        self.entry_troco = ctk.CTkEntry(
            col_troco,
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=15, weight="bold"),
            placeholder_text="0,00",
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.STOCK_COLOR[1],
        )
        self.entry_troco.pack(fill="x", pady=(0, 4))
        self.entry_troco.bind("<KeyRelease>", lambda event: self._ao_digitar_troco())
        self.entry_troco.bind("<Return>", lambda event: self.confirmar_venda_atalho(event))

        # Status / Dica do Troco
        self.lbl_status_troco = ctk.CTkLabel(
            card_troco,
            text="Aguardando valor do cliente...",
            font=ctk.CTkFont(size=10),
            text_color=theme.TEXT_MUTED,
        )
        self.lbl_status_troco.pack(fill="x", padx=16, pady=(0, 8))

        # Coluna Direita: Comprovante da Última Venda
        recibo_card = ctk.CTkFrame(body, width=340, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        recibo_card.pack(side="right", fill="both", expand=False, padx=(12, 0))
        recibo_card.pack_propagate(False)

        ctk.CTkLabel(
            recibo_card,
            text="🧾 Último Cupom / Comprovante",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=18, pady=(20, 4))

        self.box_recibo = ctk.CTkFrame(recibo_card, fg_color=theme.INNER_CARD_BG, corner_radius=10, border_width=1, border_color=theme.BORDER_COLOR)
        self.box_recibo.pack(fill="both", expand=True, padx=16, pady=(10, 10))

        self.lbl_recibo_detalhes = ctk.CTkLabel(
            self.box_recibo,
            text="Nenhuma venda finalizada nesta sessão ainda.\n\nAssim que você confirmar uma venda, os detalhes do cupom aparecerão aqui.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_MUTED,
            justify="center",
            wraplength=280,
        )
        self.lbl_recibo_detalhes.pack(expand=True, padx=14, pady=20)

        # Botão Imprimir Comprovante (para impressora térmica ou padrão)
        self.btn_imprimir = ctk.CTkButton(
            recibo_card,
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
        self.btn_imprimir.pack(fill="x", padx=16, pady=(0, 16))

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
            self._mostrar_feedback(f"✔ Bipado: {prod_encontrado['nome']} ({formatar_moeda(prod_encontrado['preco'])})", sucesso=True)
            self.entry_bipar.delete(0, tk.END)
            self.entry_qtd.focus_set()
            self.entry_qtd.select_range(0, tk.END)
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

    def _obter_subtotal_atual(self) -> float:
        if not self.produto_selecionado:
            return 0.0
        try:
            qtd = int(self.entry_qtd.get().strip())
            if qtd <= 0:
                return 0.0
            return round(qtd * self.produto_selecionado["preco"], 2)
        except ValueError:
            return 0.0

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

    def _limpar_troco(self):
        """Limpa os campos de troco e valor recebido."""
        if hasattr(self, "entry_recebido"):
            self.entry_recebido.delete(0, tk.END)
        if hasattr(self, "entry_troco"):
            self.entry_troco.delete(0, tk.END)
        if hasattr(self, "lbl_status_troco"):
            self.lbl_status_troco.configure(text="Aguardando valor do cliente...", text_color=theme.TEXT_MUTED)

    def _atualizar_subtotal(self):
        sub = self._obter_subtotal_atual()
        self.lbl_subtotal.configure(text=formatar_moeda(sub))
        if hasattr(self, "entry_recebido"):
            self._ao_digitar_recebido()

    def recarregar_dados(self):
        """Atualiza a lista de produtos disponíveis para venda."""
        todos = db.listar_produtos()
        self.produtos_disponiveis = [p for p in todos if p["estoque"] > 0]
        self.mapa_produtos.clear()

        opcoes = []
        for p in self.produtos_disponiveis:
            cod_txt = f" [{p['codigo_barras']}]" if p.get("codigo_barras") else ""
            chave = f"{p['nome']}{cod_txt} (Estoque: {p['estoque']} | {formatar_moeda(p['preco'])})"
            self.mapa_produtos[chave] = p
            opcoes.append(chave)

        if opcoes:
            self.combo_produtos.configure(values=opcoes)
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
        if getattr(self, "_processando_venda", False):
            return
        self._processando_venda = True
        try:
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

            sucesso, msg, info_venda = db.registrar_venda(self.produto_selecionado["id"], qtd)

            if sucesso and info_venda:
                # Captura valor recebido e troco se informados no caixa
                rec_val = self._converter_texto_para_float(self.entry_recebido.get()) if hasattr(self, "entry_recebido") else None
                troco_val = self._converter_texto_para_float(self.entry_troco.get()) if hasattr(self, "entry_troco") else None

                if rec_val is not None and rec_val > 0:
                    info_venda["valor_recebido"] = rec_val
                    info_venda["troco"] = troco_val if troco_val is not None else max(0.0, round(rec_val - info_venda["valor_total"], 2))
                else:
                    info_venda["valor_recebido"] = 0.0
                    info_venda["troco"] = 0.0

                # Processamento Fiscal (respeita modo Não-Fiscal vs Fiscal NFC-e com contingência)
                try:
                    from fiscal.fiscal_service import FiscalService
                    f_svc = FiscalService()
                    res_fiscal = f_svc.emitir_venda_pdv(
                        venda_id=info_venda["venda_id"],
                        itens=[info_venda],
                        valor_total=info_venda["valor_total"],
                        forma_pagamento="01",
                        troco=info_venda.get("troco", 0.0),
                        valor_recebido=info_venda.get("valor_recebido", 0.0),
                    )
                    info_venda["fiscal"] = res_fiscal
                    if res_fiscal.get("contingencia"):
                        msg += "\n⚠️ NFC-e gerada em CONTINGÊNCIA OFFLINE (Sincronização em segundo plano)."
                except Exception as ef:
                    print(f"Erro na camada fiscal: {ef}")

                self.ultima_venda_info = info_venda
                self._mostrar_feedback(msg, sucesso=True)
                self._atualizar_comprovante(info_venda)
                self._definir_qtd(1)
                self._limpar_troco()
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
        bloco_financeiro = f"TOTAL PAGO: {formatar_moeda(info['valor_total'])}\n"
        if info.get("valor_recebido", 0) > 0:
            bloco_financeiro += (
                f"Valor Recebido: {formatar_moeda(info['valor_recebido'])}\n"
                f"Troco Devolvido: {formatar_moeda(info.get('troco', 0.0))}\n"
            )

        f_info = info.get("fiscal", {})
        eh_fiscal = f_info.get("modo") == "FISCAL_NFCE"

        if eh_fiscal:
            if f_info.get("contingencia"):
                header_txt = (
                    "*** NFC-e EMITIDA EM CONTINGÊNCIA ***\n"
                    "*** PENDENTE DE AUTORIZAÇÃO ***\n\n"
                    f"NFC-e nº: {f_info.get('numero_nfce', '')}\n"
                    f"Chave: {f_info.get('chave', '')[:28]}..."
                )
                footer_txt = "EMITIDA EM CONTINGÊNCIA - Pendente de autorização"
                cor_recibo = theme.WARNING_COLOR[1]
            else:
                header_txt = (
                    "*** CUPOM FISCAL ELETRÔNICO (NFC-e) ***\n\n"
                    f"NFC-e nº: {f_info.get('numero_nfce', '')}\n"
                    f"Protocolo: {f_info.get('protocolo', '')}\n"
                    f"Chave: {f_info.get('chave', '')[:28]}..."
                )
                footer_txt = "Autorizado o uso da NF-e pela SEFAZ"
                cor_recibo = theme.PRICE_COLOR[1]
        else:
            header_txt = "*** COMPROVANTE NÃO FISCAL - CONTROLE INTERNO ***\n"
            footer_txt = "Documento sem valor fiscal - Controle Interno"
            cor_recibo = theme.ACCENT_GREEN[1]

        texto = (
            f"{header_txt}\n"
            f"Venda ID: #{info['venda_id']}\n"
            f"Horário: {info['data_hora']}\n"
            "----------------------------------------\n"
            f"Item: {info['produto_nome']}\n"
            f"Quantidade: {info['quantidade']} un\n"
            f"Preço Unitário: {formatar_moeda(info['preco_unitario'])}\n"
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
        """Envia o comprovante da última venda para a impressora padrão do Windows."""
        if not self.ultima_venda_info:
            messagebox.showinfo("Aviso", "Nenhuma venda foi finalizada para imprimir comprovante.")
            return

        info = self.ultima_venda_info
        largura = 40
        div = "-" * largura
        div_dupla = "=" * largura

        # Formato otimizado para bobinas térmicas (58mm/80mm) ou impressoras de papel comum
        linhas = [
            div_dupla,
            "CENTRAL DE VENDAS".center(largura),
            "CONTROLE INTERNO / GERENCIAL".center(largura),
            div_dupla,
            "*** COMPROVANTE NÃO FISCAL ***".center(largura),
            div,
            f"Venda ID : #{info['venda_id']}",
            f"Data/Hora: {info['data_hora']}",
            div,
            f"Item: {info['produto_nome']}",
            f"Qtd : {info['quantidade']} un x {formatar_moeda(info['preco_unitario'])}",
            div,
            f"TOTAL PAGO: {formatar_moeda(info['valor_total'])}",
        ]

        if info.get("valor_recebido", 0) > 0:
            linhas.append(f"Valor Recebido : {formatar_moeda(info['valor_recebido'])}")
            linhas.append(f"Troco Devolvido: {formatar_moeda(info.get('troco', 0.0))}")

        linhas.extend([
            div,
            "Documento sem valor fiscal".center(largura),
            "Uso interno e conferência gerencial".center(largura),
            "Obrigado pela preferência!".center(largura),
            div_dupla,
            "\n\n\n\n",
        ])
        conteudo_cupom = "\n".join(linhas)

        try:
            temp_dir = tempfile.gettempdir()
            caminho_cupom = os.path.join(temp_dir, f"cupom_venda_{info['venda_id']}.txt")
            with open(caminho_cupom, "w", encoding="utf-8") as f:
                f.write(conteudo_cupom)

            impresso = False
            # 1. ShellExecute nativo do Windows (Notepad /p silencioso)
            if hasattr(os, "startfile"):
                try:
                    os.startfile(caminho_cupom, "print")
                    impresso = True
                except Exception:
                    impresso = False

            # 2. Fallback via PowerShell Out-Printer
            if not impresso:
                cmd = f"Get-Content -Path '{caminho_cupom}' -Encoding UTF8 | Out-Printer"
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", cmd],
                    capture_output=True,
                    timeout=8,
                )
                if res.returncode == 0:
                    impresso = True
                else:
                    erro_ps = res.stderr.decode("cp1252", errors="replace").strip()
                    raise RuntimeError(erro_ps or "Falha ao enviar documento ao spooler de impressão.")

            self._mostrar_feedback(f"🖨️ Cupom #{info['venda_id']} enviado para a impressora!", sucesso=True)

        except Exception as e:
            messagebox.showwarning(
                "Aviso de Impressão",
                f"Não foi possível enviar o cupom para a impressora:\n\n{str(e)}\n\n"
                f"Verifique se sua impressora de comprovantes está conectada, ligada e configurada como padrão no Windows."
            )

    def focar_nova_venda(self):
        """Foca no campo de bipagem por código de barras para nova venda."""
        self.entry_bipar.focus_set()
        self.entry_bipar.select_range(0, tk.END)
