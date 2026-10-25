"""
Aplicação Principal - Sistema de Gestão de Vendas, PDV e Inventário
Arquivo: app.py

Ponto de entrada da aplicação desktop comercial construída com CustomTkinter.
Gerencia a janela principal, barra lateral com logotipo e menu acordeão,
header HUD com relógio e atalho para backup, persistência de tema Dark/Light,
além da navegação para as telas do sistema:
  1. Catálogo / Lista de Produtos (com busca por EAN e importação de XML da NF-e)
  2. Cadastrar Novo Produto (com foco automático e suporte a leitor USB de código de barras)
  3. Nova Venda Balcão / PDV (com atalho F2 e leitor óptico USB)
  4. Histórico de Vendas de Hoje
  5. Fechamento Consolidado do Dia
  6. Central de Exportação Excel (.xlsx) com proteção de senha
  7. Módulo Fiscal / NFC-e (disponível nas edições Fiscal e Completa)
  8. Central de Cópias de Segurança e Backup Atômico
"""

import sys
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any
import customtkinter as ctk
from tkinter import messagebox

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

import database as db
import theme
import edicao_config
import backup_manager
import license_manager as lm

from views.catalog_view import CatalogView
from views.product_form_view import ProductFormView
from views.pos_sale_view import POSSaleView
from views.sales_history_view import SalesHistoryView
from views.daily_closure_view import DailyClosureView
from views.export_excel_view import ExportExcelView
from views.license_modal import LicenseActivationModal
from views.backup_modal import BackupModal
from views.dashboard_view import DashboardView
from views.screensaver_overlay import ScreensaverOverlay

# Carrega condicionalmente o módulo fiscal se a edição suportar
FiscalConfigView = None
FiscalSyncWorker = None
if edicao_config.permite_modulo_fiscal():
    try:
        from views.fiscal_config_view import FiscalConfigView
        from fiscal.sync_worker import FiscalSyncWorker
    except Exception:
        pass

# Configuração inicial de tema CustomTkinter
ctk.set_default_color_theme("blue")


def obter_caminho_recurso(caminho_relativo: str) -> str:
    """
    Retorna o caminho absoluto para recursos (imagens, ícones, assets),
    garantindo compatibilidade tanto em modo desenvolvimento quanto quando
    empacotado em executável único com PyInstaller (sys._MEIPASS).
    """
    if getattr(sys, "frozen", False):
        base_meipass = getattr(sys, "_MEIPASS", None)
        if base_meipass:
            caminho_temp = os.path.join(base_meipass, caminho_relativo)
            if os.path.exists(caminho_temp):
                return caminho_temp

        caminho_exe = os.path.join(os.path.dirname(sys.executable), caminho_relativo)
        if os.path.exists(caminho_exe):
            return caminho_exe

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), caminho_relativo)


class App(ctk.CTk):
    """Janela principal da aplicação comercial com arquitetura multi-edição."""

    def __init__(self, edicao: Optional[str] = None):
        super().__init__()

        # 1. Configuração da Edição
        if edicao:
            edicao_config.definir_edicao(edicao)

        # 2. Inicializa o banco de dados SQLite local com integridade transacional
        db.init_db()

        # 3. Dispara a rotina de verificação e backup automático diário em background
        backup_manager.disparar_backup_automatico_thread()

        # 4. Inicializa o software sempre na versão Light por padrão
        self.tema_atual = "Light"
        ctk.set_appearance_mode("Light")
        db.salvar_config("appearance_mode", "Light")

        # 5. Validação do Sistema de Licenciamento Criptográfico Ed25519
        self.licenca_valida, self.licenca_msg, self.info_licenca = lm.validar_licenca()

        # Configurações da Janela
        nome_edicao = edicao_config.obter_nome_edicao()
        self.title(nome_edicao)
        self.geometry("1260x780")
        self.minsize(1040, 660)
        self.configure(fg_color=theme.BG_COLOR)

        # Configuração do Ícone da Janela
        caminho_ico = obter_caminho_recurso("assets/vendas.ico")
        if not os.path.exists(caminho_ico):
            caminho_ico = obter_caminho_recurso("vendas.ico")
        if os.path.exists(caminho_ico):
            try:
                self.iconbitmap(caminho_ico)
            except Exception:
                pass

        # Configuração do Layout Principal (Grid com 2 colunas: Sidebar e Conteúdo)
        self.grid_columnconfigure(0, weight=0)  # Sidebar largura fixa
        self.grid_columnconfigure(1, weight=1)  # Conteúdo expansível
        self.grid_rowconfigure(0, weight=1)

        # Estado dos Menus Acordeão
        self.secoes_acordeao = {}
        self.subitens_botoes = {}
        self.subitem_ativo: Optional[str] = None

        # Criação dos Componentes de Interface
        self._criar_sidebar()
        self._criar_area_conteudo()

        # Atualiza badges de status na barra lateral
        self._atualizar_badge_licenca()
        self._atualizar_badge_modo_fiscal()

        # Inicia o relógio dinâmico no HUD
        self._atualizar_relogio()

        # Inicialização condicional do Worker de Sincronização Fiscal em background
        self.fiscal_sync_worker = None
        if edicao_config.permite_modulo_fiscal():
            try:
                from fiscal.sync_worker import FiscalSyncWorker as FWorker
                self.fiscal_sync_worker = FWorker(intervalo_segundos=120)
                self.fiscal_sync_worker.start()
            except Exception:
                pass

        self.protocol("WM_DELETE_WINDOW", self._ao_fechar_janela)

        # Atalhos rápidos de teclado
        self.bind("<F1>", lambda e: self._navegar_subitem("estoque_catalogo"))
        self.bind_all("<F2>", self._tratar_atalho_f2)
        self.bind_all("<F3>", self._tratar_atalho_f3)
        self.bind_all("<F4>", self._tratar_atalho_f4)

        # Monitoramento Inteligente de Inatividade e Protetor de Tela (Screensaver)
        self._ultimo_evento_usuario = time.time()
        self._ultimo_mouse_check = 0.0
        self.screensaver_overlay = ScreensaverOverlay(self, on_dismiss=self._ao_desbloquear_screensaver)

        # Captura global de eventos para zerar o contador de inatividade ao menor toque
        self.bind_all("<Key>", self._ao_detectar_atividade_usuario, add="+")
        self.bind_all("<Button>", self._ao_detectar_atividade_usuario, add="+")
        self.bind_all("<Motion>", self._ao_detectar_atividade_mouse, add="+")

        # Inicia ciclo periódico de verificação de inatividade a cada 1 segundo (precisão exata)
        self.after(1000, self._verificar_inatividade_screensaver)

        # Controle de Ativação de Licença:
        if not self.licenca_valida:
            self.withdraw()
            self.after(50, self._exibir_modal_ativacao_obrigatoria)
        else:
            self.after(10, self._centralizar_janela)
            self._navegar_subitem("pdv_nova_venda")

    def _centralizar_janela(self):
        """Posiciona a janela no centro do monitor do usuário."""
        self.update_idletasks()
        largura = self.winfo_width()
        altura = self.winfo_height()
        pos_x = (self.winfo_screenwidth() - largura) // 2
        pos_y = (self.winfo_screenheight() - altura) // 2
        self.geometry(f"{largura}x{altura}+{pos_x}+{pos_y}")

    # ========================================================================
    # MONITORAMENTO DE INATIVIDADE & TELA DE DESCANSO (SCREENSAVER)
    # ========================================================================

    def _ao_detectar_atividade_usuario(self, event=None):
        """Registra a atividade do usuário via teclado ou cliques de mouse e fecha screensaver se ativo."""
        self._ultimo_evento_usuario = time.time()
        if hasattr(self, "screensaver_overlay") and self.screensaver_overlay.ativo:
            self.screensaver_overlay.fechar_screensaver()

    def _ao_detectar_atividade_mouse(self, event=None):
        """Registra movimento do mouse com limitação de taxa para evitar overhead de CPU."""
        agora = time.time()
        if agora - self._ultimo_mouse_check > 0.5:
            self._ultimo_mouse_check = agora
            self._ultimo_evento_usuario = agora

    def registrar_atividade_externa(self):
        """Permite que views filhas (como PDV ao finalizar venda ou trocar abas) reiniciem o contador."""
        self._ultimo_evento_usuario = time.time()

    def _verificar_inatividade_screensaver(self):
        """Verifica se o tempo configurado de inatividade foi atingido para exibir o protetor de tela."""
        try:
            if hasattr(self, "screensaver_overlay") and not self.screensaver_overlay.ativo and self.licenca_valida:
                config_min = db.obter_config("screensaver_timeout_min", "0.5")
                if config_min not in ("0", "Desativado"):
                    try:
                        timeout_segundos = max(5, int(float(config_min) * 60))
                    except (ValueError, TypeError):
                        timeout_segundos = 30  # Padrão 30 segundos
                    
                    if time.time() - self._ultimo_evento_usuario >= timeout_segundos:
                        self.ativar_screensaver_manual()
        except Exception:
            pass
        finally:
            self.after(1000, self._verificar_inatividade_screensaver)

    def ativar_screensaver_manual(self):
        """Ativa a tela de descanso cobrindo 100% da aplicação."""
        if hasattr(self, "screensaver_overlay"):
            self.screensaver_overlay.mostrar()

    def _ao_desbloquear_screensaver(self):
        """Callback acionado ao desbloquear ou fechar a tela de descanso."""
        self._ultimo_evento_usuario = time.time()

    # ========================================================================
    # BARRA LATERAL (SIDEBAR COM LOGO E ACORDEÃO)
    # ========================================================================

    def _criar_sidebar(self):
        """Constrói a barra lateral de navegação com logotipo e menus ramificados."""
        self.sidebar_frame = ctk.CTkFrame(
            self,
            width=340,
            corner_radius=0,
            fg_color=theme.SIDEBAR_BG,
            border_width=0,
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False)

        # 1. Área do Logotipo da Empresa
        self._criar_area_logotipo()

        # Divisor Superior
        ctk.CTkFrame(self.sidebar_frame, height=1, fg_color=theme.BORDER_COLOR).pack(fill="x", padx=16, pady=(8, 10))

        # 2. Container para Menus Acordeão (sem barra de rolagem visual)
        self.menu_scroll = ctk.CTkScrollableFrame(self.sidebar_frame, fg_color="transparent")
        self.menu_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        # Oculta permanentemente a barra de rolagem visual garantindo encaixe fluido e sem barras indesejadas
        self.menu_scroll._scrollbar.grid_forget()
        self.menu_scroll._parent_frame.grid_columnconfigure(1, weight=0, minsize=0)
        self.menu_scroll._parent_canvas.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=0, pady=0)

        # Subitens de Configurações & Fiscal (exigem autenticação de administrador)
        subitens_fiscal = [
            ("rel_fechamento", "📋 Fechamento do Dia 🔒", "fechamento_dia"),
            ("rel_exportar", "📥 Exportar Planilha 🔒", "exportar_excel"),
            ("rel_backup", "🛡 Backup 🔒", "backup_modal"),
            ("fiscal_config", "⚙ Emissão Fiscal / NFC-e 🔒", "config_fiscal"),
        ]

        # Estrutura modular de menus
        estrutura_menu = [
            {
                "id": "estoque",
                "titulo": "Estoque & Produtos",
                "icone": "📦",
                "subitens": [
                    ("estoque_catalogo", "🏷 Catálogo / Lista", "catalogo"),
                    ("estoque_novo", "➕ Cadastrar Produto", "novo_produto"),
                ],
            },
            {
                "id": "pdv",
                "titulo": "Frente de Caixa / PDV",
                "icone": "🛒",
                "subitens": [
                    ("pdv_nova_venda", "⚡ Nova Venda (F2)", "nova_venda"),
                    ("pdv_historico", "🕒 Histórico de Vendas", "historico_vendas"),
                ],
            },
            {
                "id": "fiscal_config",
                "titulo": "Configurações & Fiscal",
                "icone": "⚙",
                "subitens": subitens_fiscal,
            },
        ]

        for sec in estrutura_menu:
            self._criar_secao_acordeao(sec)

        # Abre as seções de Estoque e PDV por padrão, mantendo Configurações & Fiscal recolhida ao abrir o software
        for sec_id in self.secoes_acordeao:
            if sec_id == "fiscal_config":
                self._toggle_secao(sec_id, forcar_abrir=False)
            else:
                self._toggle_secao(sec_id, forcar_abrir=True)

        # 3. Rodapé da Sidebar
        footer_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        footer_frame.pack(side="bottom", fill="x", padx=16, pady=(12, 14))

        # Botão em Destaque do Dashboard Analítico (BI) - Elevado na barra lateral
        self.btn_dashboard_bi = ctk.CTkButton(
            footer_frame,
            text="📈 Dashboard Analítico (BI) 🔒",
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#D97706",
            hover_color="#B45309",
            text_color="#FFFFFF",
            command=self._abrir_dashboard_bi,
        )
        self.btn_dashboard_bi.pack(fill="x", pady=(0, 10))

        # Logotipo Oficial AstridSoft - Localizado no rodapé abaixo do botão do Dashboard
        self._criar_area_logo_astridsoft(footer_frame)

        # Divisor Rodapé
        ctk.CTkFrame(footer_frame, height=1, fg_color=theme.BORDER_COLOR).pack(fill="x", pady=(4, 6))

        # Linha Discreta de Status da Licença
        self.card_licenca = ctk.CTkFrame(footer_frame, fg_color="transparent")
        self.card_licenca.pack(fill="x", pady=(0, 4))

        self.lbl_licenca_status = ctk.CTkLabel(
            self.card_licenca,
            text="Carregando licença...",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.STOCK_COLOR[1],
            anchor="w",
        )
        self.lbl_licenca_status.pack(anchor="w", padx=2)

        ed_sigla = edicao_config.obter_edicao()
        self.lbl_licenca_detalhes = ctk.CTkLabel(
            self.card_licenca,
            text=f"v1.0 • Edição {ed_sigla}",
            font=ctk.CTkFont(size=9),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.lbl_licenca_detalhes.pack(anchor="w", padx=2, pady=(1, 0))

        self.lbl_modo_fiscal = ctk.CTkLabel(
            footer_frame,
            text="",
            font=ctk.CTkFont(size=8),
            text_color=theme.TEXT_MUTED,
        )

        # Barra Inferior de Controles: Seletor de Tema (largura ajustada) + Botão Chavinha de Licença
        controls_row = ctk.CTkFrame(footer_frame, fg_color="transparent")
        controls_row.pack(fill="x", pady=(6, 0))

        self.tema_menu = ctk.CTkOptionMenu(
            controls_row,
            values=["Dark", "Light", "System"],
            command=self._ao_alterar_tema,
            height=30,
            corner_radius=6,
            fg_color=theme.BTN_SECONDARY_BG,
            button_color=theme.ACCENT_BLUE,
            button_hover_color=theme.ACCENT_BLUE_HOVER,
            dropdown_fg_color=theme.CARD_BG,
            text_color=theme.BTN_SECONDARY_TEXT,
            font=ctk.CTkFont(size=11),
        )
        self.tema_menu.set(self.tema_atual)
        self.tema_menu.pack(side="left", fill="x", expand=True, padx=(0, 6))

        # Botão Chavinha para alterar / renovar a licença
        self.btn_renovar_lic = ctk.CTkButton(
            controls_row,
            text="🔑",
            width=36,
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(size=13),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._abrir_modal_renovacao,
        )
        self.btn_renovar_lic.pack(side="right")

    def _ao_alterar_tema(self, novo_modo: str):
        """Aplica instantaneamente o modo de aparência e persiste a escolha no SQLite."""
        self.tema_atual = novo_modo
        ctk.set_appearance_mode(novo_modo)
        db.salvar_config("appearance_mode", novo_modo)

    def _atualizar_badge_licenca(self):
        """Atualiza visualmente o status da licença na barra lateral de forma discreta e elegante."""
        if not hasattr(self, "lbl_licenca_status") or not hasattr(self, "info_licenca"):
            return

        info = self.info_licenca
        ed_sigla = edicao_config.obter_edicao()

        if info.get("is_lifetime"):
            self.lbl_licenca_status.configure(
                text="💎 Licença: Vitalícia",
                text_color=theme.PRICE_COLOR[1],
            )
            cliente = info.get("client", "Comercial")
            if hasattr(self, "lbl_licenca_detalhes"):
                self.lbl_licenca_detalhes.configure(text=f"Cliente: {cliente} • v1.0 • {ed_sigla}")
        elif info.get("status") == "VALID":
            dias = info.get("days_remaining", 0)
            cor = theme.STOCK_COLOR[1] if dias > 5 else theme.WARNING_COLOR[1]
            eh_trial = info.get("plan") == "15_DAYS"
            titulo_lic = f"⭐ Trial: {dias} dias" if eh_trial else f"⏳ Licença: {dias} dias"
            self.lbl_licenca_status.configure(
                text=titulo_lic,
                text_color=cor,
            )
            exp_str = info.get("expires_at", "")
            if exp_str and hasattr(self, "lbl_licenca_detalhes"):
                try:
                    dt_fmt = datetime.fromisoformat(exp_str).strftime("%d/%m/%Y")
                    self.lbl_licenca_detalhes.configure(text=f"Expira: {dt_fmt} • v1.0 • {ed_sigla}")
                except Exception:
                    self.lbl_licenca_detalhes.configure(text=f"Ativa • v1.0 • {ed_sigla}")
        else:
            self.lbl_licenca_status.configure(
                text="❌ Licença Bloqueada",
                text_color=theme.ACCENT_RED[1],
            )
            if hasattr(self, "lbl_licenca_detalhes"):
                self.lbl_licenca_detalhes.configure(text="Clique na chavinha 🔑 para ativar")

    def _exibir_modal_ativacao_obrigatoria(self):
        """Exibe o modal de ativação bloqueando a interface quando não há licença válida."""
        LicenseActivationModal(
            self,
            on_activated_callback=self._apos_ativar_licenca,
            em_modo_bloqueio=True,
            mensagem_inicial=self.licenca_msg,
        )

    def _abrir_modal_renovacao(self):
        """Abre o modal de ativação em modo não-bloqueante para renovação ou upgrade de licença."""
        LicenseActivationModal(
            self,
            on_activated_callback=self._apos_renovar_licenca,
            em_modo_bloqueio=False,
            mensagem_inicial="",
        )

    def _abrir_modal_backup(self):
        """Abre a central de cópias de segurança e restauração de dados com autenticação administrativa."""
        from views.admin_auth_modal import solicitar_senha_admin
        autorizado = solicitar_senha_admin(
            self,
            titulo="Backup & Segurança (Acesso Restrito)",
            motivo="Digite a senha de administrador para acessar as ferramentas de backup e restauração:",
        )
        if not autorizado:
            return

        BackupModal(
            parent=self,
            on_restored_callback=self._sincronizar_apos_restauracao,
        )

    def _abrir_dashboard_bi(self):
        """Abre o Dashboard Analítico (BI) isolado exigindo senha administrativa."""
        from views.admin_auth_modal import solicitar_senha_admin
        autorizado = solicitar_senha_admin(
            self,
            titulo="Painel Analítico & BI (Acesso Restrito)",
            motivo="Acesso confidencial ao Dashboard de Vendas e Margem de Lucro",
        )
        if not autorizado:
            return

        # Desmarca subitens ativos nos acordeões (todos voltam ao estilo padrão com borda azul)
        for sid, item in self.subitens_botoes.items():
            btn = item["button"]
            btn.configure(
                fg_color=theme.INNER_CARD_BG,
                text_color="#60A5FA",
                hover_color=theme.BTN_SECONDARY_HOVER,
                border_width=2,
                border_color="#3B82F6",
            )

        self.subitem_ativo = "dashboard_analytics"
        self.lbl_breadcrumb.configure(text="Gestão Estratégica › Dashboard Analítico (BI)")

        # Oculta todas as telas e exibe a view do Dashboard
        for v in self.views.values():
            v.pack_forget()

        if hasattr(self, "view_dashboard"):
            self.view_dashboard.recarregar_dados()
            self.view_dashboard.pack(fill="both", expand=True)

    def _apos_ativar_licenca(self):
        """Executado após ativação inicial com sucesso: libera a tela principal."""
        self.licenca_valida, self.licenca_msg, self.info_licenca = lm.validar_licenca()
        self._atualizar_badge_licenca()
        self.deiconify()
        self._centralizar_janela()
        self._navegar_subitem("pdv_nova_venda")

    def _apos_renovar_licenca(self):
        """Executado após renovação de chave no rodapé."""
        self.licenca_valida, self.licenca_msg, self.info_licenca = lm.validar_licenca()
        self._atualizar_badge_licenca()

    def _criar_area_logotipo(self):
        """Inicializa o container do logotipo da empresa no topo da barra lateral."""
        self.logo_container = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.logo_container.pack(fill="x", padx=16, pady=(16, 6))
        self.atualizar_logotipo_sidebar()

    def atualizar_logotipo_sidebar(self):
        """Renderiza ou atualiza instantaneamente o logotipo da empresa (personalizado ou padrão)."""
        if not hasattr(self, "logo_container"):
            return

        for w in self.logo_container.winfo_children():
            w.destroy()

        # Verifica se o cliente configurou um logotipo personalizado no Dashboard
        caminho_custom = db.obter_config("custom_logo_path", "")
        if caminho_custom and os.path.exists(caminho_custom):
            caminho_logo = caminho_custom
        else:
            caminho_logo = obter_caminho_recurso(os.path.join("assets", "logo.png"))

        logo_carregado = False
        if PIL_AVAILABLE and os.path.exists(caminho_logo):
            try:
                with Image.open(caminho_logo) as img_raw:
                    pil_img = img_raw.copy()
                orig_w, orig_h = pil_img.size
                alvo_w = 300
                alvo_h = int((orig_h / orig_w) * alvo_w)
                alvo_h = min(alvo_h, 115)

                logo_ctk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(alvo_w, alvo_h))
                lbl_logo_img = ctk.CTkLabel(self.logo_container, image=logo_ctk, text="")
                lbl_logo_img.pack(pady=4)
                self.lbl_logo_img = lbl_logo_img
                logo_carregado = True
            except Exception:
                logo_carregado = False

        if not logo_carregado:
            card_fallback = ctk.CTkFrame(self.logo_container, fg_color=theme.INNER_CARD_BG, corner_radius=12, border_width=1, border_color=theme.BORDER_COLOR)
            card_fallback.pack(fill="x", pady=4)

            inner = ctk.CTkFrame(card_fallback, fg_color="transparent")
            inner.pack(fill="x", padx=14, pady=14)

            badge_icon = ctk.CTkFrame(inner, fg_color=theme.ACCENT_BLUE, corner_radius=12, width=60, height=60)
            badge_icon.pack_propagate(False)
            badge_icon.pack(side="left", padx=(0, 14))
            ctk.CTkLabel(badge_icon, text="🛍️", font=ctk.CTkFont(size=28)).pack(expand=True)

            text_frame = ctk.CTkFrame(inner, fg_color="transparent")
            text_frame.pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(text_frame, text="CENTRAL DE VENDAS", font=ctk.CTkFont(size=15, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w")
            ctk.CTkLabel(text_frame, text="PDV & GESTÃO", font=ctk.CTkFont(size=12), text_color=theme.TEXT_SECONDARY).pack(anchor="w")

    def _criar_area_logo_astridsoft(self, parent_frame):
        """Renderiza o logotipo oficial AstridSoft posicionado no rodapé abaixo do Dashboard."""
        caminho_light = obter_caminho_recurso(os.path.join("assets", "astridsoft_logo.png"))
        caminho_dark = obter_caminho_recurso(os.path.join("assets", "astridsoft_logo_white.png"))
        if not os.path.exists(caminho_dark):
            caminho_dark = caminho_light

        if PIL_AVAILABLE and os.path.exists(caminho_light):
            try:
                with Image.open(caminho_light) as f_light:
                    pil_light = f_light.copy()
                with Image.open(caminho_dark) as f_dark:
                    pil_dark = f_dark.copy()
                alvo_w = 125
                alvo_h = int(pil_light.height * (alvo_w / pil_light.width))

                # Mantém o logo preto original idêntico tanto no modo Light quanto no Dark
                ctk_astrid = ctk.CTkImage(
                    light_image=pil_light,
                    dark_image=pil_light,
                    size=(alvo_w, alvo_h),
                )
                self.lbl_astrid_logo = ctk.CTkLabel(parent_frame, image=ctk_astrid, text="")
                self.lbl_astrid_logo.pack(pady=(2, 6))
            except Exception:
                pass

    def _criar_secao_acordeao(self, config_secao: dict):
        """Cria uma categoria com cabeçalho clicável e container de subitens expansíveis."""
        sec_id = config_secao["id"]
        titulo = config_secao["titulo"]
        icone = config_secao["icone"]
        subitens = config_secao["subitens"]

        secao_frame = ctk.CTkFrame(self.menu_scroll, fg_color="transparent")
        secao_frame.pack(fill="x", pady=(1, 2))

        # Botão Cabeçalho da Categoria
        # Se for 'fiscal_config' (Configurações & Fiscal), aplica estilo do Dashboard (altura 40, cantos 8) na cor verde #059669
        if sec_id == "fiscal_config":
            btn_header = ctk.CTkButton(
                secao_frame,
                text=f"{icone}  {titulo}",
                height=40,
                corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
                fg_color="#059669",
                hover_color="#047857",
                text_color="#FFFFFF",
                border_width=0,
                command=lambda sid=sec_id: self._toggle_secao(sid),
            )
        else:
            btn_header = ctk.CTkButton(
                secao_frame,
                text=f"{icone}  {titulo}",
                height=36,
                corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
                fg_color=theme.INNER_CARD_BG,
                text_color=theme.TEXT_PRIMARY,
                hover_color=theme.BTN_SECONDARY_HOVER,
                border_width=1,
                border_color=theme.BORDER_COLOR,
                command=lambda sid=sec_id: self._toggle_secao(sid),
            )
        btn_header.pack(fill="x", padx=2, pady=1)

        # Container dos Subitens
        sub_container = ctk.CTkFrame(secao_frame, fg_color="transparent")
        sub_container.pack(fill="x", padx=2, pady=(1, 3))

        for sub_id, rotulo, view_key in subitens:
            # Remove o seletor de variação unicode (\ufe0f) para que todos os ícones tenham largura idêntica (18px)
            rotulo_formatado = rotulo.replace("\ufe0f", "")
            btn_sub = ctk.CTkButton(
                sub_container,
                text=f"  {rotulo_formatado}",
                height=38,
                corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
                fg_color=theme.INNER_CARD_BG,
                text_color="#60A5FA",
                hover_color=theme.BTN_SECONDARY_HOVER,
                border_width=2,
                border_color="#3B82F6",
                command=lambda sid=sub_id, vk=view_key, r=rotulo, cat=titulo: self._navegar_subitem(
                    sid, vk, r, cat
                ),
            )
            btn_sub.pack(fill="x", padx=(4, 2), pady=2)
            self.subitens_botoes[sub_id] = {
                "button": btn_sub,
                "view_key": view_key,
                "rotulo": rotulo,
                "categoria": titulo,
            }

        self.secoes_acordeao[sec_id] = {
            "btn_header": btn_header,
            "container": sub_container,
            "icone": icone,
            "titulo": titulo,
            "aberto": True,
        }

    def _toggle_secao(self, sec_id: str, forcar_abrir: Optional[bool] = None):
        """Expande ou recolhe os subitens de uma categoria do acordeão."""
        info = self.secoes_acordeao.get(sec_id)
        if not info:
            return

        novo_estado = forcar_abrir if forcar_abrir is not None else not info["aberto"]
        info["aberto"] = novo_estado

        seta = "▼" if novo_estado else "▶"
        info["btn_header"].configure(text=f"{info['icone']}  {info['titulo']}   {seta}")

        if novo_estado:
            info["container"].pack(fill="x", padx=2, pady=(1, 3))
        else:
            info["container"].pack_forget()

    # ========================================================================
    # ÁREA DE CONTEÚDO PRINCIPAL (TOP HEADER HUD + TELAS DEDICADAS)
    # ========================================================================

    def _criar_area_conteudo(self):
        """Cria o container principal com o Header HUD e instancia as telas dedicadas."""
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.grid(row=0, column=1, sticky="nsew")

        # 1. Top Header HUD
        self.header_hud = ctk.CTkFrame(
            self.content_container,
            height=54,
            corner_radius=0,
            fg_color=theme.HEADER_BG,
            border_width=0,
        )
        self.header_hud.pack(fill="x", side="top")
        self.header_hud.pack_propagate(False)

        # Breadcrumb da tela ativa
        self.lbl_breadcrumb = ctk.CTkLabel(
            self.header_hud,
            text="📍 Estoque & Produtos  ›  Catálogo / Lista",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self.lbl_breadcrumb.pack(side="left", padx=24, pady=16)

        # Lado Direito do HUD: Atalho Backup, Relógio e Conexão com o Banco
        hud_right = ctk.CTkFrame(self.header_hud, fg_color="transparent")
        hud_right.pack(side="right", padx=20, pady=10)

        # Badge de Conexão com o Banco SQLite
        db_badge = ctk.CTkFrame(hud_right, fg_color=theme.INNER_CARD_BG, corner_radius=6, border_width=1, border_color=theme.BORDER_COLOR)
        db_badge.pack(side="right", padx=(10, 0))
        ctk.CTkLabel(
            db_badge,
            text="🟢 SQLite Conectado",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.STOCK_COLOR[1],
        ).pack(padx=10, pady=4)

        # Botão Rápido de Backup no Header (espaçamento uniforme sem artefato de caractere de variação)
        btn_quick_backup = ctk.CTkButton(
            hud_right,
            text="🛡 Backup",
            width=92,
            height=28,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._abrir_modal_backup,
        )
        btn_quick_backup.pack(side="right", padx=(10, 0))

        # Divisor Vertical
        ctk.CTkFrame(hud_right, width=1, height=22, fg_color=theme.BORDER_COLOR).pack(side="right", padx=10)

        # Relógio Digital com Data e Hora
        self.lbl_relogio = ctk.CTkLabel(
            hud_right,
            text="--/--/----  00:00:00",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self.lbl_relogio.pack(side="right")

        # Linha Divisória Inferior do Header
        ctk.CTkFrame(self.content_container, height=1, fg_color=theme.BORDER_COLOR).pack(fill="x")

        # 2. Container das Telas (Views Frame)
        self.views_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.views_frame.pack(fill="both", expand=True)

        # Instanciação das telas
        self.view_catalogo = CatalogView(
            self.views_frame,
            on_data_changed_callback=self._sincronizar_apos_mudanca_produtos,
            on_goto_cadastrar=lambda: self._navegar_subitem("estoque_novo"),
        )

        self.view_novo_produto = ProductFormView(
            self.views_frame,
            on_product_added_callback=self._sincronizar_apos_mudanca_produtos,
            on_goto_catalogo=lambda: self._navegar_subitem("estoque_catalogo"),
        )

        self.view_nova_venda = POSSaleView(
            self.views_frame,
            on_sale_completed_callback=self._sincronizar_apos_venda,
            on_goto_historico=lambda: self._navegar_subitem("pdv_historico"),
            on_cash_closed_callback=self._sincronizar_apos_fechamento_caixa,
        )

        self.view_historico_vendas = SalesHistoryView(
            self.views_frame,
            on_goto_nova_venda=lambda: self._navegar_subitem("pdv_nova_venda"),
            on_venda_cancelada=self._sincronizar_apos_venda,
        )

        self.view_fechamento_dia = DailyClosureView(
            self.views_frame,
            on_goto_exportar=lambda: self._navegar_subitem("rel_exportar"),
        )

        self.view_exportar_excel = ExportExcelView(self.views_frame)
        self.view_dashboard = DashboardView(self.views_frame)

        self.views = {
            "catalogo": self.view_catalogo,
            "novo_produto": self.view_novo_produto,
            "nova_venda": self.view_nova_venda,
            "historico_vendas": self.view_historico_vendas,
            "fechamento_dia": self.view_fechamento_dia,
            "exportar_excel": self.view_exportar_excel,
            "dashboard_analytics": self.view_dashboard,
        }

        # Instancia a view fiscal apenas se a edição suportar
        if edicao_config.permite_modulo_fiscal():
            try:
                from views.fiscal_config_view import FiscalConfigView as FView
                self.view_fiscal_config = FView(
                    self.views_frame,
                    on_mode_changed=self._ao_alterar_modo_fiscal,
                )
                self.views["config_fiscal"] = self.view_fiscal_config
            except Exception:
                pass

    def _ao_alterar_modo_fiscal(self, novo_modo: str):
        """Atualiza a indicação visual do regime operacional no rodapé da barra lateral."""
        self._atualizar_badge_modo_fiscal()

    def _atualizar_badge_modo_fiscal(self):
        """Consulta o banco de dados e sincroniza o rótulo do rodapé."""
        modo = db.obter_modo_emissao()
        if hasattr(self, "lbl_modo_fiscal"):
            if modo == "FISCAL_NFCE":
                self.lbl_modo_fiscal.configure(
                    text="🏛️ Modo: Emissor NFC-e (SEFAZ)",
                    text_color=theme.PRICE_COLOR[1],
                )
            else:
                self.lbl_modo_fiscal.configure(
                    text="🔒 Modo: Controle Interno (Não-Fiscal)",
                    text_color=theme.TEXT_MUTED,
                )

    def _ao_fechar_janela(self):
        """Encerra com segurança os workers de background antes de destruir a janela."""
        try:
            if hasattr(self, "fiscal_sync_worker") and self.fiscal_sync_worker:
                self.fiscal_sync_worker.stop()
        except Exception:
            pass
        self.destroy()

    def _atualizar_relogio(self):
        """Atualiza o relógio dinâmico do HUD a cada segundo."""
        agora = datetime.now().strftime("📅 %d/%m/%Y   ⏰ %H:%M:%S")
        self.lbl_relogio.configure(text=agora)
        self.after(1000, self._atualizar_relogio)

    # ========================================================================
    # NAVEGAÇÃO E SINCRONIZAÇÃO
    # ========================================================================

    def _navegar_subitem(
        self,
        sub_id: str,
        view_key: Optional[str] = None,
        rotulo: Optional[str] = None,
        categoria: Optional[str] = None,
    ):
        """
        Navega para a tela correspondente ou abre modais utilitários (ex: Backup).
        """
        self.registrar_atividade_externa()

        info = self.subitens_botoes.get(sub_id)
        if info:
            view_key = info["view_key"]
            rotulo = info["rotulo"]
            categoria = info["categoria"]

        if not view_key:
            return

        # Tratamento especial para o atalho de backup
        if view_key == "backup_modal":
            self._abrir_modal_backup()
            return

        # Tratamento com senha administrativa para o Dashboard Analítico
        if view_key == "dashboard_analytics":
            self._abrir_dashboard_bi()
            return

        # Tratamento com senha administrativa para o Fechamento do Dia
        if view_key == "fechamento_dia":
            from views.admin_auth_modal import solicitar_senha_admin
            autorizado = solicitar_senha_admin(
                self,
                titulo="Fechamento do Dia (Acesso Restrito)",
                motivo="Digite a senha de administrador para visualizar o fechamento diário do caixa:",
            )
            if not autorizado:
                return

        # Tratamento com senha administrativa para Exportar Planilha
        if view_key == "exportar_excel":
            from views.admin_auth_modal import solicitar_senha_admin
            autorizado = solicitar_senha_admin(
                self,
                titulo="Exportar Planilha (Acesso Restrito)",
                motivo="Digite a senha de administrador para exportar relatórios em planilha:",
            )
            if not autorizado:
                return

        # Tratamento com senha administrativa para a Administração Fiscal & Troca de Regime
        if view_key == "config_fiscal":
            if not edicao_config.permite_modulo_fiscal():
                messagebox.showinfo(
                    "Módulo Fiscal NFC-e",
                    "A Emissão Fiscal NFC-e está disponível nas Edições Fiscal e Completa.",
                    parent=self,
                )
                return
            from views.admin_auth_modal import solicitar_senha_admin
            autorizado = solicitar_senha_admin(
                self,
                titulo="Administração Fiscal (Acesso Restrito)",
                motivo="Digite a senha de administrador para acessar as configurações fiscais e alternância de regime operacional:",
            )
            if not autorizado:
                return

        self.subitem_ativo = sub_id

        # Atualiza o estilo visual dos botões do acordeão
        for sid, item in self.subitens_botoes.items():
            btn = item["button"]
            if sid == sub_id:
                # Estilo da Imagem 3: Ativo / Selecionado (Azul sólido com texto branco)
                btn.configure(
                    fg_color=theme.ACCENT_BLUE,
                    text_color="#FFFFFF",
                    hover_color=theme.ACCENT_BLUE_HOVER,
                    border_width=2,
                    border_color="#60A5FA",
                )
            else:
                # Estilo da Imagem 2: Inativo / Destaque com Borda (Fundo escuro, borda azul 2px, texto azul claro)
                btn.configure(
                    fg_color=theme.INNER_CARD_BG,
                    text_color="#60A5FA",
                    hover_color=theme.BTN_SECONDARY_HOVER,
                    border_width=2,
                    border_color="#3B82F6",
                )

        # Atualiza o Breadcrumb no Header HUD
        limpo_rotulo = (
            rotulo.replace("🏷️", "")
            .replace("➕", "")
            .replace("⚡", "")
            .replace("🕒", "")
            .replace("📋", "")
            .replace("📥", "")
            .replace("🛡️", "")
            .replace("🛡", "")
            .replace("⚙️", "")
            .replace("📈", "")
            .replace("📊", "")
            .replace("🔒", "")
            .strip()
            if rotulo
            else ""
        )
        self.lbl_breadcrumb.configure(text=f"📍 {categoria}  ›  {limpo_rotulo}")

        # Esconde todas as visualizações ativas exceto a selecionada
        for k, v in self.views.items():
            if k != view_key:
                v.pack_forget()

        # Exibe a view dedicada
        view_ativa = self.views.get(view_key)
        if view_ativa:
            view_ativa.pack(fill="both", expand=True)

            if hasattr(view_ativa, "recarregar_dados"):
                precisa = getattr(view_ativa, "_necessita_recarregar", True)
                if precisa:
                    self.after(10, view_ativa.recarregar_dados)

            # Foco ergonômico automático
            if view_key == "novo_produto" and hasattr(view_ativa, "focar_cadastro"):
                self.after(50, view_ativa.focar_cadastro)
            elif view_key == "catalogo" and hasattr(view_ativa, "focar_busca"):
                self.after(50, view_ativa.focar_busca)
            elif view_key == "nova_venda" and hasattr(view_ativa, "focar_nova_venda"):
                self.after(50, view_ativa.focar_nova_venda)
            elif view_key == "historico_vendas" and hasattr(view_ativa, "focar_busca"):
                self.after(50, view_ativa.focar_busca)

    def _sincronizar_apos_mudanca_produtos(self):
        """Quando um produto é cadastrado ou editado, sincroniza catálogo e PDV sob demanda."""
        for v in (self.view_catalogo, self.view_novo_produto, self.view_nova_venda):
            if v.winfo_ismapped() and hasattr(v, "recarregar_dados"):
                v.recarregar_dados()
            else:
                v._necessita_recarregar = True

    def _sincronizar_apos_venda(self):
        """Quando uma venda ocorre, sincroniza catálogo, histórico, fechamento e dashboard sob demanda."""
        alvos = [self.view_catalogo, self.view_nova_venda, self.view_historico_vendas, self.view_fechamento_dia]
        if hasattr(self, "view_exportar_excel"):
            alvos.append(self.view_exportar_excel)
        if hasattr(self, "view_dashboard"):
            alvos.append(self.view_dashboard)

        for v in alvos:
            if v.winfo_ismapped() and hasattr(v, "recarregar_dados"):
                v.recarregar_dados()
            else:
                v._necessita_recarregar = True

    def _sincronizar_apos_fechamento_caixa(self):
        """Quando o caixa é fechado no PDV, sincroniza interfaces sob demanda."""
        alvos = [self.view_nova_venda, self.view_historico_vendas, self.view_fechamento_dia]
        if hasattr(self, "view_exportar_excel"):
            alvos.append(self.view_exportar_excel)
        if hasattr(self, "view_dashboard"):
            alvos.append(self.view_dashboard)

        for v in alvos:
            if v.winfo_ismapped() and hasattr(v, "recarregar_dados"):
                v.recarregar_dados()
            else:
                v._necessita_recarregar = True

    def _sincronizar_apos_restauracao(self):
        """Sincroniza todas as interfaces após restauração de uma cópia de segurança."""
        self._sincronizar_apos_mudanca_produtos()
        self._sincronizar_apos_venda()
        self._atualizar_badge_modo_fiscal()

    def _tratar_atalho_f2(self, event=None):
        """
        Tratamento unificado da tecla F2:
        - Se o usuário já estiver na tela de Nova Venda (PDV), aciona a confirmação da venda imediatamente.
        - Se estiver em outra tela, navega diretamente para a tela de Nova Venda (PDV).
        """
        try:
            if self.grab_current() is not None:
                return
        except Exception:
            pass

        if self.subitem_ativo == "pdv_nova_venda" and hasattr(self, "view_nova_venda"):
            self.view_nova_venda.confirmar_venda_atalho()
            return "break"
        else:
            self._navegar_subitem("pdv_nova_venda")
            return "break"

    def _tratar_atalho_f3(self, event=None):
        """
        Tratamento do atalho global F3:
        Abre o modal de busca rápida no estoque para localizar produtos por nome ou código de barras.
        Se o usuário estiver em outra tela, navega para o PDV e abre o modal.
        """
        try:
            if self.grab_current() is not None:
                return
        except Exception:
            pass

        if hasattr(self, "view_nova_venda"):
            if self.subitem_ativo != "pdv_nova_venda":
                self._navegar_subitem("pdv_nova_venda")
            self.after(50, self.view_nova_venda._abrir_modal_busca_estoque)
            return "break"

    def _tratar_atalho_f4(self, event=None):
        """
        Tratamento do atalho global F4:
        Adiciona o produto selecionado com sua respectiva quantidade ao carrinho de compras no PDV.
        """
        try:
            if self.grab_current() is not None:
                return
        except Exception:
            pass

        if hasattr(self, "view_nova_venda") and self.subitem_ativo == "pdv_nova_venda":
            self.view_nova_venda._adicionar_ao_carrinho()
            return "break"



def main():
    """Ponto de entrada padrão (Edição Completa ou via argumento)."""
    edicao = "COMPLETO"
    if len(sys.argv) > 1:
        arg = sys.argv[1].upper().replace("--EDITION=", "").replace("-E=", "").strip()
        if "NAO_FISCAL" in arg or "NAOFISCAL" in arg:
            edicao = "NAO_FISCAL"
        elif "FISCAL" in arg:
            edicao = "FISCAL"

    app = App(edicao=edicao)
    app.mainloop()


if __name__ == "__main__":
    main()
