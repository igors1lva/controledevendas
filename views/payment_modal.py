"""
Modal de Finalização de Pagamento e Conclusão de Venda (F2)
Arquivo: views/payment_modal.py

Janela modal flutuante de alta ergonomia e velocidade para o operador do PDV:
- Apresenta o Valor Total da Venda em destaque
- Seletor rápido de Forma de Pagamento (Dinheiro, Pix, Débito, Crédito)
- Calculadora de Troco automática com botões de cédulas rápidas
- Dados da Maquininha (Bandeira e NSU) para cartões
- Campo de CPF do Cliente na Nota (Opcional com máscara)
- Atalho F2 para confirmação imediata e Esc para cancelamento/retorno
"""

import re
from typing import Callable, Dict, Any, List, Optional
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

import theme


def formatar_moeda(valor: float) -> str:
    """Formata valor numérico para padrão monetário brasileiro R$ 0,00."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class PaymentModal(ctk.CTkToplevel):
    """Janela modal para definição de pagamento, troco e CPF antes da emissão final da venda."""

    def __init__(
        self,
        parent,
        valor_total: float,
        itens: List[Dict[str, Any]],
        on_confirm_callback: Callable[[Dict[str, Any]], None],
    ):
        super().__init__(parent)
        self.parent = parent
        self.valor_total = float(valor_total)
        self.itens = itens
        self.on_confirm_callback = on_confirm_callback

        self.forma_selecionada = "DINHEIRO"
        self.botoes_pgto: Dict[str, ctk.CTkButton] = {}

        self.title("💳 Finalização da Venda & Pagamento (F2)")
        self.geometry("640x720")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_COLOR)

        # Transparência e foco modal exclusivo
        self.transient(parent)
        self.grab_set()

        self._criar_layout()
        self._centralizar_janela()

        # Vincula atalhos de teclado da janela modal
        self.bind("<F2>", self._ao_pressionar_f2)
        self.bind("<Escape>", lambda e: self._cancelar())
        self.bind("<Return>", self._ao_teclar_enter)
        self.bind("<KP_Enter>", self._ao_teclar_enter)

        # Foco inicial no campo de valor recebido
        self.after(150, self._focar_campo_inicial)

    def _centralizar_janela(self):
        """Posiciona a janela modal no centro absoluto da tela em qualquer resolução."""
        theme.centralizar_toplevel(self, 640, 700)

    def _criar_layout(self):
        # 1. Cabeçalho da Modal
        head_frame = ctk.CTkFrame(self, fg_color=theme.CARD_BG, corner_radius=0, height=56)
        head_frame.pack(fill="x")
        head_frame.pack_propagate(False)

        col_tit = ctk.CTkFrame(head_frame, fg_color="transparent")
        col_tit.pack(side="left", padx=20, pady=8)

        ctk.CTkLabel(
            col_tit,
            text="💳 Finalização da Venda",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            col_tit,
            text="Defina a forma de pagamento e confirme para emitir a venda",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w")

        # Container Principal com espaçamento
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(12, 16))

        # 2. Card de Valor Total da Venda
        card_total = ctk.CTkFrame(
            body,
            corner_radius=10,
            fg_color=theme.INNER_CARD_BG,
            border_width=2,
            border_color=theme.ACCENT_BLUE,
        )
        card_total.pack(fill="x", pady=(0, 10))

        inner_tot = ctk.CTkFrame(card_total, fg_color="transparent")
        inner_tot.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(
            inner_tot,
            text="TOTAL A PAGAR",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w")

        self.lbl_valor_total = ctk.CTkLabel(
            inner_tot,
            text=formatar_moeda(self.valor_total),
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=theme.STOCK_COLOR[1],
        )
        self.lbl_valor_total.pack(anchor="w", pady=(2, 0))

        # Resumo de itens
        qtd_total_itens = sum(it.get("quantidade", 1) for it in self.itens) if self.itens else 1
        desc_itens = f"{len(self.itens)} produto(s) no carrinho ({qtd_total_itens} un)" if len(self.itens) > 1 else (
            f"1 produto ({self.itens[0].get('produto_nome', 'Item')} - {self.itens[0].get('quantidade', 1)} un)" if self.itens else "Venda direta"
        )
        ctk.CTkLabel(
            inner_tot,
            text=desc_itens,
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        # 3. Seletor de Forma de Pagamento
        ctk.CTkLabel(
            body,
            text="Forma de Pagamento:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(2, 4))

        pills_frame = ctk.CTkFrame(body, fg_color="transparent")
        pills_frame.pack(fill="x", pady=(0, 12))

        opcoes = [
            ("DINHEIRO", "💵 Dinheiro"),
            ("PIX", "📱 Pix"),
            ("CARTAO_DEBITO", "💳 Débito"),
            ("CARTAO_CREDITO", "💳 Crédito"),
        ]

        for cod, rot in opcoes:
            btn = ctk.CTkButton(
                pills_frame,
                text=rot,
                height=42,
                corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=theme.ACCENT_BLUE if cod == self.forma_selecionada else theme.INNER_CARD_BG,
                text_color="#FFFFFF" if cod == self.forma_selecionada else theme.TEXT_SECONDARY,
                hover_color=theme.ACCENT_BLUE_HOVER,
                border_width=1,
                border_color=theme.BORDER_COLOR,
                command=lambda c=cod: self._selecionar_forma(c),
            )
            btn.pack(side="left", padx=4, expand=True, fill="both")
            self.botoes_pgto[cod] = btn

        # 4. Container de Conteúdo Dinâmico por Forma de Pagamento
        self.container_dinamico = ctk.CTkFrame(body, fg_color="transparent")
        self.container_dinamico.pack(fill="x", pady=(0, 10))

        # 4.1 Painel Dinheiro (Calculadora de Troco)
        self.painel_dinheiro = ctk.CTkFrame(
            self.container_dinamico,
            corner_radius=10,
            fg_color=theme.INNER_CARD_BG,
            border_width=1,
            border_color=theme.BORDER_COLOR,
        )

        head_d = ctk.CTkFrame(self.painel_dinheiro, fg_color="transparent")
        head_d.pack(fill="x", padx=16, pady=(10, 4))

        ctk.CTkLabel(
            head_d,
            text="💵 Dinheiro Físico & Cálculo de Troco",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        # Cédulas Rápidas
        pills_cedulas = ctk.CTkFrame(self.painel_dinheiro, fg_color="transparent")
        pills_cedulas.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkButton(
            pills_cedulas,
            text="Exato",
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.CARD_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.TEXT_PRIMARY,
            border_width=1,
            border_color=theme.BORDER_COLOR,
            command=self._definir_valor_exato,
        ).pack(side="left", padx=2, expand=True, fill="x")

        for val_c in [10, 20, 50, 100, 200]:
            ctk.CTkButton(
                pills_cedulas,
                text=f"R$ {val_c}",
                height=30,
                corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=theme.CARD_BG,
                hover_color=theme.BTN_SECONDARY_HOVER,
                text_color=theme.TEXT_SECONDARY,
                border_width=1,
                border_color=theme.BORDER_COLOR,
                command=lambda v=val_c: self._definir_cedula(v),
            ).pack(side="left", padx=2, expand=True, fill="x")

        # Grid: Valor Recebido e Troco
        grid_d = ctk.CTkFrame(self.painel_dinheiro, fg_color="transparent")
        grid_d.pack(fill="x", padx=16, pady=(0, 8))

        col_rec = ctk.CTkFrame(grid_d, fg_color="transparent")
        col_rec.pack(side="left", fill="both", expand=True, padx=(0, 6))

        ctk.CTkLabel(
            col_rec,
            text="Valor Recebido (R$):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, 2))

        self.entry_recebido = ctk.CTkEntry(
            col_rec,
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=15, weight="bold"),
            placeholder_text="0,00",
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
        )
        self.entry_recebido.pack(fill="x")
        self.entry_recebido.bind("<KeyRelease>", lambda e: self._ao_digitar_recebido())

        col_trc = ctk.CTkFrame(grid_d, fg_color="transparent")
        col_trc.pack(side="right", fill="both", expand=True, padx=(6, 0))

        ctk.CTkLabel(
            col_trc,
            text="Troco a Devolver (R$):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, 2))

        self.entry_troco = ctk.CTkEntry(
            col_trc,
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=15, weight="bold"),
            placeholder_text="0,00",
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.STOCK_COLOR[1],
        )
        self.entry_troco.pack(fill="x")

        self.lbl_status_troco = ctk.CTkLabel(
            self.painel_dinheiro,
            text="Aguardando valor recebido...",
            font=ctk.CTkFont(size=10),
            text_color=theme.TEXT_MUTED,
        )
        self.lbl_status_troco.pack(fill="x", padx=16, pady=(2, 8))

        # 4.2 Painel Digital / Cartão / Pix
        self.painel_digital = ctk.CTkFrame(
            self.container_dinamico,
            corner_radius=10,
            fg_color=theme.INNER_CARD_BG,
            border_width=1,
            border_color=theme.BORDER_COLOR,
        )

        self.lbl_digital_titulo = ctk.CTkLabel(
            self.painel_digital,
            text="💳 Maquininha de Cartão (POS / TEF)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self.lbl_digital_titulo.pack(anchor="w", padx=16, pady=(10, 2))

        self.lbl_digital_info = ctk.CTkLabel(
            self.painel_digital,
            text="Transação direta • Sem necessidade de troco.",
            font=ctk.CTkFont(size=11),
            text_color=theme.STOCK_COLOR[1],
        )
        self.lbl_digital_info.pack(anchor="w", padx=16, pady=(0, 8))

        self.frame_campos_cartao = ctk.CTkFrame(self.painel_digital, fg_color="transparent")
        self.frame_campos_cartao.pack(fill="x", padx=16, pady=(0, 10))

        col_band = ctk.CTkFrame(self.frame_campos_cartao, fg_color="transparent")
        col_band.pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkLabel(col_band, text="Bandeira do Cartão:", font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(anchor="w", pady=(0, 2))
        self.combo_bandeira = ctk.CTkComboBox(
            col_band,
            values=["Mastercard", "Visa", "Elo", "Hipercard", "American Express", "Outra"],
            height=34,
            corner_radius=6,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            button_color=theme.ACCENT_BLUE,
            font=ctk.CTkFont(size=11),
        )
        self.combo_bandeira.pack(fill="x")
        self.combo_bandeira.set("Mastercard")

        col_nsu = ctk.CTkFrame(self.frame_campos_cartao, fg_color="transparent")
        col_nsu.pack(side="right", fill="x", expand=True, padx=(6, 0))

        ctk.CTkLabel(col_nsu, text="NSU / Autorização (Opcional):", font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(anchor="w", pady=(0, 2))
        self.entry_nsu = ctk.CTkEntry(
            col_nsu,
            height=34,
            corner_radius=6,
            placeholder_text="Ex: 089124",
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            font=ctk.CTkFont(size=11),
        )
        self.entry_nsu.pack(fill="x")

        # Exibe inicialmente o painel de dinheiro
        self.painel_dinheiro.pack(fill="x")

        # 5. Card de CPF na Nota (Opcional)
        card_cpf = ctk.CTkFrame(
            body,
            corner_radius=10,
            fg_color=theme.INNER_CARD_BG,
            border_width=1,
            border_color=theme.BORDER_COLOR,
        )
        card_cpf.pack(fill="x", pady=(0, 14))

        head_cpf = ctk.CTkFrame(card_cpf, fg_color="transparent")
        head_cpf.pack(fill="x", padx=16, pady=(8, 2))

        ctk.CTkLabel(
            head_cpf,
            text="📋 CPF do Cliente na Nota (NFC-e / Cupom):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            head_cpf,
            text="(Opcional)",
            font=ctk.CTkFont(size=10, slant="italic"),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(6, 0))

        ctk.CTkButton(
            head_cpf,
            text="Limpar",
            width=50,
            height=20,
            corner_radius=4,
            font=ctk.CTkFont(size=10),
            fg_color=theme.CARD_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.TEXT_MUTED,
            command=self._limpar_cpf,
        ).pack(side="right")

        self.entry_cpf = ctk.CTkEntry(
            card_cpf,
            placeholder_text="000.000.000-00 (Opcional - Digite apenas os números)",
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
        )
        self.entry_cpf.pack(fill="x", padx=16, pady=(0, 10))
        self.entry_cpf.bind("<KeyRelease>", self._ao_digitar_cpf)

        # 6. Rodapé de Ações (Cancelar Esc vs Finalizar Venda F2)
        bar_acoes = ctk.CTkFrame(body, fg_color="transparent")
        bar_acoes.pack(fill="x", pady=(6, 0))

        btn_cancelar = ctk.CTkButton(
            bar_acoes,
            text="❌ Cancelar (Esc)",
            height=46,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._cancelar,
        )
        btn_cancelar.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_confirmar_final = ctk.CTkButton(
            bar_acoes,
            text="✔ FINALIZAR VENDA (F2)",
            height=46,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            text_color="#FFFFFF",
            command=self._confirmar,
        )
        self.btn_confirmar_final.pack(side="right", fill="x", expand=True, padx=(6, 0))

    def _focar_campo_inicial(self):
        """Define o foco inicial no campo de valor recebido."""
        if hasattr(self, "entry_recebido"):
            self.entry_recebido.focus_set()
            self.entry_recebido.delete(0, tk.END)
            self.entry_recebido.insert(0, f"{self.valor_total:.2f}".replace(".", ","))
            self._ao_digitar_recebido()
            self.entry_recebido.select_range(0, tk.END)

    def _selecionar_forma(self, cod: str):
        """Alterna a forma de pagamento ativa da modal."""
        self.forma_selecionada = cod
        for c, btn in self.botoes_pgto.items():
            if c == cod:
                btn.configure(fg_color=theme.ACCENT_BLUE, text_color="#FFFFFF")
            else:
                btn.configure(fg_color=theme.INNER_CARD_BG, text_color=theme.TEXT_SECONDARY)

        if cod == "DINHEIRO":
            self.painel_digital.pack_forget()
            self.painel_dinheiro.pack(fill="x")
            self.entry_recebido.focus_set()
            self._ao_digitar_recebido()
        else:
            self.painel_dinheiro.pack_forget()
            self.painel_digital.pack(fill="x")
            if cod == "PIX":
                self.lbl_digital_titulo.configure(text="📱 Pagamento Instantâneo Pix")
                self.lbl_digital_info.configure(
                    text=f"Aguardando confirmação Pix ({formatar_moeda(self.valor_total)}) • Sem troco.",
                    text_color=theme.STOCK_COLOR[1],
                )
                self.frame_campos_cartao.pack_forget()
            else:
                tipo = "Débito" if cod == "CARTAO_DEBITO" else "Crédito"
                self.lbl_digital_titulo.configure(text=f"💳 Cartão de {tipo} (Maquininha POS / TEF)")
                self.lbl_digital_info.configure(
                    text=f"Insira ou aproxime o cartão na maquininha ({formatar_moeda(self.valor_total)}) • Sem troco.",
                    text_color=theme.ACCENT_BLUE[1] if isinstance(theme.ACCENT_BLUE, tuple) else theme.ACCENT_BLUE,
                )
                self.frame_campos_cartao.pack(fill="x", padx=16, pady=(0, 10))
                self.combo_bandeira.focus_set()

    def _definir_valor_exato(self):
        """Preenche o valor recebido com o total exato da venda."""
        self.entry_recebido.delete(0, tk.END)
        self.entry_recebido.insert(0, f"{self.valor_total:.2f}".replace(".", ","))
        self._ao_digitar_recebido()

    def _definir_cedula(self, valor_cedula: float):
        """Define o valor recebido como a cédula selecionada."""
        self.entry_recebido.delete(0, tk.END)
        self.entry_recebido.insert(0, f"{valor_cedula:.2f}".replace(".", ","))
        self._ao_digitar_recebido()

    def _ao_digitar_recebido(self):
        """Calcula o troco em tempo real com base no valor digitado."""
        texto = self.entry_recebido.get().strip().replace(".", "").replace(",", ".")
        try:
            val = float(texto)
            troco = val - self.valor_total
            if troco >= 0:
                self.entry_troco.delete(0, tk.END)
                self.entry_troco.insert(0, f"{troco:.2f}".replace(".", ","))
                self.lbl_status_troco.configure(
                    text=f"✔ Troco a devolver ao cliente: {formatar_moeda(troco)}",
                    text_color=theme.STOCK_COLOR[1],
                )
                self.btn_confirmar_final.configure(state="normal")
            else:
                falta = abs(troco)
                self.entry_troco.delete(0, tk.END)
                self.entry_troco.insert(0, "0,00")
                self.lbl_status_troco.configure(
                    text=f"⚠️ Falta {formatar_moeda(falta)} para completar o pagamento.",
                    text_color=theme.WARNING_COLOR[1],
                )
        except ValueError:
            self.entry_troco.delete(0, tk.END)
            self.entry_troco.insert(0, "0,00")
            self.lbl_status_troco.configure(
                text="Aguardando valor do cliente...",
                text_color=theme.TEXT_MUTED,
            )

    def _ao_digitar_cpf(self, event=None):
        """Aplica máscara dinâmica no campo de CPF (000.000.000-00)."""
        texto = self.entry_cpf.get()
        nums = re.sub(r"\D", "", texto)[:11]

        formatado = ""
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
        self.entry_cpf.delete(0, tk.END)

    def _ao_teclar_enter(self, event=None):
        """Confirma a venda caso tecle Enter."""
        self._confirmar()
        return "break"

    def _ao_pressionar_f2(self, event=None):
        """Confirma a venda pelo atalho F2."""
        self._confirmar()
        return "break"

    def _confirmar(self):
        """Valida os dados e dispara o callback de finalização para a tela principal."""
        forma = self.forma_selecionada
        val_recebido = self.valor_total
        val_troco = 0.0

        if forma == "DINHEIRO":
            txt_rec = self.entry_recebido.get().strip().replace(".", "").replace(",", ".")
            try:
                val_recebido = float(txt_rec) if txt_rec else self.valor_total
            except ValueError:
                messagebox.showwarning("Aviso", "Informe um valor numérico válido para o dinheiro recebido.", parent=self)
                self.entry_recebido.focus_set()
                return

            if val_recebido < self.valor_total:
                falta = self.valor_total - val_recebido
                messagebox.showwarning(
                    "Valor Insuficiente",
                    f"O valor recebido ({formatar_moeda(val_recebido)}) é menor que o total da venda ({formatar_moeda(self.valor_total)}).\n\nFalta: {formatar_moeda(falta)}.",
                    parent=self,
                )
                self.entry_recebido.focus_set()
                return

            val_troco = max(0.0, round(val_recebido - self.valor_total, 2))

        # Captura e valida CPF se preenchido
        cpf_bruto = self.entry_cpf.get().strip()
        cpf_nums = re.sub(r"\D", "", cpf_bruto)
        if cpf_nums and len(cpf_nums) != 11:
            resp = messagebox.askyesno(
                "CPF Incompleto",
                f"O CPF informado possui {len(cpf_nums)} dígitos (o padrão é 11 dígitos).\n\nDeseja continuar assim mesmo?",
                parent=self,
            )
            if not resp:
                self.entry_cpf.focus_set()
                return

        cpf_formatado = f"{cpf_nums[:3]}.{cpf_nums[3:6]}.{cpf_nums[6:9]}-{cpf_nums[9:11]}" if len(cpf_nums) == 11 else cpf_bruto

        dados_retorno = {
            "forma_pagamento": forma,
            "valor_recebido": val_recebido,
            "troco": val_troco,
            "bandeira": self.combo_bandeira.get() if hasattr(self, "combo_bandeira") else "Mastercard",
            "nsu": self.entry_nsu.get().strip() if hasattr(self, "entry_nsu") else "",
            "cpf_cliente": cpf_formatado,
            "cpf_nums": cpf_nums,
        }

        self.destroy()
        if self.on_confirm_callback:
            self.on_confirm_callback(dados_retorno)

    def _cancelar(self):
        """Fecha a modal sem concluir a venda, retornando o foco à tela de vendas."""
        self.destroy()
