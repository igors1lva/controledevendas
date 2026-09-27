"""
Módulo de Ponto de Venda (PDV / Vendas)
Arquivo: views/pos_view.py

Responsável pela seleção de produtos, cálculo de subtotais em tempo real,
abate atômico de estoque, validação contra estoque zerado e registro das vendas.
"""

import tkinter as tk
from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk

import database as db


def formatar_moeda(valor: float) -> str:
    """Formata valor numérico para padrão monetário brasileiro R$ 0,00."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class POSView(ctk.CTkFrame):
    """Painel do Ponto de Venda (PDV)."""

    def __init__(self, parent, on_sale_completed_callback: Optional[Callable] = None):
        super().__init__(parent, fg_color="transparent")
        self.on_sale_completed_callback = on_sale_completed_callback

        # Estado interno
        self.produtos_disponiveis: List[Dict[str, Any]] = []
        self.mapa_produtos: Dict[str, Dict[str, Any]] = {}  # "Nome [ID #X]" -> dict
        self.produto_selecionado: Optional[Dict[str, Any]] = None

        self._criar_layout()
        self.recarregar_dados()

    def _criar_layout(self):
        # 1. Cabeçalho
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(16, 12))

        lbl_titulo = ctk.CTkLabel(
            header_frame,
            text="🛒 Ponto de Venda (PDV)",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC",
        )
        lbl_titulo.pack(anchor="w")

        lbl_subtitulo = ctk.CTkLabel(
            header_frame,
            text="Realize vendas rápidas, com baixa automática de estoque e cálculo de totais em tempo real.",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8",
        )
        lbl_subtitulo.pack(anchor="w")

        # 2. Corpo Principal Dividido em Duas Colunas (Esquerda: Operação | Direita: Resumo e Histórico)
        body_frame = ctk.CTkFrame(self, fg_color="transparent")
        body_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        # ====================================================================
        # COLUNA ESQUERDA: Formulário da Venda
        # ====================================================================
        left_card = ctk.CTkFrame(body_frame, corner_radius=12, fg_color="#1E293B", border_width=1, border_color="#334155")
        left_card.pack(side="left", fill="both", expand=True, padx=(0, 12))

        ctk.CTkLabel(
            left_card,
            text="⚡ Nova Operação de Venda",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#F8FAFC",
        ).pack(anchor="w", padx=20, pady=(18, 12))

        # Seleção de Produto
        ctk.CTkLabel(
            left_card,
            text="Selecione o Produto:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#E2E8F0",
        ).pack(anchor="w", padx=20, pady=(4, 2))

        self.combo_produtos = ctk.CTkComboBox(
            left_card,
            values=["Nenhum produto com estoque disponível"],
            height=38,
            corner_radius=8,
            fg_color="#0F172A",
            border_color="#334155",
            button_color="#2563EB",
            button_hover_color="#1D4ED8",
            dropdown_fg_color="#1E293B",
            dropdown_hover_color="#334155",
            command=self._ao_selecionar_produto,
        )
        self.combo_produtos.pack(fill="x", padx=20, pady=(0, 14))

        # Cards Informativos do Produto Selecionado
        info_grid = ctk.CTkFrame(left_card, fg_color="transparent")
        info_grid.pack(fill="x", padx=20, pady=(0, 14))

        # Preço Unitário Card
        card_preco = ctk.CTkFrame(info_grid, corner_radius=8, fg_color="#0F172A", border_width=1, border_color="#334155")
        card_preco.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=4)
        ctk.CTkLabel(card_preco, text="PREÇO UNITÁRIO", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(pady=(8, 2))
        self.lbl_preco_unit = ctk.CTkLabel(card_preco, text="R$ 0,00", font=ctk.CTkFont(size=16, weight="bold"), text_color="#38BDF8")
        self.lbl_preco_unit.pack(pady=(0, 8))

        # Estoque Disponível Card
        card_est = ctk.CTkFrame(info_grid, corner_radius=8, fg_color="#0F172A", border_width=1, border_color="#334155")
        card_est.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
        ctk.CTkLabel(card_est, text="ESTOQUE ATUAL", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(pady=(8, 2))
        self.lbl_estoque_disp = ctk.CTkLabel(card_est, text="0 un", font=ctk.CTkFont(size=16, weight="bold"), text_color="#10B981")
        self.lbl_estoque_disp.pack(pady=(0, 8))

        # Campo: Quantidade a Vender
        ctk.CTkLabel(
            left_card,
            text="Quantidade a Vender:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#E2E8F0",
        ).pack(anchor="w", padx=20, pady=(6, 2))

        qtd_frame = ctk.CTkFrame(left_card, fg_color="transparent")
        qtd_frame.pack(fill="x", padx=20, pady=(0, 14))

        self.btn_menos = ctk.CTkButton(
            qtd_frame,
            text="-",
            width=42,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#334155",
            hover_color="#475569",
            command=self._diminuir_qtd,
        )
        self.btn_menos.pack(side="left", padx=(0, 8))

        self.entry_qtd = ctk.CTkEntry(
            qtd_frame,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            justify="center",
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.entry_qtd.insert(0, "1")
        self.entry_qtd.pack(side="left", fill="x", expand=True)
        self.entry_qtd.bind("<KeyRelease>", lambda event: self._atualizar_subtotal())

        self.btn_mais = ctk.CTkButton(
            qtd_frame,
            text="+",
            width=42,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#334155",
            hover_color="#475569",
            command=self._aumentar_qtd,
        )
        self.btn_mais.pack(side="left", padx=(8, 0))

        # Card de Total da Operação (Subtotal)
        card_total = ctk.CTkFrame(left_card, corner_radius=10, fg_color="#0F172A", border_width=1, border_color="#2563EB")
        card_total.pack(fill="x", padx=20, pady=(8, 14))

        ctk.CTkLabel(
            card_total,
            text="TOTAL DA VENDA",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#94A3B8",
        ).pack(pady=(12, 2))

        self.lbl_subtotal = ctk.CTkLabel(
            card_total,
            text="R$ 0,00",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#38BDF8",
        )
        self.lbl_subtotal.pack(pady=(0, 12))

        # Botão Confirmar Venda
        self.btn_confirmar = ctk.CTkButton(
            left_card,
            text="✔ CONFIRMAR VENDA (F2)",
            height=46,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#10B981",
            hover_color="#059669",
            command=self._confirmar_venda,
        )
        self.btn_confirmar.pack(fill="x", padx=20, pady=(6, 10))

        # Banner de Feedback / Alertas
        self.lbl_feedback = ctk.CTkLabel(
            left_card,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#10B981",
            wraplength=380,
        )
        self.lbl_feedback.pack(padx=20, pady=(0, 14))

        # ====================================================================
        # COLUNA DIREITA: Indicadores do Dia e Histórico de Vendas
        # ====================================================================
        right_card = ctk.CTkFrame(body_frame, corner_radius=12, fg_color="#1E293B", border_width=1, border_color="#334155")
        right_card.pack(side="right", fill="both", expand=True, padx=(12, 0))

        ctk.CTkLabel(
            right_card,
            text="📊 Desempenho do Dia",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#F8FAFC",
        ).pack(anchor="w", padx=20, pady=(18, 12))

        # Grid de Resumo do Dia
        resumo_grid = ctk.CTkFrame(right_card, fg_color="transparent")
        resumo_grid.pack(fill="x", padx=20, pady=(0, 12))

        # Card: Faturamento Hoje
        card_fat = ctk.CTkFrame(resumo_grid, corner_radius=8, fg_color="#0F172A", border_width=1, border_color="#334155")
        card_fat.pack(side="left", fill="both", expand=True, padx=(0, 4))
        ctk.CTkLabel(card_fat, text="FATURAMENTO HOJE", font=ctk.CTkFont(size=9, weight="bold"), text_color="#94A3B8").pack(pady=(6, 1))
        self.lbl_fat_hoje = ctk.CTkLabel(card_fat, text="R$ 0,00", font=ctk.CTkFont(size=14, weight="bold"), text_color="#10B981")
        self.lbl_fat_hoje.pack(pady=(0, 6))

        # Card: Itens Vendidos
        card_itens = ctk.CTkFrame(resumo_grid, corner_radius=8, fg_color="#0F172A", border_width=1, border_color="#334155")
        card_itens.pack(side="left", fill="both", expand=True, padx=4)
        ctk.CTkLabel(card_itens, text="ITENS VENDIDOS", font=ctk.CTkFont(size=9, weight="bold"), text_color="#94A3B8").pack(pady=(6, 1))
        self.lbl_itens_hoje = ctk.CTkLabel(card_itens, text="0 un", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC")
        self.lbl_itens_hoje.pack(pady=(0, 6))

        # Card: Vendas Realizadas
        card_trans = ctk.CTkFrame(resumo_grid, corner_radius=8, fg_color="#0F172A", border_width=1, border_color="#334155")
        card_trans.pack(side="left", fill="both", expand=True, padx=(4, 0))
        ctk.CTkLabel(card_trans, text="OPERAÇÕES", font=ctk.CTkFont(size=9, weight="bold"), text_color="#94A3B8").pack(pady=(6, 1))
        self.lbl_vendas_hoje = ctk.CTkLabel(card_trans, text="0", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38BDF8")
        self.lbl_vendas_hoje.pack(pady=(0, 6))

        # Histórico de Vendas Recentes
        ctk.CTkLabel(
            right_card,
            text="Últimas Vendas Realizadas Hoje:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#CBD5E1",
        ).pack(anchor="w", padx=20, pady=(6, 6))

        # Tabela Cabeçalho de Vendas Recentes
        rec_header = ctk.CTkFrame(right_card, height=28, fg_color="#0F172A", corner_radius=6)
        rec_header.pack(fill="x", padx=20, pady=(0, 4))

        ctk.CTkLabel(rec_header, text="Hora", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8", width=55).pack(side="left", padx=4)
        ctk.CTkLabel(rec_header, text="Produto", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkLabel(rec_header, text="Qtd", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8", width=45).pack(side="left", padx=4)
        ctk.CTkLabel(rec_header, text="Total", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8", width=80).pack(side="left", padx=4)

        # Scrollable Frame para Linhas de Vendas
        self.scroll_historico = ctk.CTkScrollableFrame(right_card, fg_color="transparent")
        self.scroll_historico.pack(fill="both", expand=True, padx=20, pady=(0, 14))

    def _mostrar_feedback(self, mensagem: str, sucesso: bool = True):
        cor = "#10B981" if sucesso else "#EF4444"
        self.lbl_feedback.configure(text=mensagem, text_color=cor)
        self.after(5000, lambda: self.lbl_feedback.configure(text=""))

    def _diminuir_qtd(self):
        try:
            val = int(self.entry_qtd.get().strip())
            if val > 1:
                self.entry_qtd.delete(0, tk.END)
                self.entry_qtd.insert(0, str(val - 1))
                self._atualizar_subtotal()
        except ValueError:
            self.entry_qtd.delete(0, tk.END)
            self.entry_qtd.insert(0, "1")
            self._atualizar_subtotal()

    def _aumentar_qtd(self):
        try:
            val = int(self.entry_qtd.get().strip())
            if self.produto_selecionado and val >= self.produto_selecionado["estoque"]:
                self._mostrar_feedback(f"Estoque máximo disponível: {self.produto_selecionado['estoque']} un.", sucesso=False)
                return
            self.entry_qtd.delete(0, tk.END)
            self.entry_qtd.insert(0, str(val + 1))
            self._atualizar_subtotal()
        except ValueError:
            self.entry_qtd.delete(0, tk.END)
            self.entry_qtd.insert(0, "1")
            self._atualizar_subtotal()

    def _ao_selecionar_produto(self, escolha: str):
        if escolha in self.mapa_produtos:
            self.produto_selecionado = self.mapa_produtos[escolha]
            preco = self.produto_selecionado["preco"]
            estoque = self.produto_selecionado["estoque"]

            self.lbl_preco_unit.configure(text=formatar_moeda(preco))
            self.lbl_estoque_disp.configure(
                text=f"{estoque} un",
                text_color="#10B981" if estoque > 5 else ("#F59E0B" if estoque > 0 else "#EF4444"),
            )
            self._atualizar_subtotal()
        else:
            self.produto_selecionado = None
            self.lbl_preco_unit.configure(text="R$ 0,00")
            self.lbl_estoque_disp.configure(text="0 un", text_color="#94A3B8")
            self.lbl_subtotal.configure(text="R$ 0,00")

    def _atualizar_subtotal(self):
        if not self.produto_selecionado:
            self.lbl_subtotal.configure(text="R$ 0,00")
            return

        qtd_str = self.entry_qtd.get().strip()
        try:
            qtd = int(qtd_str)
            if qtd <= 0:
                self.lbl_subtotal.configure(text="R$ 0,00")
                return

            subtotal = qtd * self.produto_selecionado["preco"]
            self.lbl_subtotal.configure(text=formatar_moeda(subtotal))
        except ValueError:
            self.lbl_subtotal.configure(text="R$ 0,00")

    def recarregar_dados(self):
        """Atualiza a lista de produtos disponíveis no dropdown e o histórico de vendas."""
        # 1. Carrega produtos disponíveis (com estoque > 0)
        todos_produtos = db.listar_produtos()
        self.produtos_disponiveis = [p for p in todos_produtos if p["estoque"] > 0]
        self.mapa_produtos.clear()

        opcoes = []
        for p in self.produtos_disponiveis:
            chave = f"{p['nome']} (Estoque: {p['estoque']} | {formatar_moeda(p['preco'])})"
            self.mapa_produtos[chave] = p
            opcoes.append(chave)

        if opcoes:
            self.combo_produtos.configure(values=opcoes)
            # Mantém ou reseta a seleção
            if self.produto_selecionado:
                novo_selecionado = None
                for chave, p in self.mapa_produtos.items():
                    if p["id"] == self.produto_selecionado["id"]:
                        novo_selecionado = chave
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
            self.combo_produtos.configure(values=["Nenhum produto com estoque disponível"])
            self.combo_produtos.set("Nenhum produto com estoque disponível")
            self.produto_selecionado = None
            self.lbl_preco_unit.configure(text="R$ 0,00")
            self.lbl_estoque_disp.configure(text="0 un", text_color="#EF4444")
            self.lbl_subtotal.configure(text="R$ 0,00")
            self.btn_confirmar.configure(state="disabled")

        # 2. Atualiza Resumo e Histórico do Dia
        self._recarregar_resumo_e_historico()

    def _recarregar_resumo_e_historico(self):
        resumo = db.obter_resumo_dia()
        self.lbl_fat_hoje.configure(text=formatar_moeda(resumo["total_faturamento"]))
        self.lbl_itens_hoje.configure(text=f"{resumo['total_itens']} un")
        self.lbl_vendas_hoje.configure(text=str(resumo["total_vendas"]))

        # Histórico recente
        for w in self.scroll_historico.winfo_children():
            w.destroy()

        vendas = db.obter_vendas_recentes_do_dia(limite=25)
        if not vendas:
            lbl_vazio = ctk.CTkLabel(
                self.scroll_historico,
                text="Nenhuma venda registrada hoje ainda.",
                font=ctk.CTkFont(size=11, slant="italic"),
                text_color="#64748B",
            )
            lbl_vazio.pack(pady=30)
            return

        for v in vendas:
            self._criar_linha_historico(v)

    def _criar_linha_historico(self, venda: dict):
        linha = ctk.CTkFrame(self.scroll_historico, height=32, fg_color="#182234", corner_radius=6)
        linha.pack(fill="x", pady=2)

        hora_str = venda["data_hora"].split(" ")[-1][:5] if " " in venda["data_hora"] else venda["data_hora"]

        ctk.CTkLabel(linha, text=hora_str, font=ctk.CTkFont(size=10), text_color="#64748B", width=55).pack(side="left", padx=4)
        ctk.CTkLabel(linha, text=venda["produto_nome"], font=ctk.CTkFont(size=11, weight="bold"), text_color="#F1F5F9", anchor="w").pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkLabel(linha, text=f"{venda['quantidade']}x", font=ctk.CTkFont(size=11), text_color="#CBD5E1", width=45).pack(side="left", padx=4)
        ctk.CTkLabel(linha, text=formatar_moeda(venda["valor_total"]), font=ctk.CTkFont(size=11, weight="bold"), text_color="#10B981", width=80, anchor="e").pack(side="left", padx=4)

    def _confirmar_venda(self):
        if not self.produto_selecionado:
            self._mostrar_feedback("Nenhum produto selecionado para venda.", sucesso=False)
            return

        qtd_str = self.entry_qtd.get().strip()
        try:
            quantidade = int(qtd_str)
            if quantidade <= 0:
                raise ValueError
        except ValueError:
            self._mostrar_feedback("Informe uma quantidade válida (mínimo 1 unidade).", sucesso=False)
            return

        # Executa transação segura no banco de dados
        sucesso, msg, info_venda = db.registrar_venda(self.produto_selecionado["id"], quantidade)

        if sucesso:
            self._mostrar_feedback(msg, sucesso=True)
            self.entry_qtd.delete(0, tk.END)
            self.entry_qtd.insert(0, "1")
            self.recarregar_dados()

            if self.on_sale_completed_callback:
                self.on_sale_completed_callback()
        else:
            self._mostrar_feedback(msg, sucesso=False)

    def focar_nova_venda(self):
        """Foca no campo de quantidade para nova venda."""
        self.entry_qtd.focus_set()
        self.entry_qtd.select_range(0, tk.END)

    def focar_historico(self):
        """Destaca o histórico de vendas."""
        if hasattr(self, "scroll_historico"):
            self.scroll_historico.focus_set()
