"""
Módulo de Visualização de Inventário (Produtos)
Arquivo: views/inventory_view.py

Responsável pelo cadastro, listagem, busca, edição e exclusão de produtos
em estoque com interface gráfica moderna em CustomTkinter.
"""

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional
import customtkinter as ctk

import database as db


class EditProductModal(ctk.CTkToplevel):
    """Janela modal moderna para edição de produto cadastrado."""

    def __init__(self, parent, produto: dict, on_saved_callback: Callable):
        super().__init__(parent)
        self.produto = produto
        self.on_saved_callback = on_saved_callback

        self.title(f"Editar Produto: {produto['nome']}")
        self.geometry("450x420")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Centraliza a janela modal em relação à aplicação principal
        self.after(10, self._centralizar)

        self._criar_widgets()

    def _centralizar(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _criar_widgets(self):
        container = ctk.CTkFrame(self, corner_radius=12, fg_color="#1E293B")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Cabeçalho
        lbl_titulo = ctk.CTkLabel(
            container,
            text="✏️ Alterar Dados do Produto",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#F8FAFC",
        )
        lbl_titulo.pack(pady=(15, 5))

        lbl_id = ctk.CTkLabel(
            container,
            text=f"ID do Registro: #{self.produto['id']}",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8",
        )
        lbl_id.pack(pady=(0, 15))

        # Campo: Nome
        ctk.CTkLabel(
            container,
            text="Nome do Produto:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#E2E8F0",
        ).pack(anchor="w", padx=25)

        self.entry_nome = ctk.CTkEntry(
            container,
            height=36,
            corner_radius=8,
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.entry_nome.insert(0, self.produto["nome"])
        self.entry_nome.pack(fill="x", padx=25, pady=(4, 12))

        # Campo: Preço Unitário
        ctk.CTkLabel(
            container,
            text="Preço Unitário (R$):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#E2E8F0",
        ).pack(anchor="w", padx=25)

        self.entry_preco = ctk.CTkEntry(
            container,
            height=36,
            corner_radius=8,
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.entry_preco.insert(0, f"{self.produto['preco']:.2f}")
        self.entry_preco.pack(fill="x", padx=25, pady=(4, 12))

        # Campo: Estoque
        ctk.CTkLabel(
            container,
            text="Quantidade em Estoque:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#E2E8F0",
        ).pack(anchor="w", padx=25)

        self.entry_estoque = ctk.CTkEntry(
            container,
            height=36,
            corner_radius=8,
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.entry_estoque.insert(0, str(self.produto["estoque"]))
        self.entry_estoque.pack(fill="x", padx=25, pady=(4, 18))

        # Botões de Ação
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=(5, 10))

        btn_cancelar = ctk.CTkButton(
            btn_frame,
            text="Cancelar",
            fg_color="#334155",
            hover_color="#475569",
            height=38,
            corner_radius=8,
            command=self.destroy,
        )
        btn_cancelar.pack(side="left", expand=True, fill="x", padx=(0, 6))

        btn_salvar = ctk.CTkButton(
            btn_frame,
            text="Salvar Alterações",
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            height=38,
            corner_radius=8,
            command=self._salvar,
        )
        btn_salvar.pack(side="right", expand=True, fill="x", padx=(6, 0))

    def _salvar(self):
        nome = self.entry_nome.get().strip()
        preco_str = self.entry_preco.get().strip().replace(",", ".")
        estoque_str = self.entry_estoque.get().strip()

        if not nome:
            messagebox.showwarning("Aviso", "O nome do produto não pode ficar vazio.", parent=self)
            return

        try:
            preco = float(preco_str)
            if preco <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Aviso", "Preço inválido. Digite um valor numérico maior que zero (ex: 49.90).", parent=self)
            return

        try:
            estoque = int(estoque_str)
            if estoque < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Aviso", "Quantidade de estoque inválida. Digite um número inteiro maior ou igual a zero.", parent=self)
            return

        sucesso, msg = db.atualizar_produto(self.produto["id"], nome, preco, estoque)
        if sucesso:
            self.on_saved_callback()
            self.destroy()
        else:
            messagebox.showerror("Erro", msg, parent=self)


class InventoryView(ctk.CTkFrame):
    """Painel principal do Módulo de Inventário (Cadastro, Gestão e Listagem de Produtos)."""

    def __init__(self, parent, on_data_changed_callback: Optional[Callable] = None):
        super().__init__(parent, fg_color="transparent")
        self.on_data_changed_callback = on_data_changed_callback

        self._criar_layout()
        self.recarregar_produtos()

    def _criar_layout(self):
        # 1. Cabeçalho da Seção
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(16, 12))

        lbl_titulo = ctk.CTkLabel(
            header_frame,
            text="📦 Gestão de Inventário e Produtos",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC",
        )
        lbl_titulo.pack(anchor="w")

        lbl_subtitulo = ctk.CTkLabel(
            header_frame,
            text="Cadastre novos produtos, controle estoque em tempo real e edite preços.",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8",
        )
        lbl_subtitulo.pack(anchor="w")

        # 2. Formulário de Cadastro (Card Superior)
        form_card = ctk.CTkFrame(self, corner_radius=12, fg_color="#1E293B", border_width=1, border_color="#334155")
        form_card.pack(fill="x", padx=24, pady=(0, 16))

        form_title = ctk.CTkLabel(
            form_card,
            text="➕ Cadastrar Novo Produto",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#E2E8F0",
        )
        form_title.pack(anchor="w", padx=20, pady=(14, 10))

        # Linha de Inputs do Formulário
        inputs_frame = ctk.CTkFrame(form_card, fg_color="transparent")
        inputs_frame.pack(fill="x", padx=20, pady=(0, 14))

        # Nome do produto
        col_nome = ctk.CTkFrame(inputs_frame, fg_color="transparent")
        col_nome.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkLabel(col_nome, text="Nome do Produto *", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94A3B8").pack(anchor="w")
        self.entry_nome = ctk.CTkEntry(
            col_nome,
            placeholder_text="Ex: Mouse Gamer Óptico",
            height=36,
            corner_radius=8,
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.entry_nome.pack(fill="x", pady=(4, 0))

        # Preço Unitário
        col_preco = ctk.CTkFrame(inputs_frame, fg_color="transparent")
        col_preco.pack(side="left", padx=(0, 10), fill="x", expand=False)
        ctk.CTkLabel(col_preco, text="Preço Unitário (R$) *", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94A3B8").pack(anchor="w")
        self.entry_preco = ctk.CTkEntry(
            col_preco,
            placeholder_text="Ex: 89.90",
            width=160,
            height=36,
            corner_radius=8,
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.entry_preco.pack(fill="x", pady=(4, 0))

        # Quantidade em Estoque
        col_estoque = ctk.CTkFrame(inputs_frame, fg_color="transparent")
        col_estoque.pack(side="left", padx=(0, 10), fill="x", expand=False)
        ctk.CTkLabel(col_estoque, text="Estoque Inicial *", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94A3B8").pack(anchor="w")
        self.entry_estoque = ctk.CTkEntry(
            col_estoque,
            placeholder_text="Ex: 20",
            width=130,
            height=36,
            corner_radius=8,
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.entry_estoque.pack(fill="x", pady=(4, 0))

        # Botão Salvar
        col_btn = ctk.CTkFrame(inputs_frame, fg_color="transparent")
        col_btn.pack(side="left", fill="x", expand=False)
        ctk.CTkLabel(col_btn, text=" ", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.btn_cadastrar = ctk.CTkButton(
            col_btn,
            text="Adicionar Produto",
            fg_color="#10B981",
            hover_color="#059669",
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._adicionar_produto,
        )
        self.btn_cadastrar.pack(pady=(4, 0))

        # Banner de Feedback / Mensagens
        self.lbl_feedback = ctk.CTkLabel(
            form_card,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#10B981",
        )
        self.lbl_feedback.pack(anchor="w", padx=20, pady=(0, 8))

        # 3. Card da Tabela de Produtos
        table_card = ctk.CTkFrame(self, corner_radius=12, fg_color="#1E293B", border_width=1, border_color="#334155")
        table_card.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        # Barra de Pesquisa e Filtro
        search_frame = ctk.CTkFrame(table_card, fg_color="transparent")
        search_frame.pack(fill="x", padx=16, pady=12)

        self.entry_busca = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Buscar produto por nome...",
            height=36,
            corner_radius=8,
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.entry_busca.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_busca.bind("<KeyRelease>", lambda event: self.recarregar_produtos())

        btn_atualizar = ctk.CTkButton(
            search_frame,
            text="Atualizar Lista",
            width=120,
            height=36,
            corner_radius=8,
            fg_color="#334155",
            hover_color="#475569",
            command=self.recarregar_produtos,
        )
        btn_atualizar.pack(side="right")

        self.lbl_totais = ctk.CTkLabel(
            search_frame,
            text="Carregando produtos...",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8",
        )
        self.lbl_totais.pack(side="right", padx=16)

        # Cabeçalho da Tabela
        header_grid = ctk.CTkFrame(table_card, height=36, fg_color="#0F172A", corner_radius=6)
        header_grid.pack(fill="x", padx=16, pady=(0, 6))

        col_configs = [
            ("ID", 50, "center"),
            ("Nome do Produto", 300, "w"),
            ("Preço Unitário", 120, "e"),
            ("Estoque", 100, "center"),
            ("Status", 120, "center"),
            ("Ações", 160, "center"),
        ]

        for nome_col, largura, alinhamento in col_configs:
            lbl = ctk.CTkLabel(
                header_grid,
                text=nome_col,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#94A3B8",
                width=largura,
            )
            if alinhamento == "w":
                lbl.pack(side="left", fill="x", expand=True, padx=8)
            else:
                lbl.pack(side="left", padx=6)

        # Área de Rolagem para os Registros
        self.scroll_frame = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    def _mostrar_feedback(self, mensagem: str, sucesso: bool = True):
        cor = "#10B981" if sucesso else "#EF4444"
        self.lbl_feedback.configure(text=mensagem, text_color=cor)
        self.after(4000, lambda: self.lbl_feedback.configure(text=""))

    def _adicionar_produto(self):
        nome = self.entry_nome.get().strip()
        preco_str = self.entry_preco.get().strip().replace(",", ".")
        estoque_str = self.entry_estoque.get().strip()

        if not nome:
            self._mostrar_feedback("Por favor, preencha o nome do produto.", sucesso=False)
            return

        try:
            preco = float(preco_str)
            if preco <= 0:
                raise ValueError
        except ValueError:
            self._mostrar_feedback("Preço inválido. Digite um valor numérico positivo (ex: 29.90).", sucesso=False)
            return

        try:
            estoque = int(estoque_str)
            if estoque < 0:
                raise ValueError
        except ValueError:
            self._mostrar_feedback("Estoque inválido. Digite um número inteiro maior ou igual a zero.", sucesso=False)
            return

        sucesso, msg = db.adicionar_produto(nome, preco, estoque)
        self._mostrar_feedback(msg, sucesso=sucesso)

        if sucesso:
            self.entry_nome.delete(0, tk.END)
            self.entry_preco.delete(0, tk.END)
            self.entry_estoque.delete(0, tk.END)
            self.recarregar_produtos()
            if self.on_data_changed_callback:
                self.on_data_changed_callback()

    def recarregar_produtos(self):
        """Atualiza a lista visual de produtos com base no banco de dados."""
        # Limpa itens anteriores do scroll frame
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        termo = self.entry_busca.get().strip() if hasattr(self, "entry_busca") else ""
        produtos = db.listar_produtos(termo)

        total_prods = len(produtos)
        zerados = sum(1 for p in produtos if p["estoque"] == 0)
        baixo_estoque = sum(1 for p in produtos if 0 < p["estoque"] <= 5)

        self.lbl_totais.configure(
            text=f"Total: {total_prods} itens | Esgotados: {zerados} | Baixo Estoque: {baixo_estoque}"
        )

        if not produtos:
            msg_vazio = (
                "Nenhum produto cadastrado no momento."
                if not termo
                else f"Nenhum produto encontrado para '{termo}'."
            )
            lbl_vazio = ctk.CTkLabel(
                self.scroll_frame,
                text=msg_vazio,
                font=ctk.CTkFont(size=13, slant="italic"),
                text_color="#64748B",
            )
            lbl_vazio.pack(pady=40)
            return

        for p in produtos:
            self._criar_linha_produto(p)

    def _criar_linha_produto(self, produto: dict):
        linha = ctk.CTkFrame(self.scroll_frame, height=44, fg_color="#182234", corner_radius=6)
        linha.pack(fill="x", pady=2)

        # ID
        ctk.CTkLabel(
            linha,
            text=f"#{produto['id']}",
            font=ctk.CTkFont(size=11),
            text_color="#64748B",
            width=50,
        ).pack(side="left", padx=6)

        # Nome
        ctk.CTkLabel(
            linha,
            text=produto["nome"],
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#F1F5F9",
            anchor="w",
            width=300,
        ).pack(side="left", fill="x", expand=True, padx=8)

        # Preço
        ctk.CTkLabel(
            linha,
            text=f"R$ {produto['preco']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            font=ctk.CTkFont(size=12),
            text_color="#38BDF8",
            width=120,
            anchor="e",
        ).pack(side="left", padx=6)

        # Estoque
        ctk.CTkLabel(
            linha,
            text=f"{produto['estoque']} un",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#F8FAFC",
            width=100,
        ).pack(side="left", padx=6)

        # Status Badge
        estoque = produto["estoque"]
        if estoque == 0:
            badge_cor = "#EF4444"
            badge_texto = "ESGOTADO"
        elif estoque <= 5:
            badge_cor = "#F59E0B"
            badge_texto = "BAIXO"
        else:
            badge_cor = "#10B981"
            badge_texto = "EM ESTOQUE"

        badge_frame = ctk.CTkFrame(linha, fg_color=badge_cor, corner_radius=10, width=95, height=22)
        badge_frame.pack_propagate(False)
        badge_frame.pack(side="left", padx=12)
        ctk.CTkLabel(
            badge_frame,
            text=badge_texto,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#FFFFFF",
        ).pack(expand=True)

        # Botões de Ações (Editar e Excluir)
        acoes_frame = ctk.CTkFrame(linha, fg_color="transparent", width=160)
        acoes_frame.pack(side="left", padx=6)

        btn_editar = ctk.CTkButton(
            acoes_frame,
            text="Editar",
            width=65,
            height=26,
            corner_radius=6,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            font=ctk.CTkFont(size=11),
            command=lambda p=produto: self._abrir_modal_editar(p),
        )
        btn_editar.pack(side="left", padx=4)

        btn_excluir = ctk.CTkButton(
            acoes_frame,
            text="Excluir",
            width=65,
            height=26,
            corner_radius=6,
            fg_color="#DC2626",
            hover_color="#B91C1C",
            font=ctk.CTkFont(size=11),
            command=lambda p=produto: self._confirmar_exclusao(p),
        )
        btn_excluir.pack(side="left", padx=4)

    def _abrir_modal_editar(self, produto: dict):
        EditProductModal(self.winfo_toplevel(), produto, on_saved_callback=self._apos_salvar_edicao)

    def _apos_salvar_edicao(self):
        self.recarregar_produtos()
        self._mostrar_feedback("Produto atualizado com sucesso!", sucesso=True)
        if self.on_data_changed_callback:
            self.on_data_changed_callback()

    def _confirmar_exclusao(self, produto: dict):
        resposta = messagebox.askyesno(
            "Confirmar Exclusão",
            f"Deseja realmente excluir o produto '{produto['nome']}'?\nEsta ação não poderá ser desfeita.",
            parent=self.winfo_toplevel(),
        )
        if resposta:
            sucesso, msg = db.excluir_produto(produto["id"])
            if sucesso:
                self._mostrar_feedback(msg, sucesso=True)
                self.recarregar_produtos()
                if self.on_data_changed_callback:
                    self.on_data_changed_callback()
            else:
                messagebox.showwarning("Aviso", msg, parent=self.winfo_toplevel())

    def focar_cadastro(self):
        """Foca no campo de cadastro de novo produto."""
        self.entry_nome.focus_set()

    def focar_busca(self):
        """Foca no campo de busca do catálogo."""
        self.entry_busca.focus_set()
