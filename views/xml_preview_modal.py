"""
Modal de Pré-visualização e Conferência de XML de NF-e
Arquivo: views/xml_preview_modal.py

Exibe interface moderna para conferência dos produtos extraídos da nota fiscal,
identificando automaticamente itens novos vs reposição de estoque, e permitindo
a gravação atômica em lote no inventário.
"""

import tkinter as tk
from tkinter import messagebox
from typing import Dict, Any, Callable, List
import customtkinter as ctk

import database as db
import theme


def formatar_moeda(valor: float) -> str:
    """Formata valor numérico para padrão monetário brasileiro R$ 0,00."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class XMLPreviewModal(ctk.CTkToplevel):
    """Janela modal para conferência de produtos de NF-e antes da gravação."""

    def __init__(self, parent, dados_nota: Dict[str, Any], on_confirmed_callback: Callable):
        super().__init__(parent)
        self.dados_nota = dados_nota
        self.on_confirmed_callback = on_confirmed_callback
        self.itens_widgets: List[Dict[str, Any]] = []

        self.title(f"Importação de NF-e: Nota #{self.dados_nota.get('numero_nf', 'S/N')}")
        self.geometry("960x650")
        self.minsize(850, 550)
        self.configure(fg_color=theme.MODAL_BG)
        self.transient(parent)
        self.grab_set()

        self.after(20, self._centralizar)
        self._criar_layout()

    def _centralizar(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _criar_layout(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # 1. Header do Fornecedor e Nota
        header_card = ctk.CTkFrame(container, corner_radius=10, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        header_card.pack(fill="x", pady=(0, 14))

        top_info = ctk.CTkFrame(header_card, fg_color="transparent")
        top_info.pack(fill="x", padx=18, pady=14)

        col_left = ctk.CTkFrame(top_info, fg_color="transparent")
        col_left.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            col_left,
            text=f"📦 Fornecedor: {self.dados_nota.get('emitente_nome', 'Não Informado')}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        cnpj_txt = f"CNPJ: {self.dados_nota.get('emitente_cnpj', 'N/D')}" if self.dados_nota.get('emitente_cnpj') else ""
        sub_info = f"Nota Fiscal Nº {self.dados_nota.get('numero_nf')} (Série {self.dados_nota.get('serie', '1')})  •  {cnpj_txt}"
        ctk.CTkLabel(
            col_left,
            text=sub_info,
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        col_right = ctk.CTkFrame(top_info, fg_color="transparent")
        col_right.pack(side="right")

        badge_tot = ctk.CTkFrame(col_right, fg_color=theme.INNER_CARD_BG, corner_radius=8, border_width=1, border_color=theme.BORDER_COLOR)
        badge_tot.pack(side="right")
        ctk.CTkLabel(badge_tot, text="VALOR TOTAL DA NOTA", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(padx=12, pady=(6, 1))
        ctk.CTkLabel(
            badge_tot,
            text=formatar_moeda(self.dados_nota.get("valor_total", 0.0)),
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.PRICE_COLOR,
        ).pack(padx=12, pady=(0, 6))

        # 2. Cabeçalho da Tabela de Itens
        tbl_header = ctk.CTkFrame(container, height=36, corner_radius=6, fg_color=theme.INNER_CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        tbl_header.pack(fill="x", pady=(0, 4))
        tbl_header.pack_propagate(False)

        col_defs = [
            ("Código / Barras", 150),
            ("Descrição da Mercadoria", 280),
            ("Qtd", 60),
            ("Custo Unit.", 95),
            ("Preço Venda (R$)", 125),
            ("Ação Prevista", 140),
        ]

        for tit, w in col_defs:
            lbl = ctk.CTkLabel(
                tbl_header,
                text=tit,
                width=w,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.TEXT_SECONDARY,
                anchor="w",
            )
            lbl.pack(side="left", padx=8)

        # 3. Lista Scrollável com os Itens do XML
        scroll_itens = ctk.CTkScrollableFrame(container, fg_color=theme.CARD_BG, corner_radius=8, border_width=1, border_color=theme.BORDER_COLOR)
        scroll_itens.pack(fill="both", expand=True, pady=(0, 14))

        itens = self.dados_nota.get("itens", [])

        for it in itens:
            row_frame = ctk.CTkFrame(scroll_itens, height=44, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)

            cod_barras = it.get("codigo_barras") or it.get("codigo_fornecedor") or "SEM CÓDIGO"

            # Verifica no banco se já existe
            prod_existente = None
            if it.get("codigo_barras"):
                prod_existente = db.obter_produto_por_codigo_barras(it["codigo_barras"])
            if not prod_existente and it.get("nome"):
                # Busca por nome
                prods_nome = db.listar_produtos(it["nome"])
                for p in prods_nome:
                    if p["nome"].strip().lower() == it["nome"].strip().lower():
                        prod_existente = p
                        break

            # Coluna 1: Código de Barras
            ctk.CTkLabel(
                row_frame,
                text=cod_barras,
                width=150,
                font=ctk.CTkFont(size=11),
                text_color=theme.TEXT_PRIMARY,
                anchor="w",
            ).pack(side="left", padx=8)

            # Coluna 2: Nome do Produto
            ctk.CTkLabel(
                row_frame,
                text=it.get("nome", "Item"),
                width=280,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.TEXT_PRIMARY,
                anchor="w",
            ).pack(side="left", padx=8)

            # Coluna 3: Quantidade
            ctk.CTkLabel(
                row_frame,
                text=f"{it.get('quantidade', 0)} un",
                width=60,
                font=ctk.CTkFont(size=11),
                text_color=theme.STOCK_COLOR,
                anchor="w",
            ).pack(side="left", padx=8)

            # Coluna 4: Preço de Custo
            ctk.CTkLabel(
                row_frame,
                text=formatar_moeda(it.get("preco_custo", 0.0)),
                width=95,
                font=ctk.CTkFont(size=11),
                text_color=theme.TEXT_SECONDARY,
                anchor="w",
            ).pack(side="left", padx=8)

            # Coluna 5: Preço de Venda (Editável)
            preco_sug = prod_existente["preco"] if prod_existente else it.get("preco_venda_sugerido", 0.0)
            entry_venda = ctk.CTkEntry(
                row_frame,
                width=110,
                height=30,
                corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=theme.ENTRY_BG,
                border_color=theme.ENTRY_BORDER,
                text_color=theme.ENTRY_TEXT,
            )
            entry_venda.insert(0, f"{preco_sug:.2f}")
            entry_venda.pack(side="left", padx=8)

            # Coluna 6: Ação Prevista
            if prod_existente:
                badge_acao = ctk.CTkLabel(
                    row_frame,
                    text="🔄 Repor Estoque",
                    width=130,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#38BDF8",
                    anchor="w",
                )
            else:
                badge_acao = ctk.CTkLabel(
                    row_frame,
                    text="✨ Novo Produto",
                    width=130,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#10B981",
                    anchor="w",
                )
            badge_acao.pack(side="left", padx=8)

            self.itens_widgets.append({
                "item_data": it,
                "entry_venda": entry_venda,
                "ja_existe": bool(prod_existente),
            })

            # Divisor sutil
            ctk.CTkFrame(scroll_itens, height=1, fg_color=theme.BORDER_COLOR).pack(fill="x", padx=4)

        # 4. Rodapé com Ações
        footer = ctk.CTkFrame(container, fg_color="transparent")
        footer.pack(fill="x")

        lbl_resumo = ctk.CTkLabel(
            footer,
            text=f"Total de {len(itens)} item(ns) pronto(s) para importação.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        )
        lbl_resumo.pack(side="left")

        btn_cancelar = ctk.CTkButton(
            footer,
            text="Cancelar",
            width=110,
            height=38,
            corner_radius=8,
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self.destroy,
        )
        btn_cancelar.pack(side="right", padx=(10, 0))

        btn_confirmar = ctk.CTkButton(
            footer,
            text=f"✔ Confirmar Importação ({len(itens)} Itens)",
            width=240,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            command=self._confirmar_importacao,
        )
        btn_confirmar.pack(side="right")

    def _confirmar_importacao(self):
        """Grava os produtos do XML no banco SQLite de forma transacional."""
        novos_count = 0
        repostos_count = 0
        erros_count = 0

        for row in self.itens_widgets:
            it = row["item_data"]
            entry = row["entry_venda"]

            # Lê o preço de venda digitado pelo operador
            try:
                preco_venda = float(entry.get().strip().replace(",", "."))
                if preco_venda <= 0:
                    preco_venda = it["preco_custo"] * 1.5
            except ValueError:
                preco_venda = it["preco_custo"] * 1.5

            cod_barras = it.get("codigo_barras") or it.get("codigo_fornecedor")

            sucesso, msg, acao = db.repor_ou_cadastrar_produto_xml(
                codigo_barras=cod_barras,
                nome=it["nome"],
                qtd=it["quantidade"],
                preco_custo=it["preco_custo"],
                preco_venda_sugerido=preco_venda,
            )

            if sucesso:
                if acao == "NOVO":
                    novos_count += 1
                else:
                    repostos_count += 1
            else:
                erros_count += 1

        msg_final = (
            f"Importação da NF-e concluída com sucesso!\n\n"
            f"• {novos_count} novo(s) produto(s) cadastrado(s)\n"
            f"• {repostos_count} produto(s) com estoque reposto"
        )
        if erros_count > 0:
            msg_final += f"\n• {erros_count} item(ns) apresentaram inconsistência."

        messagebox.showinfo("Importação Concluída", msg_final, parent=self)

        if self.on_confirmed_callback:
            self.on_confirmed_callback()

        self.destroy()
