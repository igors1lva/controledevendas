"""
Módulo de Visualização: Catálogo de Produtos
Arquivo: views/catalog_view.py

Tela dedicada exclusivamente à listagem, pesquisa por nome e código de barras,
filtros rápidos, importação de XML de NF-e, edição e exclusão de produtos em estoque.
"""

import tkinter as tk
from tkinter import messagebox, filedialog
from typing import Callable, Optional, List, Dict, Any
import customtkinter as ctk

import database as db
import theme
import xml_importer
from views.xml_preview_modal import XMLPreviewModal


def formatar_moeda(valor: float) -> str:
    """Formata valor numérico para padrão monetário brasileiro R$ 0,00."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class EditProductModal(ctk.CTkToplevel):
    """Janela modal moderna para edição de produto cadastrado."""

    def __init__(self, parent, produto: dict, on_saved_callback: Callable):
        super().__init__(parent)
        self.produto = produto
        self.on_saved_callback = on_saved_callback

        self.title(f"Editar Produto: {produto['nome']}")
        self.geometry("480x520")
        self.resizable(False, False)
        self.configure(fg_color=theme.MODAL_BG)
        self.transient(parent)
        self.grab_set()

        self.after(10, self._centralizar)
        self._criar_widgets()

    def _centralizar(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _criar_widgets(self):
        container = ctk.CTkFrame(self, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        lbl_titulo = ctk.CTkLabel(
            container,
            text="✏️ Alterar Dados do Produto",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        lbl_titulo.pack(pady=(15, 3))

        lbl_id = ctk.CTkLabel(
            container,
            text=f"ID do Registro: #{self.produto['id']}",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        )
        lbl_id.pack(pady=(0, 12))

        # Código de Barras
        ctk.CTkLabel(container, text="Código de Barras (EAN):", font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=25)
        self.entry_codigo_barras = ctk.CTkEntry(
            container,
            height=34,
            corner_radius=6,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
        )
        cod_atual = self.produto.get("codigo_barras") or ""
        self.entry_codigo_barras.insert(0, str(cod_atual))
        self.entry_codigo_barras.pack(fill="x", padx=25, pady=(2, 8))

        # Nome
        ctk.CTkLabel(container, text="Nome do Produto *:", font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=25)
        self.entry_nome = ctk.CTkEntry(
            container,
            height=34,
            corner_radius=6,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
        )
        self.entry_nome.insert(0, self.produto["nome"])
        self.entry_nome.pack(fill="x", padx=25, pady=(2, 8))

        # Preço de Custo e Preço de Venda
        grid_precos = ctk.CTkFrame(container, fg_color="transparent")
        grid_precos.pack(fill="x", padx=25, pady=(2, 8))

        col_c = ctk.CTkFrame(grid_precos, fg_color="transparent")
        col_c.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkLabel(col_c, text="Preço de Custo (R$):", font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w")
        self.entry_custo = ctk.CTkEntry(
            col_c,
            height=34,
            corner_radius=6,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
        )
        custo_val = self.produto.get("preco_custo", 0.0) or 0.0
        self.entry_custo.insert(0, f"{custo_val:.2f}")
        self.entry_custo.pack(fill="x", pady=(2, 0))

        col_v = ctk.CTkFrame(grid_precos, fg_color="transparent")
        col_v.pack(side="left", fill="x", expand=True, padx=(6, 0))
        ctk.CTkLabel(col_v, text="Preço de Venda (R$) *:", font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w")
        self.entry_preco = ctk.CTkEntry(
            col_v,
            height=34,
            corner_radius=6,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
        )
        self.entry_preco.insert(0, f"{self.produto['preco']:.2f}")
        self.entry_preco.pack(fill="x", pady=(2, 0))

        # Estoque
        ctk.CTkLabel(container, text="Quantidade em Estoque *:", font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=25)
        self.entry_estoque = ctk.CTkEntry(
            container,
            height=34,
            corner_radius=6,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
        )
        self.entry_estoque.insert(0, str(self.produto["estoque"]))
        self.entry_estoque.pack(fill="x", padx=25, pady=(2, 16))

        # Botões
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=(5, 10))

        btn_cancelar = ctk.CTkButton(
            btn_frame,
            text="Cancelar",
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            height=38,
            corner_radius=8,
            command=self.destroy,
        )
        btn_cancelar.pack(side="left", expand=True, fill="x", padx=(0, 6))

        btn_salvar = ctk.CTkButton(
            btn_frame,
            text="Salvar Alterações",
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            height=38,
            corner_radius=8,
            command=self._salvar,
        )
        btn_salvar.pack(side="right", expand=True, fill="x", padx=(6, 0))

    def _salvar(self):
        cod_barras = self.entry_codigo_barras.get().strip()
        nome = self.entry_nome.get().strip()
        custo_str = self.entry_custo.get().strip().replace(",", ".")
        preco_str = self.entry_preco.get().strip().replace(",", ".")
        estoque_str = self.entry_estoque.get().strip()

        if not nome:
            messagebox.showwarning("Aviso", "O nome do produto não pode ficar vazio.", parent=self)
            return

        preco_custo = 0.0
        if custo_str:
            try:
                preco_custo = float(custo_str)
                if preco_custo < 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Aviso", "Preço de custo inválido.", parent=self)
                return

        try:
            preco = float(preco_str)
            if preco <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Aviso", "Preço de venda inválido. Digite um número maior que zero.", parent=self)
            return

        try:
            estoque = int(estoque_str)
            if estoque < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Aviso", "Estoque inválido. Digite um número inteiro maior ou igual a zero.", parent=self)
            return

        sucesso, msg = db.atualizar_produto(
            produto_id=self.produto["id"],
            nome=nome,
            preco=preco,
            estoque=estoque,
            codigo_barras=cod_barras if cod_barras else None,
            preco_custo=preco_custo,
        )
        if sucesso:
            self.on_saved_callback()
            self.destroy()
        else:
            messagebox.showerror("Erro ao Atualizar", msg, parent=self)


class CatalogView(ctk.CTkFrame):
    """Tela dedicada à exibição, busca e gerenciamento do catálogo de produtos."""

    def __init__(self, parent, on_data_changed_callback: Optional[Callable] = None, on_goto_cadastrar: Optional[Callable] = None):
        super().__init__(parent, fg_color="transparent")
        self.on_data_changed_callback = on_data_changed_callback
        self.on_goto_cadastrar = on_goto_cadastrar

        self.filtro_ativo = "todos"  # "todos", "em_estoque", "baixo", "esgotados"
        self._criar_layout()
        self.recarregar_dados()

    def _criar_layout(self):
        # 1. Cabeçalho da Tela
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(16, 12))

        col_tit = ctk.CTkFrame(header_frame, fg_color="transparent")
        col_tit.pack(side="left")

        lbl_titulo = ctk.CTkLabel(
            col_tit,
            text="🏷️ Catálogo & Lista de Produtos",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        lbl_titulo.pack(anchor="w")

        lbl_subtitulo = ctk.CTkLabel(
            col_tit,
            text="Consulte por nome ou código de barras, gerencie preços, importe notas fiscais e controle o estoque.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        )
        lbl_subtitulo.pack(anchor="w")

        # Botões de Ação Superior (Importar XML + Cadastrar Novo)
        col_actions = ctk.CTkFrame(header_frame, fg_color="transparent")
        col_actions.pack(side="right")

        btn_xml = ctk.CTkButton(
            col_actions,
            text="📥 Importar XML de Nota",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=38,
            corner_radius=8,
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            command=self._abrir_importacao_xml,
        )
        btn_xml.pack(side="left", padx=(0, 8))

        if self.on_goto_cadastrar:
            btn_novo = ctk.CTkButton(
                col_actions,
                text="➕ Cadastrar Produto",
                font=ctk.CTkFont(size=12, weight="bold"),
                height=38,
                corner_radius=8,
                fg_color=theme.ACCENT_GREEN,
                hover_color=theme.ACCENT_GREEN_HOVER,
                command=self.on_goto_cadastrar,
            )
            btn_novo.pack(side="left")

        # 2. Card de Métricas e Filtros Rápidos
        filter_card = ctk.CTkFrame(self, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        filter_card.pack(fill="x", padx=24, pady=(0, 12))

        # Linha Superior do Card: Barra de Pesquisa e Botões de Filtro
        top_filter_row = ctk.CTkFrame(filter_card, fg_color="transparent")
        top_filter_row.pack(fill="x", padx=16, pady=12)

        self.entry_busca = ctk.CTkEntry(
            top_filter_row,
            placeholder_text="🔍 Buscar produto por nome ou bipar código de barras...",
            height=38,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
        )
        self.entry_busca.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.entry_busca.bind("<KeyRelease>", lambda event: self.recarregar_dados())

        # Botões de Filtro Rápido (Pills)
        self.btn_filtros = {}
        filtros = [
            ("todos", "Todos"),
            ("em_estoque", "Em Estoque"),
            ("baixo", "Baixo Estoque"),
            ("esgotados", "Esgotados"),
        ]

        pills_frame = ctk.CTkFrame(top_filter_row, fg_color="transparent")
        pills_frame.pack(side="right")

        for fid, rotulo in filtros:
            btn = ctk.CTkButton(
                pills_frame,
                text=rotulo,
                height=32,
                corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=theme.ACCENT_BLUE if fid == "todos" else theme.INNER_CARD_BG,
                text_color=theme.ACCENT_BLUE_TEXT if fid == "todos" else theme.TEXT_SECONDARY,
                hover_color=theme.BTN_SECONDARY_HOVER,
                border_width=1,
                border_color=theme.BORDER_COLOR,
                command=lambda f=fid: self._aplicar_filtro(f),
            )
            btn.pack(side="left", padx=3)
            self.btn_filtros[fid] = btn

        # Linha Inferior do Card: Indicadores
        self.lbl_stats = ctk.CTkLabel(
            filter_card,
            text="Carregando catálogo...",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        )
        self.lbl_stats.pack(anchor="w", padx=16, pady=(0, 10))

        # 3. Card da Tabela de Itens
        table_card = ctk.CTkFrame(self, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        table_card.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        # Cabeçalho da Tabela
        header_grid = ctk.CTkFrame(table_card, height=38, fg_color=theme.INNER_CARD_BG, corner_radius=6, border_width=1, border_color=theme.BORDER_COLOR)
        header_grid.pack(fill="x", padx=16, pady=(12, 6))

        col_configs = [
            ("ID", 45, "center"),
            ("Código / EAN", 130, "w"),
            ("Nome do Produto", 260, "w"),
            ("Custo Unit.", 95, "e"),
            ("Preço Venda", 100, "e"),
            ("Estoque", 85, "center"),
            ("Status", 105, "center"),
            ("Ações", 145, "center"),
        ]

        for nome_col, largura, alinhamento in col_configs:
            lbl = ctk.CTkLabel(
                header_grid,
                text=nome_col,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.TEXT_SECONDARY,
                width=largura,
            )
            if alinhamento == "w":
                lbl.pack(side="left", fill="x" if nome_col == "Nome do Produto" else None, expand=True if nome_col == "Nome do Produto" else False, padx=6)
            else:
                lbl.pack(side="left", padx=6)

        # Scrollable Frame
        self.scroll_frame = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    def _abrir_importacao_xml(self):
        """Abre o diálogo para seleção de XML de NF-e e exibe a pré-visualização."""
        caminho = filedialog.askopenfilename(
            title="Selecionar XML da Nota Fiscal (NF-e / NFC-e)",
            filetypes=[("Arquivos XML da NF-e", "*.xml"), ("Todos os arquivos", "*.*")],
            parent=self,
        )
        if not caminho:
            return

        ok, msg, dados_nota = xml_importer.parsear_xml_nfe(caminho)
        if not ok:
            messagebox.showerror("Erro na Leitura do XML", msg, parent=self)
            return

        XMLPreviewModal(self, dados_nota, on_confirmed_callback=self._apos_importar_xml)

    def _apos_importar_xml(self):
        """Sincroniza o catálogo após importação de produtos de XML."""
        self.recarregar_dados()
        if self.on_data_changed_callback:
            self.on_data_changed_callback()

    def _aplicar_filtro(self, filtro_id: str):
        self.filtro_ativo = filtro_id
        for fid, btn in self.btn_filtros.items():
            if fid == filtro_id:
                btn.configure(fg_color=theme.ACCENT_BLUE, text_color=theme.ACCENT_BLUE_TEXT)
            else:
                btn.configure(fg_color=theme.INNER_CARD_BG, text_color=theme.TEXT_SECONDARY)
        self.recarregar_dados()

    def recarregar_dados(self):
        """Atualiza a lista de produtos com base no termo de busca e no filtro ativo."""
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        termo = self.entry_busca.get().strip() if hasattr(self, "entry_busca") else ""
        todos_produtos = db.listar_produtos(termo)

        # Totais gerais
        total = len(todos_produtos)
        zerados = sum(1 for p in todos_produtos if p["estoque"] == 0)
        baixos = sum(1 for p in todos_produtos if 0 < p["estoque"] <= 5)
        em_estoque = sum(1 for p in todos_produtos if p["estoque"] > 5)

        self.lbl_stats.configure(
            text=f"Total Cadastrado: {total} itens  |  Normal: {em_estoque}  |  Baixo Estoque: {baixos}  |  Esgotados: {zerados}"
        )

        # Filtra de acordo com o pill selecionado
        if self.filtro_ativo == "em_estoque":
            produtos = [p for p in todos_produtos if p["estoque"] > 5]
        elif self.filtro_ativo == "baixo":
            produtos = [p for p in todos_produtos if 0 < p["estoque"] <= 5]
        elif self.filtro_ativo == "esgotados":
            produtos = [p for p in todos_produtos if p["estoque"] == 0]
        else:
            produtos = todos_produtos

        if not produtos:
            lbl_vazio = ctk.CTkLabel(
                self.scroll_frame,
                text="Nenhum produto encontrado correspondente aos filtros atuais.",
                font=ctk.CTkFont(size=13, slant="italic"),
                text_color=theme.TEXT_MUTED,
            )
            lbl_vazio.pack(pady=40)
            return

        for p in produtos:
            self._renderizar_linha_produto(p)

    def _renderizar_linha_produto(self, p: dict):
        row = ctk.CTkFrame(self.scroll_frame, height=44, fg_color=theme.INNER_CARD_BG, corner_radius=6, border_width=1, border_color=theme.BORDER_COLOR)
        row.pack(fill="x", pady=2)

        # ID
        ctk.CTkLabel(row, text=f"#{p['id']}", width=45, font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY).pack(side="left", padx=6)

        # Código de Barras
        cod_txt = p.get("codigo_barras") or "—"
        ctk.CTkLabel(row, text=cod_txt, width=130, font=ctk.CTkFont(size=11), text_color=theme.TEXT_PRIMARY, anchor="w").pack(side="left", padx=6)

        # Nome
        ctk.CTkLabel(row, text=p["nome"], font=ctk.CTkFont(size=12, weight="bold"), text_color=theme.TEXT_PRIMARY, anchor="w").pack(side="left", fill="x", expand=True, padx=6)

        # Preço de Custo
        custo_val = p.get("preco_custo", 0.0) or 0.0
        custo_fmt = formatar_moeda(custo_val) if custo_val > 0 else "—"
        ctk.CTkLabel(row, text=custo_fmt, width=95, font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY, anchor="e").pack(side="left", padx=6)

        # Preço de Venda
        ctk.CTkLabel(row, text=formatar_moeda(p["preco"]), width=100, font=ctk.CTkFont(size=12, weight="bold"), text_color=theme.PRICE_COLOR, anchor="e").pack(side="left", padx=6)

        # Estoque
        ctk.CTkLabel(row, text=f"{p['estoque']} un", width=85, font=ctk.CTkFont(size=12, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left", padx=6)

        # Badge de Status
        if p["estoque"] > 5:
            badge_txt, badge_cor = "🟢 Normal", theme.STOCK_COLOR
        elif p["estoque"] > 0:
            badge_txt, badge_cor = "🟡 Baixo", theme.WARNING_COLOR
        else:
            badge_txt, badge_cor = "🔴 Esgotado", theme.ACCENT_RED

        ctk.CTkLabel(row, text=badge_txt, width=105, font=ctk.CTkFont(size=11, weight="bold"), text_color=badge_cor).pack(side="left", padx=6)

        # Ações
        acoes_frame = ctk.CTkFrame(row, fg_color="transparent", width=145)
        acoes_frame.pack(side="left", padx=6)

        ctk.CTkButton(
            acoes_frame,
            text="✏️ Editar",
            width=65,
            height=28,
            corner_radius=5,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            command=lambda prod=p: self._abrir_modal_edicao(prod),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            acoes_frame,
            text="🗑️ Excluir",
            width=65,
            height=28,
            corner_radius=5,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.ACCENT_RED,
            hover_color=theme.ACCENT_RED_HOVER,
            command=lambda prod=p: self._confirmar_exclusao(prod),
        ).pack(side="left", padx=2)

    def _abrir_modal_edicao(self, produto: dict):
        EditProductModal(self, produto, on_saved_callback=self._apos_salvar_edicao)

    def _apos_salvar_edicao(self):
        self.recarregar_dados()
        if self.on_data_changed_callback:
            self.on_data_changed_callback()

    def _confirmar_exclusao(self, produto: dict):
        confirma = messagebox.askyesno(
            "Confirmar Exclusão",
            f"Tem certeza que deseja excluir o produto '{produto['nome']}'?\nEsta ação não poderá ser desfeita.",
            parent=self,
        )
        if not confirma:
            return

        sucesso, msg = db.excluir_produto(produto["id"])
        if sucesso:
            self.recarregar_dados()
            if self.on_data_changed_callback:
                self.on_data_changed_callback()
        else:
            messagebox.showerror("Erro ao Excluir", msg, parent=self)

    def focar_busca(self):
        """Foca no campo de busca ao entrar na tela."""
        self.entry_busca.focus_set()
        self.entry_busca.select_range(0, tk.END)
