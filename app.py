"""
Aplicação Principal - Sistema de Gestão de Vendas e Inventário
Arquivo: app.py

Ponto de entrada da aplicação desktop construída com CustomTkinter.
Gerencia a janela principal, barra lateral com logotipo e menu acordeão,
header HUD com breadcrumb dinâmico e relógio em tempo real, persistência
de tema Dark/Light no SQLite, além da navegação para 6 telas dedicadas e independentes:
  1. Catálogo / Lista de Produtos (com busca por EAN e importação de XML da NF-e)
  2. Cadastrar Novo Produto (com foco automático e suporte a leitor USB de código de barras)
  3. Nova Venda Balcão / PDV (com atalho F2 e leitor óptico USB)
  4. Histórico de Vendas de Hoje
  5. Fechamento Consolidado do Dia
  6. Central de Exportação Excel (.xlsx)
"""

import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any
import customtkinter as ctk

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

import database as db
import theme
from views.catalog_view import CatalogView
from views.product_form_view import ProductFormView
from views.pos_sale_view import POSSaleView
from views.sales_history_view import SalesHistoryView
from views.daily_closure_view import DailyClosureView
from views.export_excel_view import ExportExcelView
from views.license_modal import LicenseActivationModal
from views.fiscal_config_view import FiscalConfigView
from fiscal.sync_worker import FiscalSyncWorker
import license_manager as lm


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
    """Janela principal da aplicação com layout moderno, acordeão e HUD."""

    def __init__(self):
        super().__init__()

        # 1. Inicializa o banco de dados SQLite local
        db.init_db()

        # 2. Carrega a preferência de tema do usuário salva no banco
        self.tema_atual = db.obter_config("appearance_mode", "Dark")
        ctk.set_appearance_mode(self.tema_atual)

        # 3. Validação do Sistema de Licenciamento Criptográfico
        self.licenca_valida, self.licenca_msg, self.info_licenca = lm.validar_licenca()

        # Configurações da Janela
        self.title("Central de Vendas")
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

        # Atualiza badge de licença na barra lateral
        self._atualizar_badge_licenca()

        # Atualiza badge de regime fiscal
        self._atualizar_badge_modo_fiscal()

        # Inicia o relógio dinâmico no HUD
        self._atualizar_relogio()

        # Inicialização do Worker de Sincronização Silenciosa Fiscal em Segundo Plano
        self.fiscal_sync_worker = FiscalSyncWorker(intervalo_segundos=120)
        self.fiscal_sync_worker.start()
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar_janela)

        # Atalhos rápidos de teclado
        self.bind("<F1>", lambda e: self._navegar_subitem("estoque_catalogo"))
        self.bind_all("<F2>", self._tratar_atalho_f2)
        self.bind("<F3>", lambda e: self._navegar_subitem("rel_fechamento"))

        # Controle de Ativação de Licença:
        if not self.licenca_valida:
            self.withdraw()
            self.after(50, self._exibir_modal_ativacao_obrigatoria)
        else:
            self.after(10, self._centralizar_janela)
            self._navegar_subitem("estoque_catalogo")

    def _centralizar_janela(self):
        """Posiciona a janela no centro do monitor do usuário."""
        self.update_idletasks()
        largura = self.winfo_width()
        altura = self.winfo_height()
        pos_x = (self.winfo_screenwidth() - largura) // 2
        pos_y = (self.winfo_screenheight() - altura) // 2
        self.geometry(f"{largura}x{altura}+{pos_x}+{pos_y}")

    # ========================================================================
    # BARRA LATERAL (SIDEBAR COM LOGO E ACORDEÃO)
    # ========================================================================

    def _criar_sidebar(self):
        """Constrói a barra lateral de navegação com logotipo e menus ramificados."""
        self.sidebar_frame = ctk.CTkFrame(
            self,
            width=290,
            corner_radius=0,
            fg_color=theme.SIDEBAR_BG,
            border_width=0,
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False)

        # 1. Área do Logotipo da Empresa
        self._criar_area_logotipo()

        # Divisor Superior
        ctk.CTkFrame(self.sidebar_frame, height=1, fg_color=theme.BORDER_COLOR).pack(fill="x", padx=16, pady=(12, 14))

        # 2. Container com Scroll para Menus Acordeão
        self.menu_scroll = ctk.CTkScrollableFrame(self.sidebar_frame, fg_color="transparent")
        self.menu_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # Estrutura com as 6 telas dedicadas
        estrutura_menu = [
            {
                "id": "estoque",
                "titulo": "Estoque & Produtos",
                "icone": "📦",
                "subitens": [
                    ("estoque_catalogo", "🏷️ Catálogo / Lista", "catalogo"),
                    ("estoque_novo", "➕ Cadastrar Produto", "novo_produto"),
                ],
            },
            {
                "id": "pdv",
                "titulo": "Frente de Caixa / PDV",
                "icone": "🛒",
                "subitens": [
                    ("pdv_nova_venda", "⚡ Nova Venda Balcão", "nova_venda"),
                    ("pdv_historico", "🕒 Histórico de Hoje", "historico_vendas"),
                ],
            },
            {
                "id": "relatorios",
                "titulo": "Relatórios & Excel",
                "icone": "📊",
                "subitens": [
                    ("rel_fechamento", "📋 Fechamento do Dia", "fechamento_dia"),
                    ("rel_exportar", "📥 Exportar Planilha", "exportar_excel"),
                ],
            },
            {
                "id": "fiscal",
                "titulo": "Fiscal & Configurações",
                "icone": "🏛️",
                "subitens": [
                    ("fiscal_config", "⚙️ Emissão Fiscal / NFC-e", "config_fiscal"),
                ],
            },
        ]

        for sec in estrutura_menu:
            self._criar_secao_acordeao(sec)

        # Abre as seções por padrão
        for sec_id in self.secoes_acordeao:
            self._toggle_secao(sec_id, forcar_abrir=True)

        # 3. Rodapé da Sidebar
        footer_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        footer_frame.pack(side="bottom", fill="x", padx=14, pady=(8, 14))

        # Divisor Rodapé
        ctk.CTkFrame(footer_frame, height=1, fg_color=theme.BORDER_COLOR).pack(fill="x", pady=(0, 10))

        # Card de Status da Licença
        self.card_licenca = ctk.CTkFrame(footer_frame, fg_color=theme.INNER_CARD_BG, corner_radius=8, border_width=1, border_color=theme.BORDER_COLOR)
        self.card_licenca.pack(fill="x", pady=(0, 10))

        self.lbl_licenca_status = ctk.CTkLabel(
            self.card_licenca,
            text="Carregando licença...",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.STOCK_COLOR[1],
        )
        self.lbl_licenca_status.pack(anchor="w", padx=10, pady=(6, 1))

        self.lbl_licenca_detalhes = ctk.CTkLabel(
            self.card_licenca,
            text="",
            font=ctk.CTkFont(size=9),
            text_color=theme.TEXT_SECONDARY,
        )
        self.lbl_licenca_detalhes.pack(anchor="w", padx=10, pady=(0, 4))

        self.btn_renovar_lic = ctk.CTkButton(
            self.card_licenca,
            text="🔑 Renovar / Alterar Chave",
            height=24,
            corner_radius=4,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._abrir_modal_renovacao,
        )
        self.btn_renovar_lic.pack(fill="x", padx=8, pady=(0, 6))

        # Modo Operacional: Controle Interno Não-Fiscal vs Fiscal NFC-e
        self.lbl_modo_fiscal = ctk.CTkLabel(
            footer_frame,
            text="🔒 Modo: Controle Interno (Não-Fiscal)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=theme.TEXT_MUTED,
        )
        self.lbl_modo_fiscal.pack(anchor="w", pady=(0, 2))

        # Versão do Sistema
        lbl_versao = ctk.CTkLabel(
            footer_frame,
            text="Versão 1.4.0 • Pro Edition",
            font=ctk.CTkFont(size=10),
            text_color=theme.TEXT_MUTED,
        )
        lbl_versao.pack(anchor="w", pady=(0, 6))

        # Alternador de Modo de Aparência (Dark / Light / System) com Persistência
        self.tema_menu = ctk.CTkOptionMenu(
            footer_frame,
            values=["Dark", "Light", "System"],
            command=self._ao_alterar_tema,
            height=28,
            corner_radius=6,
            fg_color=theme.BTN_SECONDARY_BG,
            button_color=theme.ACCENT_BLUE,
            button_hover_color=theme.ACCENT_BLUE_HOVER,
            dropdown_fg_color=theme.CARD_BG,
            text_color=theme.BTN_SECONDARY_TEXT,
        )
        self.tema_menu.set(self.tema_atual)
        self.tema_menu.pack(fill="x")

    def _ao_alterar_tema(self, novo_modo: str):
        """Aplica instantaneamente o modo de aparência e persiste a escolha no SQLite."""
        self.tema_atual = novo_modo
        ctk.set_appearance_mode(novo_modo)
        db.salvar_config("appearance_mode", novo_modo)

    def _atualizar_badge_licenca(self):
        """Atualiza visualmente o card de licença na barra lateral."""
        if not hasattr(self, "card_licenca") or not hasattr(self, "info_licenca"):
            return

        info = self.info_licenca
        if info.get("is_lifetime"):
            self.lbl_licenca_status.configure(
                text="💎 Licença: Vitalícia",
                text_color=theme.PRICE_COLOR[1],
            )
            cliente = info.get("client", "Comercial")
            self.lbl_licenca_detalhes.configure(text=f"Cliente: {cliente}")
            self.card_licenca.configure(border_color="#0284C7")
        elif info.get("status") == "VALID":
            dias = info.get("days_remaining", 0)
            cor = theme.STOCK_COLOR[1] if dias > 5 else theme.WARNING_COLOR[1]
            eh_trial = info.get("plan") == "15_DAYS"
            titulo_lic = f"⭐ Trial: {dias} dias restantes" if eh_trial else f"⏳ Licença: {dias} dias restantes"
            self.lbl_licenca_status.configure(
                text=titulo_lic,
                text_color=cor,
            )
            exp_str = info.get("expires_at", "")
            if exp_str:
                try:
                    dt_fmt = datetime.fromisoformat(exp_str).strftime("%d/%m/%Y")
                    desc_sufixo = " (Trial 15D)" if eh_trial else ""
                    self.lbl_licenca_detalhes.configure(text=f"Expira em: {dt_fmt}{desc_sufixo}")
                except Exception:
                    self.lbl_licenca_detalhes.configure(text="Plano temporário ativo")
            else:
                self.lbl_licenca_detalhes.configure(text="Plano temporário ativo")
            self.card_licenca.configure(border_color=cor)
        else:
            self.lbl_licenca_status.configure(
                text="❌ Licença Bloqueada",
                text_color=theme.ACCENT_RED[1],
            )
            self.lbl_licenca_detalhes.configure(text="Clique para ativar chave")
            self.card_licenca.configure(border_color=theme.ACCENT_RED[1])

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

    def _apos_ativar_licenca(self):
        """Executado após ativação inicial com sucesso: libera a tela principal."""
        self.licenca_valida, self.licenca_msg, self.info_licenca = lm.validar_licenca()
        self._atualizar_badge_licenca()
        self.deiconify()
        self._centralizar_janela()
        self._navegar_subitem("estoque_catalogo")

    def _apos_renovar_licenca(self):
        """Executado após renovação de chave no rodapé."""
        self.licenca_valida, self.licenca_msg, self.info_licenca = lm.validar_licenca()
        self._atualizar_badge_licenca()

    def _criar_area_logotipo(self):
        """Carrega e exibe o logotipo da empresa (assets/logo.png) ou renderiza fallback moderno."""
        logo_container = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        logo_container.pack(fill="x", padx=14, pady=(22, 10))

        caminho_logo = obter_caminho_recurso(os.path.join("assets", "logo.png"))
        logo_carregado = False

        if PIL_AVAILABLE and os.path.exists(caminho_logo):
            try:
                pil_img = Image.open(caminho_logo)
                orig_w, orig_h = pil_img.size
                alvo_w = 260
                alvo_h = int((orig_h / orig_w) * alvo_w)
                alvo_h = min(alvo_h, 105)

                logo_ctk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(alvo_w, alvo_h))
                lbl_logo_img = ctk.CTkLabel(logo_container, image=logo_ctk, text="")
                lbl_logo_img.pack(pady=6)
                logo_carregado = True
            except Exception:
                logo_carregado = False

        if not logo_carregado:
            card_fallback = ctk.CTkFrame(logo_container, fg_color=theme.INNER_CARD_BG, corner_radius=12, border_width=1, border_color=theme.BORDER_COLOR)
            card_fallback.pack(fill="x", pady=6)

            inner = ctk.CTkFrame(card_fallback, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=14)

            badge_icon = ctk.CTkFrame(inner, fg_color=theme.ACCENT_BLUE, corner_radius=10, width=54, height=54)
            badge_icon.pack_propagate(False)
            badge_icon.pack(side="left", padx=(0, 12))
            ctk.CTkLabel(badge_icon, text="🛍️", font=ctk.CTkFont(size=26)).pack(expand=True)

            text_frame = ctk.CTkFrame(inner, fg_color="transparent")
            text_frame.pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(text_frame, text="CENTRAL DE VENDAS", font=ctk.CTkFont(size=14, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w")
            ctk.CTkLabel(text_frame, text="PDV & ESTOQUE", font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY).pack(anchor="w")

    def _criar_secao_acordeao(self, config_secao: dict):
        """Cria uma categoria com cabeçalho clicável e container de subitens expansíveis."""
        sec_id = config_secao["id"]
        titulo = config_secao["titulo"]
        icone = config_secao["icone"]
        subitens = config_secao["subitens"]

        secao_frame = ctk.CTkFrame(self.menu_scroll, fg_color="transparent")
        secao_frame.pack(fill="x", pady=(2, 4))

        # Botão Cabeçalho da Categoria
        btn_header = ctk.CTkButton(
            secao_frame,
            text=f"{icone}  {titulo}",
            height=38,
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
        btn_header.pack(fill="x", padx=4, pady=2)

        # Container dos Subitens
        sub_container = ctk.CTkFrame(secao_frame, fg_color="transparent")
        sub_container.pack(fill="x", padx=4, pady=(2, 6))

        for sub_id, rotulo, view_key in subitens:
            btn_sub = ctk.CTkButton(
                sub_container,
                text=f"     {rotulo}",
                height=34,
                corner_radius=6,
                font=ctk.CTkFont(size=11),
                anchor="w",
                fg_color="transparent",
                text_color=theme.TEXT_SECONDARY,
                hover_color=theme.BTN_SECONDARY_HOVER,
                command=lambda sid=sub_id, vk=view_key, r=rotulo, cat=titulo: self._navegar_subitem(
                    sid, vk, r, cat
                ),
            )
            btn_sub.pack(fill="x", padx=(10, 4), pady=1)
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
            info["container"].pack(fill="x", padx=4, pady=(2, 6))
        else:
            info["container"].pack_forget()

    # ========================================================================
    # ÁREA DE CONTEÚDO PRINCIPAL (TOP HEADER HUD + 6 TELAS DEDICADAS)
    # ========================================================================

    def _criar_area_conteudo(self):
        """Cria o container principal com o Header HUD e instancia as 6 telas dedicadas."""
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

        # Lado Direito do HUD: Relógio e Conexão com o Banco
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

        # Instanciação das 6 telas distintas e especializadas
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

        self.view_fiscal_config = FiscalConfigView(
            self.views_frame,
            on_mode_changed=self._ao_alterar_modo_fiscal,
        )

        # Dicionário de Telas Independentes
        self.views = {
            "catalogo": self.view_catalogo,
            "novo_produto": self.view_novo_produto,
            "nova_venda": self.view_nova_venda,
            "historico_vendas": self.view_historico_vendas,
            "fechamento_dia": self.view_fechamento_dia,
            "exportar_excel": self.view_exportar_excel,
            "config_fiscal": self.view_fiscal_config,
        }

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
        Navega para a tela dedicada e independente correspondente ao subitem,
        atualiza o breadcrumb do HUD e destaca visualmente o item ativo.
        """
        info = self.subitens_botoes.get(sub_id)
        if info:
            view_key = info["view_key"]
            rotulo = info["rotulo"]
            categoria = info["categoria"]

        if not view_key:
            return

        self.subitem_ativo = sub_id

        # Atualiza o estilo visual dos botões do acordeão
        for sid, item in self.subitens_botoes.items():
            btn = item["button"]
            if sid == sub_id:
                btn.configure(fg_color=theme.ACCENT_BLUE, text_color=theme.ACCENT_BLUE_TEXT, hover_color=theme.ACCENT_BLUE_HOVER)
            else:
                btn.configure(fg_color="transparent", text_color=theme.TEXT_SECONDARY, hover_color=theme.BTN_SECONDARY_HOVER)

        # Atualiza o Breadcrumb no Header HUD
        limpo_rotulo = (
            rotulo.replace("🏷️", "")
            .replace("➕", "")
            .replace("⚡", "")
            .replace("🕒", "")
            .replace("📋", "")
            .replace("📥", "")
            .strip()
            if rotulo
            else ""
        )
        self.lbl_breadcrumb.configure(text=f"📍 {categoria}  ›  {limpo_rotulo}")

        # Esconde todas as 6 visualizações
        for v in self.views.values():
            v.pack_forget()

        # Exibe a view dedicada
        view_ativa = self.views.get(view_key)
        if view_ativa:
            view_ativa.pack(fill="both", expand=True)

            if hasattr(view_ativa, "recarregar_dados"):
                view_ativa.recarregar_dados()

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
        """Quando um produto é cadastrado ou editado, sincroniza catálogo e PDV."""
        self.view_catalogo.recarregar_dados()
        self.view_novo_produto.recarregar_dados()
        self.view_nova_venda.recarregar_dados()

    def _sincronizar_apos_venda(self):
        """Quando uma venda ocorre, sincroniza catálogo, histórico e fechamento."""
        self.view_catalogo.recarregar_dados()
        self.view_nova_venda.recarregar_dados()
        self.view_historico_vendas.recarregar_dados()
        self.view_fechamento_dia.recarregar_dados()
        if hasattr(self, "view_exportar_excel"):
            self.view_exportar_excel.recarregar_dados()

    def _tratar_atalho_f2(self, event=None):
        """
        Tratamento unificado da tecla F2:
        - Se o usuário já estiver na tela de Nova Venda (PDV), aciona a confirmação da venda imediatamente.
        - Se estiver em outra tela, navega diretamente para a tela de Nova Venda (PDV).
        """
        try:
            # Se houver modal bloqueante aberto, ignora
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


def main():
    """Ponto de entrada da aplicação."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
