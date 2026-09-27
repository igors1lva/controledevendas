"""
views/fiscal_config_view.py
Módulo de Interface: Configurações Fiscais e Monitor de Contingência da NFC-e.

Permite ao administrador do sistema:
1. Escolher no nível administrativo o Modo de Emissão:
   - Modo Não-Fiscal (Controle Interno / Sem Valor Fiscal)
   - Modo Fiscal (NFC-e SEFAZ Modelo 65 - Offline-First)
2. Configurar Certificado Digital A1 (.pfx), credenciais e dados cadastrais.
3. Testar em tempo real a comunicação com a SEFAZ via ACBr.
4. Monitorar notas emitidas em contingência offline e disparar sincronização manual.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional, Callable, Dict, Any
import customtkinter as ctk

import database as db
import theme
from fiscal.fiscal_service import FiscalService
from fiscal.sync_worker import FiscalSyncWorker
from views.admin_auth_modal import AdminAuthModal


class FiscalConfigView(ctk.CTkFrame):
    """Tela de configurações fiscais e monitoramento de contingência da NFC-e."""

    def __init__(self, parent, on_mode_changed: Optional[Callable] = None):
        super().__init__(parent, fg_color="transparent")
        self.parent = parent
        self.on_mode_changed = on_mode_changed
        self.fiscal_service = FiscalService()

        self._mostrar_senha = False
        self._carregar_dados()
        self._criar_layout()

    def _carregar_dados(self):
        self.config_atual = db.obter_configuracoes_fiscais()
        self.modo_atual = self.config_atual.get("modo_emissao", "NAO_FISCAL")

    def _criar_layout(self):
        # 1. Cabeçalho
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(16, 12))

        ctk.CTkLabel(
            header,
            text="🏛️ Administração Fiscal & Emissão NFC-e",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="Selecione o regime de operação do sistema, configure o certificado digital A1 e monitore a sincronização offline.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w")

        # 2. Card de Seleção de Modo Administrativo
        card_modo = ctk.CTkFrame(self, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        card_modo.pack(fill="x", padx=24, pady=(0, 14))

        row_modo = ctk.CTkFrame(card_modo, fg_color="transparent")
        row_modo.pack(fill="x", padx=20, pady=16)

        col_txt = ctk.CTkFrame(row_modo, fg_color="transparent")
        col_txt.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            col_txt,
            text="Regime de Operação do Sistema (Nível Administrativo):",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        self.lbl_modo_desc = ctk.CTkLabel(
            col_txt,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
            wraplength=650,
            justify="left",
        )
        self.lbl_modo_desc.pack(anchor="w", pady=(4, 0))

        # Seletor Segmentado de Modo
        self.seg_modo = ctk.CTkSegmentedButton(
            row_modo,
            values=["🔒 Controle Interno (Não-Fiscal)", "🏛️ Emissor Fiscal NFC-e (SEFAZ)"],
            command=self._ao_alterar_modo_segmentado,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=38,
        )
        self.seg_modo.pack(side="right", padx=(10, 0))

        val_inicial = "🏛️ Emissor Fiscal NFC-e (SEFAZ)" if self.modo_atual == "FISCAL_NFCE" else "🔒 Controle Interno (Não-Fiscal)"
        self.seg_modo.set(val_inicial)
        self._atualizar_descricao_modo()

        # 3. Tabview com Configurações e Monitor
        self.tabview = ctk.CTkTabview(self, corner_radius=12, fg_color=theme.CARD_BG)
        self.tabview.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self.tab_config = self.tabview.add("⚙️ Parâmetros Fiscais da Empresa")
        self.tab_monitor = self.tabview.add("📡 Monitor de Contingência & Sincronização")

        self._construir_tab_parametros()
        self._construir_tab_monitor()

    def _ao_alterar_modo_segmentado(self, escolha: str):
        novo_modo = "NAO_FISCAL" if "Não-Fiscal" in escolha else "FISCAL_NFCE"

        # Se não houve alteração real, não solicita senha
        if novo_modo == self.modo_atual:
            return

        def _confirmar_troca():
            self.modo_atual = novo_modo
            db.definir_modo_emissao(novo_modo)
            self._atualizar_descricao_modo()

            if self.on_mode_changed:
                self.on_mode_changed(novo_modo)

            nome_novo = "Emissor Fiscal NFC-e (SEFAZ)" if novo_modo == "FISCAL_NFCE" else "Controle Interno (Não-Fiscal)"
            messagebox.showinfo("Sucesso", f"Regime operacional alterado com sucesso para:\n\n{nome_novo}")

        def _cancelar_troca():
            # Restaura a seleção do seletor visual para o modo que estava ativo
            val_anterior = (
                "🏛️ Emissor Fiscal NFC-e (SEFAZ)"
                if self.modo_atual == "FISCAL_NFCE"
                else "🔒 Controle Interno (Não-Fiscal)"
            )
            self.seg_modo.set(val_anterior)

        nome_alvo = "Emissor Fiscal NFC-e (SEFAZ)" if novo_modo == "FISCAL_NFCE" else "Controle Interno (Não-Fiscal)"
        AdminAuthModal(
            parent=self.winfo_toplevel(),
            titulo="🔐 Autorização de Administrador",
            motivo=f"Para alternar o regime operacional para '{nome_alvo}', confirme a senha do administrador ou a senha padrão Central@2026:",
            on_confirm_callback=_confirmar_troca,
            on_cancel_callback=_cancelar_troca,
        )

    def _atualizar_descricao_modo(self):
        if self.modo_atual == "NAO_FISCAL":
            txt = (
                "O sistema opera com foco em gestão operacional e controle de estoque. "
                "Todas as vendas emitem comprovante gerencial com o aviso legal 'SEM VALOR FISCAL'. "
                "Não realiza conexões na SEFAZ e não requer Certificado Digital A1."
            )
            cor = theme.STOCK_COLOR[1]
        else:
            txt = (
                "O sistema emite a NFC-e (modelo 65) autorizada diretamente pela SEFAZ. "
                "Em caso de oscilação de internet ou timeout, o sistema ativa a Contingência Offline (tpEmis = 9) "
                "sem travar o caixa, sincronizando as notas em segundo plano assim que a conexão retornar."
            )
            cor = theme.PRICE_COLOR[1]

        self.lbl_modo_desc.configure(text=txt)

    def _construir_tab_parametros(self):
        scroll = ctk.CTkScrollableFrame(self.tab_config, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=10)

        # 1. Seção Empresa
        sec_emp = ctk.CTkFrame(scroll, corner_radius=10, fg_color=theme.INNER_CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        sec_emp.pack(fill="x", pady=(0, 12), padx=4)

        ctk.CTkLabel(sec_emp, text="🏢 Dados do Estabelecimento Emissor", font=ctk.CTkFont(size=14, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(12, 8))

        grid1 = ctk.CTkFrame(sec_emp, fg_color="transparent")
        grid1.pack(fill="x", padx=16, pady=(0, 14))

        # CNPJ
        ctk.CTkLabel(grid1, text="CNPJ:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
        self.entry_cnpj = ctk.CTkEntry(grid1, width=180, placeholder_text="00.000.000/0000-00")
        self.entry_cnpj.grid(row=0, column=1, sticky="w", pady=4)
        self.entry_cnpj.insert(0, self.config_atual.get("cnpj", ""))

        # IE
        ctk.CTkLabel(grid1, text="Inscrição Estadual (IE):", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=2, sticky="w", padx=(20, 10), pady=4)
        self.entry_ie = ctk.CTkEntry(grid1, width=160, placeholder_text="Somente números")
        self.entry_ie.grid(row=0, column=3, sticky="w", pady=4)
        self.entry_ie.insert(0, self.config_atual.get("ie", ""))

        # Razão Social
        ctk.CTkLabel(grid1, text="Razão Social:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=4)
        self.entry_razao = ctk.CTkEntry(grid1, width=280, placeholder_text="Razão Social da Empresa")
        self.entry_razao.grid(row=1, column=1, columnspan=2, sticky="w", pady=4)
        self.entry_razao.insert(0, self.config_atual.get("razao_social", ""))

        # Nome Fantasia
        ctk.CTkLabel(grid1, text="Fantasia:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=0, sticky="w", padx=(0, 10), pady=4)
        self.entry_fantasia = ctk.CTkEntry(grid1, width=280, placeholder_text="Nome Fantasia")
        self.entry_fantasia.grid(row=2, column=1, columnspan=2, sticky="w", pady=4)
        self.entry_fantasia.insert(0, self.config_atual.get("nome_fantasia", ""))

        # CRT
        ctk.CTkLabel(grid1, text="Regime (CRT):", font=ctk.CTkFont(size=12, weight="bold")).grid(row=1, column=3, sticky="w", padx=(20, 10), pady=4)
        self.combo_crt = ctk.CTkComboBox(grid1, values=["1 - Simples Nacional", "3 - Regime Normal"], width=180)
        self.combo_crt.grid(row=1, column=4, sticky="w", pady=4)
        self.combo_crt.set("1 - Simples Nacional" if str(self.config_atual.get("crt", "1")) == "1" else "3 - Regime Normal")

        # UF
        ctk.CTkLabel(grid1, text="UF / Estado:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=3, sticky="w", padx=(20, 10), pady=4)
        self.combo_uf = ctk.CTkComboBox(grid1, values=["SP", "MG", "RJ", "RS", "PR", "SC", "BA", "GO", "PE", "CE", "ES", "DF"], width=90)
        self.combo_uf.grid(row=2, column=4, sticky="w", pady=4)
        self.combo_uf.set(self.config_atual.get("uf", "SP"))

        # 2. Seção Certificado Digital A1
        sec_cert = ctk.CTkFrame(scroll, corner_radius=10, fg_color=theme.INNER_CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        sec_cert.pack(fill="x", pady=(0, 12), padx=4)

        ctk.CTkLabel(sec_cert, text="🔐 Certificado Digital A1 (.pfx / .p12)", font=ctk.CTkFont(size=14, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(12, 8))

        row_c = ctk.CTkFrame(sec_cert, fg_color="transparent")
        row_c.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(row_c, text="Arquivo do Certificado:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 2))
        sub_c = ctk.CTkFrame(row_c, fg_color="transparent")
        sub_c.pack(fill="x")

        self.entry_cert_path = ctk.CTkEntry(sub_c, placeholder_text="Caminho do arquivo .pfx do Certificado A1")
        self.entry_cert_path.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_cert_path.insert(0, self.config_atual.get("cert_caminho", ""))

        btn_browse = ctk.CTkButton(
            sub_c,
            text="📁 Procurar .pfx",
            width=130,
            command=self._selecionar_certificado,
            fg_color=theme.BTN_SECONDARY_BG,
            text_color=theme.BTN_SECONDARY_TEXT,
            hover_color=theme.BTN_SECONDARY_HOVER,
        )
        btn_browse.pack(side="right")

        # Senha do Certificado
        row_s = ctk.CTkFrame(sec_cert, fg_color="transparent")
        row_s.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkLabel(row_s, text="Senha do Certificado A1 (Criptografada localmente):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 2))
        sub_s = ctk.CTkFrame(row_s, fg_color="transparent")
        sub_s.pack(fill="x")

        self.entry_cert_senha = ctk.CTkEntry(sub_s, width=280, show="*")
        self.entry_cert_senha.pack(side="left", padx=(0, 8))
        self.entry_cert_senha.insert(0, self.config_atual.get("cert_senha", ""))

        self.btn_olho = ctk.CTkButton(
            sub_s,
            text="👁️ Exibir",
            width=90,
            command=self._toggle_exibir_senha,
            fg_color=theme.BTN_SECONDARY_BG,
            text_color=theme.BTN_SECONDARY_TEXT,
        )
        self.btn_olho.pack(side="left")

        # 3. Seção Parâmetros SEFAZ & CSC
        sec_sefaz = ctk.CTkFrame(scroll, corner_radius=10, fg_color=theme.INNER_CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        sec_sefaz.pack(fill="x", pady=(0, 12), padx=4)

        ctk.CTkLabel(sec_sefaz, text="⚙️ Parâmetros SEFAZ, CSC e Numeração", font=ctk.CTkFont(size=14, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(12, 8))

        grid_s = ctk.CTkFrame(sec_sefaz, fg_color="transparent")
        grid_s.pack(fill="x", padx=16, pady=(0, 14))

        # Ambiente
        ctk.CTkLabel(grid_s, text="Ambiente SEFAZ:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
        self.combo_ambiente = ctk.CTkComboBox(grid_s, values=["2 - Homologação (Testes)", "1 - Produção (Oficial)"], width=220)
        self.combo_ambiente.grid(row=0, column=1, sticky="w", pady=4)
        self.combo_ambiente.set("2 - Homologação (Testes)" if str(self.config_atual.get("ambiente", "2")) == "2" else "1 - Produção (Oficial)")

        # ID CSC
        ctk.CTkLabel(grid_s, text="ID do Token CSC:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=2, sticky="w", padx=(20, 10), pady=4)
        self.entry_csc_id = ctk.CTkEntry(grid_s, width=120, placeholder_text="000001")
        self.entry_csc_id.grid(row=0, column=3, sticky="w", pady=4)
        self.entry_csc_id.insert(0, self.config_atual.get("csc_id", "000001"))

        # Token CSC
        ctk.CTkLabel(grid_s, text="Código CSC:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=4)
        self.entry_csc_token = ctk.CTkEntry(grid_s, width=320, placeholder_text="Código alfanumérico fornecido pela SEFAZ")
        self.entry_csc_token.grid(row=1, column=1, columnspan=2, sticky="w", pady=4)
        self.entry_csc_token.insert(0, self.config_atual.get("csc_token", ""))

        # Série e Número
        ctk.CTkLabel(grid_s, text="Série NFC-e:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=0, sticky="w", padx=(0, 10), pady=4)
        self.entry_serie = ctk.CTkEntry(grid_s, width=80)
        self.entry_serie.grid(row=2, column=1, sticky="w", pady=4)
        self.entry_serie.insert(0, str(self.config_atual.get("serie", 1)))

        ctk.CTkLabel(grid_s, text="Último Nº Emitido:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=2, sticky="w", padx=(20, 10), pady=4)
        self.entry_ultimo_num = ctk.CTkEntry(grid_s, width=120)
        self.entry_ultimo_num.grid(row=2, column=3, sticky="w", pady=4)
        self.entry_ultimo_num.insert(0, str(self.config_atual.get("ultimo_numero", 0)))

        # 4. Seção ACBr e Ações
        sec_acbr = ctk.CTkFrame(scroll, corner_radius=10, fg_color=theme.INNER_CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        sec_acbr.pack(fill="x", pady=(0, 14), padx=4)

        ctk.CTkLabel(sec_acbr, text="🔌 Comunicação ACBr & Teste de Conexão", font=ctk.CTkFont(size=14, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(12, 8))

        row_acbr = ctk.CTkFrame(sec_acbr, fg_color="transparent")
        row_acbr.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(row_acbr, text="Host ACBr:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 6))
        self.entry_acbr_host = ctk.CTkEntry(row_acbr, width=130)
        self.entry_acbr_host.pack(side="left", padx=(0, 16))
        self.entry_acbr_host.insert(0, self.config_atual.get("acbr_host", "127.0.0.1"))

        ctk.CTkLabel(row_acbr, text="Porta TCP:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 6))
        self.entry_acbr_porta = ctk.CTkEntry(row_acbr, width=80)
        self.entry_acbr_porta.pack(side="left", padx=(0, 20))
        self.entry_acbr_porta.insert(0, str(self.config_atual.get("acbr_porta", 3434)))

        self.btn_testar_sefaz = ctk.CTkButton(
            row_acbr,
            text="🧪 Testar Conexão SEFAZ",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._testar_conexao_sefaz,
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            width=180,
        )
        self.btn_testar_sefaz.pack(side="left")

        self.lbl_status_teste = ctk.CTkLabel(sec_acbr, text="", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme.TEXT_MUTED)
        self.lbl_status_teste.pack(anchor="w", padx=16, pady=(0, 12))

        # Botão Salvar Todas as Preferências Fiscais
        btn_salvar = ctk.CTkButton(
            scroll,
            text="💾 Salvar Configurações Fiscais",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            command=self._salvar_configuracoes,
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
        )
        btn_salvar.pack(fill="x", padx=4, pady=(10, 20))

    def _construir_tab_monitor(self):
        # 1. Cards de Resumo
        resumo_row = ctk.CTkFrame(self.tab_monitor, fg_color="transparent")
        resumo_row.pack(fill="x", padx=16, pady=(16, 12))

        # Card Autorizadas
        c1 = ctk.CTkFrame(resumo_row, fg_color=theme.INNER_CARD_BG, corner_radius=10, border_width=1, border_color=theme.BORDER_COLOR)
        c1.pack(side="left", fill="both", expand=True, padx=(0, 8))
        ctk.CTkLabel(c1, text="Autorizadas Hoje", font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=14, pady=(10, 2))
        self.lbl_tot_autorizadas = ctk.CTkLabel(c1, text="0", font=ctk.CTkFont(size=22, weight="bold"), text_color=theme.STOCK_COLOR[1])
        self.lbl_tot_autorizadas.pack(anchor="w", padx=14, pady=(0, 10))

        # Card Contingência Pendente
        c2 = ctk.CTkFrame(resumo_row, fg_color=theme.INNER_CARD_BG, corner_radius=10, border_width=1, border_color=theme.BORDER_COLOR)
        c2.pack(side="left", fill="both", expand=True, padx=4)
        ctk.CTkLabel(c2, text="Contingência Pendente", font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=14, pady=(10, 2))
        self.lbl_tot_pendentes = ctk.CTkLabel(c2, text="0", font=ctk.CTkFont(size=22, weight="bold"), text_color=theme.WARNING_COLOR[1])
        self.lbl_tot_pendentes.pack(anchor="w", padx=14, pady=(0, 10))

        # Card Rejeitadas
        c3 = ctk.CTkFrame(resumo_row, fg_color=theme.INNER_CARD_BG, corner_radius=10, border_width=1, border_color=theme.BORDER_COLOR)
        c3.pack(side="left", fill="both", expand=True, padx=(8, 0))
        ctk.CTkLabel(c3, text="Rejeitadas", font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=14, pady=(10, 2))
        self.lbl_tot_rejeitadas = ctk.CTkLabel(c3, text="0", font=ctk.CTkFont(size=22, weight="bold"), text_color=theme.ACCENT_RED[1])
        self.lbl_tot_rejeitadas.pack(anchor="w", padx=14, pady=(0, 10))

        # Barra de Ação
        bar_sync = ctk.CTkFrame(self.tab_monitor, fg_color="transparent")
        bar_sync.pack(fill="x", padx=16, pady=(4, 10))

        ctk.CTkLabel(bar_sync, text="Lista de Vendas em Contingência Offline (Aguardando Sincronização):", font=ctk.CTkFont(size=13, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")

        self.btn_sync_agora = ctk.CTkButton(
            bar_sync,
            text="🔄 Sincronizar Agora com a SEFAZ",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._sincronizar_manualmente,
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            height=34,
        )
        self.btn_sync_agora.pack(side="right")

        # Container com a lista de pendências
        self.scroll_pendencias = ctk.CTkScrollableFrame(self.tab_monitor, fg_color=theme.INNER_CARD_BG, corner_radius=10, border_width=1, border_color=theme.BORDER_COLOR)
        self.scroll_pendencias.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._recarregar_dados_monitor()

    def _recarregar_dados_monitor(self):
        resumo = db.obter_resumo_fiscal_hoje()
        self.lbl_tot_autorizadas.configure(text=str(resumo.get("autorizadas", 0)))
        self.lbl_tot_pendentes.configure(text=str(resumo.get("pendentes", 0)))
        self.lbl_tot_rejeitadas.configure(text=str(resumo.get("rejeitadas", 0)))

        # Limpa lista
        for widget in self.scroll_pendencias.winfo_children():
            widget.destroy()

        pendentes = db.obter_vendas_fiscais_pendentes()
        if not pendentes:
            ctk.CTkLabel(
                self.scroll_pendencias,
                text="✔ Nenhuma nota pendente em contingência. Todas as emissões estão sincronizadas!",
                font=ctk.CTkFont(size=13),
                text_color=theme.STOCK_COLOR[1],
            ).pack(pady=30)
            return

        for p in pendentes:
            card = ctk.CTkFrame(self.scroll_pendencias, corner_radius=8, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
            card.pack(fill="x", pady=4, padx=6)

            txt = (
                f"Venda #{p['venda_id']} | NFC-e nº {p['numero_nfce']} (Série {p['serie']})\n"
                f"Chave: {p['chave_acesso']}\n"
                f"Emitida em: {p['dh_emissao']} | Tentativas: {p.get('tentativas_sincronizacao', 0)}"
            )
            ctk.CTkLabel(card, text=txt, font=ctk.CTkFont(size=11), justify="left").pack(side="left", padx=12, pady=8)

            badge = ctk.CTkLabel(
                card,
                text="PENDENTE DE ENVIO",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=theme.WARNING_COLOR[1],
            )
            badge.pack(side="right", padx=14)

    def _sincronizar_manualmente(self):
        self.btn_sync_agora.configure(state="disabled", text="⏳ Sincronizando...")

        def _tarefa():
            worker = FiscalSyncWorker()
            res = worker.sincronizar_agora()
            self.after(0, lambda: self._pos_sincronizacao(res))

        threading.Thread(target=_tarefa, daemon=True).start()

    def _pos_sincronizacao(self, res: Dict[str, int]):
        self.btn_sync_agora.configure(state="normal", text="🔄 Sincronizar Agora com a SEFAZ")
        self._recarregar_dados_monitor()
        msg = f"Sincronização concluída!\n\nAutorizadas: {res.get('autorizadas', 0)}\nRejeitadas: {res.get('rejeitadas', 0)}\nPendentes: {res.get('pendentes', 0)}"
        messagebox.showinfo("Sincronização SEFAZ", msg)

    def _selecionar_certificado(self):
        caminho = filedialog.askopenfilename(
            title="Selecione o Certificado Digital A1 (.pfx / .p12)",
            filetypes=[("Certificado Digital A1", "*.pfx *.p12"), ("Todos os Arquivos", "*.*")],
        )
        if caminho:
            self.entry_cert_path.delete(0, tk.END)
            self.entry_cert_path.insert(0, caminho)

    def _toggle_exibir_senha(self):
        self._mostrar_senha = not self._mostrar_senha
        if self._mostrar_senha:
            self.entry_cert_senha.configure(show="")
            self.btn_olho.configure(text="🔒 Ocultar")
        else:
            self.entry_cert_senha.configure(show="*")
            self.btn_olho.configure(text="👁️ Exibir")

    def _testar_conexao_sefaz(self):
        self.lbl_status_teste.configure(text="⏳ Conectando à SEFAZ via ACBr...", text_color=theme.PRICE_COLOR[1])
        self.btn_testar_sefaz.configure(state="disabled")

        def _tarefa():
            ok, resp, cstat = self.fiscal_service.testar_sefaz()
            self.after(0, lambda: self._pos_teste_sefaz(ok, resp, cstat))

        threading.Thread(target=_tarefa, daemon=True).start()

    def _pos_teste_sefaz(self, ok: bool, resp: str, cstat: int):
        self.btn_testar_sefaz.configure(state="normal")
        if ok and cstat == 107:
            self.lbl_status_teste.configure(
                text="✅ SEFAZ em Operação! Conexão estabelecida com sucesso (cStat 107).",
                text_color=theme.STOCK_COLOR[1],
            )
        else:
            self.lbl_status_teste.configure(
                text=f"⚠️ Falha de comunicação: {resp}",
                text_color=theme.ACCENT_RED[1],
            )

    def _salvar_configuracoes(self):
        crt_cod = "1" if "1" in self.combo_crt.get() else "3"
        amb_cod = "2" if "2" in self.combo_ambiente.get() else "1"

        try:
            serie_int = int(self.entry_serie.get().strip() or "1")
            ultimo_num_int = int(self.entry_ultimo_num.get().strip() or "0")
            porta_int = int(self.entry_acbr_porta.get().strip() or "3434")
        except ValueError:
            messagebox.showerror("Erro de Validação", "Série, Último Número e Porta TCP devem ser números inteiros.")
            return

        dados = {
            "modo_emissao": self.modo_atual,
            "cnpj": self.entry_cnpj.get().strip(),
            "ie": self.entry_ie.get().strip(),
            "razao_social": self.entry_razao.get().strip(),
            "nome_fantasia": self.entry_fantasia.get().strip(),
            "crt": crt_cod,
            "ambiente": amb_cod,
            "uf": self.combo_uf.get().strip(),
            "cert_caminho": self.entry_cert_path.get().strip(),
            "cert_senha": self.entry_cert_senha.get().strip(),
            "csc_id": self.entry_csc_id.get().strip(),
            "csc_token": self.entry_csc_token.get().strip(),
            "serie": serie_int,
            "ultimo_numero": ultimo_num_int,
            "acbr_host": self.entry_acbr_host.get().strip(),
            "acbr_porta": porta_int,
        }

        db.salvar_configuracoes_fiscais(dados)
        self.fiscal_service.recarregar_configuracoes()

        if self.on_mode_changed:
            self.on_mode_changed(self.modo_atual)

        messagebox.showinfo("Sucesso", "Configurações fiscais salvas com sucesso!")
