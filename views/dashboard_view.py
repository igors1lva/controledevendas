"""
Dashboard Analítico e In-App Analytics (BI Gerencial)
Arquivo: views/dashboard_view.py

Painel visual integrado para visualização estratégica de desempenho comercial:
- Cartões de KPI com Faturamento, Lucro Real, Margem %, Ticket Médio e Vendas.
- Gráfico de Barras interativo para Evolução Diária das Vendas.
- Gráfico Donut / Rosca para Distribuição de Métodos de Pagamento.
- Ranking Top 10 Produtos Mais Vendidos com Curva ABC e barras de lucratividade.
- Apuração de Horários de Pico (Manhã, Tarde, Noite) e Insights Automatizados.
- Filtros rápidos por período (Hoje, 7 Dias, 30 Dias, Mês Atual, Todo o Histórico).
"""

import os
import math
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
from typing import Optional, Dict, Any, List
import customtkinter as ctk

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

import theme
import database as db
import reports


class DashboardView(ctk.CTkFrame):
    """Tela de Dashboard Analítico In-App com gráficos nativos em Canvas e KPIs."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.periodo_atual = "hoje"
        self.botoes_periodo: Dict[str, ctk.CTkButton] = {}

        self._criar_layout()
        self.recarregar_dados()

    def _criar_layout(self):
        # 1. Top Bar com Título, Seletor de Período e Ações
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=24, pady=(16, 12))

        # Coluna Título
        col_tit = ctk.CTkFrame(top_bar, fg_color="transparent")
        col_tit.pack(side="left")

        lbl_tit = ctk.CTkLabel(
            col_tit,
            text="📈 Dashboard Analítico & In-App Analytics (BI)",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        lbl_tit.pack(anchor="w")

        self.lbl_subtitulo = ctk.CTkLabel(
            col_tit,
            text="Inteligência de vendas em tempo real, apuração de margem líquida e curva ABC.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        )
        self.lbl_subtitulo.pack(anchor="w")

        # Coluna Ações e Período (Lado Direito)
        col_acoes = ctk.CTkFrame(top_bar, fg_color="transparent")
        col_acoes.pack(side="right")

        # Botão Atualizar
        btn_refresh = ctk.CTkButton(
            col_acoes,
            text="🔄 Atualizar",
            width=90,
            height=34,
            corner_radius=7,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self.recarregar_dados,
        )
        btn_refresh.pack(side="right", padx=(8, 0))

        # Botão Exportar Excel
        btn_export = ctk.CTkButton(
            col_acoes,
            text="📥 Exportar Excel",
            width=115,
            height=34,
            corner_radius=7,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            command=self._exportar_relatorio_excel,
        )
        btn_export.pack(side="right")

        # Seletor de Períodos (Pills)
        bar_periodos = ctk.CTkFrame(self, fg_color="transparent")
        bar_periodos.pack(fill="x", padx=24, pady=(0, 10))

        ctk.CTkLabel(
            bar_periodos,
            text="Período de Análise:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 8))

        periodos = [
            ("hoje", "📅 Hoje"),
            ("7d", "📊 Últimos 7 Dias"),
            ("30d", "🗓️ Últimos 30 Dias"),
            ("mes", "📆 Este Mês"),
            ("todos", "🌐 Todo o Período"),
        ]

        for p_id, p_label in periodos:
            btn_p = ctk.CTkButton(
                bar_periodos,
                text=p_label,
                height=30,
                corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=theme.ACCENT_BLUE if p_id == self.periodo_atual else theme.INNER_CARD_BG,
                text_color="#FFFFFF" if p_id == self.periodo_atual else theme.TEXT_SECONDARY,
                hover_color=theme.ACCENT_BLUE_HOVER,
                border_width=1,
                border_color=theme.BORDER_COLOR,
                command=lambda pid=p_id: self._mudar_periodo(pid),
            )
            btn_p.pack(side="left", padx=3)
            self.botoes_periodo[p_id] = btn_p

        # 2. Container com Scroll para o Conteúdo do Dashboard
        self.scroll_dash = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_dash.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # 3. Cards de KPIs (6 Cards Principais com Estornos / Canceladas)
        self.grid_kpis = ctk.CTkFrame(self.scroll_dash, fg_color="transparent")
        self.grid_kpis.pack(fill="x", pady=(0, 12))
        for col_i in range(6):
            self.grid_kpis.grid_columnconfigure(col_i, weight=1)

        # Referências aos labels para atualização dinâmica
        self.lbl_kpi_fat = None
        self.lbl_kpi_fat_sub = None
        self.lbl_kpi_lucro = None
        self.lbl_kpi_margem = None
        self.lbl_kpi_cancel = None
        self.lbl_kpi_cancel_sub = None
        self.lbl_kpi_ticket = None
        self.lbl_kpi_vendas = None
        self.lbl_kpi_cmv = None

        self._construir_cards_kpi()

        # 4. Linha de Gráficos Centrais (Evolução Diária + Métodos de Pagamento)
        self.row_graficos = ctk.CTkFrame(self.scroll_dash, fg_color="transparent")
        self.row_graficos.pack(fill="x", pady=(0, 12))
        self.row_graficos.grid_columnconfigure(0, weight=6)
        self.row_graficos.grid_columnconfigure(1, weight=4)

        # Gráfico 1: Evolução Diária (Barras)
        self.card_graf_diario = ctk.CTkFrame(self.row_graficos, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        self.card_graf_diario.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)

        head_gd = ctk.CTkFrame(self.card_graf_diario, fg_color="transparent")
        head_gd.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(head_gd, text="📊 Evolução das Vendas no Período", font=ctk.CTkFont(size=13, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")
        self.lbl_tot_graf_diario = ctk.CTkLabel(head_gd, text="R$ 0,00", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme.ACCENT_BLUE)
        self.lbl_tot_graf_diario.pack(side="right")

        self.canvas_diario = tk.Canvas(self.card_graf_diario, height=210, bg="#0F172A", highlightthickness=0)
        self.canvas_diario.pack(fill="x", padx=16, pady=(0, 12))

        # Gráfico 2: Métodos de Pagamento (Donut)
        self.card_graf_pgto = ctk.CTkFrame(self.row_graficos, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        self.card_graf_pgto.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=4)

        head_gp = ctk.CTkFrame(self.card_graf_pgto, fg_color="transparent")
        head_gp.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(head_gp, text="🍩 Métodos de Pagamento", font=ctk.CTkFont(size=13, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")

        self.canvas_pgto = tk.Canvas(self.card_graf_pgto, height=210, bg="#0F172A", highlightthickness=0)
        self.canvas_pgto.pack(fill="x", padx=16, pady=(0, 12))

        # 5. Linha Inferior (Top Produtos Curva ABC + Horários de Pico e Insights)
        self.row_inferior = ctk.CTkFrame(self.scroll_dash, fg_color="transparent")
        self.row_inferior.pack(fill="x", pady=(0, 12))
        self.row_inferior.grid_columnconfigure(0, weight=6)
        self.row_inferior.grid_columnconfigure(1, weight=4)

        # Card Top Produtos
        self.card_top_produtos = ctk.CTkFrame(self.row_inferior, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        self.card_top_produtos.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)

        head_tp = ctk.CTkFrame(self.card_top_produtos, fg_color="transparent")
        head_tp.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(head_tp, text="🏆 Top Produtos Mais Vendidos (Curva ABC)", font=ctk.CTkFont(size=13, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")

        self.box_produtos_lista = ctk.CTkFrame(self.card_top_produtos, fg_color="transparent")
        self.box_produtos_lista.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        # Card Horários de Pico & Insights
        self.card_insights = ctk.CTkFrame(self.row_inferior, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        self.card_insights.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=4)

        head_ins = ctk.CTkFrame(self.card_insights, fg_color="transparent")
        head_ins.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(head_ins, text="⏰ Horários de Maior Movimento", font=ctk.CTkFont(size=13, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")

        self.box_insights_conteudo = ctk.CTkFrame(self.card_insights, fg_color="transparent")
        self.box_insights_conteudo.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        # 6. Card de Log de Transações & Estornos do Período
        self.card_logs = ctk.CTkFrame(self.scroll_dash, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        self.card_logs.pack(fill="x", pady=(0, 16))

        head_logs = ctk.CTkFrame(self.card_logs, fg_color="transparent")
        head_logs.pack(fill="x", padx=16, pady=(12, 6))

        col_hlogs = ctk.CTkFrame(head_logs, fg_color="transparent")
        col_hlogs.pack(side="left")

        ctk.CTkLabel(
            col_hlogs,
            text="📋 Log de Transações & Estornos do Período",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            col_hlogs,
            text="Registro detalhado das operações com identificação de vendas concluídas e cancelamentos devidamente abatidos do faturamento.",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w")

        self.box_logs_conteudo = ctk.CTkFrame(self.card_logs, fg_color="transparent")
        self.box_logs_conteudo.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        # 7. Linha de Personalização Visual & Proteção de Tela
        self.row_customizacao = ctk.CTkFrame(self.scroll_dash, fg_color="transparent")
        self.row_customizacao.pack(fill="x", pady=(0, 16))
        self.row_customizacao.grid_columnconfigure(0, weight=1)
        self.row_customizacao.grid_columnconfigure(1, weight=1)

        # Card A: Personalização do Logotipo da Empresa
        self._construir_card_personalizacao_logo()

        # Card B: Configurações da Tela de Descanso Inteligente (Screensaver)
        self._construir_card_tela_descanso()

    def _obter_caminho_base_app(self) -> str:
        """Retorna o diretório base da aplicação onde customizações e mídias são gravadas."""
        import sys
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _construir_card_personalizacao_logo(self):
        """Constrói o card de personalização do logotipo da empresa no menu lateral."""
        card = ctk.CTkFrame(self.row_customizacao, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)

        # Cabeçalho
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(head, text="🖼️ Identidade Visual & Logotipo da Empresa", font=ctk.CTkFont(size=13, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(head, text="Personalize o logotipo exibido no topo da barra lateral do sistema.", font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY).pack(anchor="w")

        # Corpo
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        # Aviso sobre dimensões padronizadas
        info_badge = ctk.CTkFrame(body, fg_color=theme.INNER_CARD_BG, corner_radius=6, border_width=1, border_color=theme.BORDER_COLOR)
        info_badge.pack(fill="x", pady=(4, 10))
        ctk.CTkLabel(
            info_badge,
            text="📐 Dimensão Recomendada: 480 × 160 px (Proporção 3:1)\nFormatos aceitos: PNG com fundo transparente ou JPG.",
            font=ctk.CTkFont(size=10),
            text_color="#38BDF8",
            justify="left",
        ).pack(padx=10, pady=8, anchor="w")

        # Container do Preview do Logotipo Ativo
        preview_box = ctk.CTkFrame(body, fg_color="#0F172A", corner_radius=8, height=95, border_width=1, border_color=theme.BORDER_COLOR)
        preview_box.pack(fill="x", pady=(0, 6))
        preview_box.pack_propagate(False)

        self.lbl_preview_logo = ctk.CTkLabel(preview_box, text="")
        self.lbl_preview_logo.pack(expand=True)

        self.lbl_status_logo = ctk.CTkLabel(body, text="", font=ctk.CTkFont(size=10, slant="italic"), text_color=theme.TEXT_MUTED)
        self.lbl_status_logo.pack(anchor="w", pady=(0, 8))

        # Linha de Botões de Ação
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x")

        btn_alterar = ctk.CTkButton(
            btn_row,
            text="📁 Alterar Logotipo...",
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            command=self._acao_alterar_logotipo,
        )
        btn_alterar.pack(side="left", fill="x", expand=True, padx=(0, 4))

        btn_restaurar = ctk.CTkButton(
            btn_row,
            text="🔄 Restaurar Padrão",
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._acao_restaurar_logotipo,
        )
        btn_restaurar.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Atualiza o preview inicial
        self._atualizar_preview_logotipo()

    def _atualizar_preview_logotipo(self):
        """Recarrega a miniatura do logotipo ativo no painel."""
        caminho_custom = db.obter_config("custom_logo_path", "")
        usa_custom = bool(caminho_custom and os.path.exists(caminho_custom))

        if usa_custom:
            caminho_img = caminho_custom
            self.lbl_status_logo.configure(text=f"Logotipo personalizado: {os.path.basename(caminho_custom)}")
        else:
            caminho_img = os.path.join(self._obter_caminho_base_app(), "assets", "logo.png")
            self.lbl_status_logo.configure(text="Utilizando o logotipo padrão do sistema")

        if PIL_AVAILABLE and os.path.exists(caminho_img):
            try:
                with Image.open(caminho_img) as f_img:
                    pil_img = f_img.copy()
                alvo_w = 210
                alvo_h = int((pil_img.height / pil_img.width) * alvo_w)
                alvo_h = min(alvo_h, 75)
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(alvo_w, alvo_h))
                self.lbl_preview_logo.configure(image=ctk_img, text="")
                self.lbl_preview_logo.image = ctk_img
            except Exception:
                self.lbl_preview_logo.configure(image=None, text="[Pré-visualização Indisponível]")
        else:
            self.lbl_preview_logo.configure(image=None, text="[Arquivo de Logo Não Encontrado]")

    def _acao_alterar_logotipo(self):
        """Permite ao cliente carregar seu logotipo, padronizando para as dimensões de 480x160 px."""
        caminho = filedialog.askopenfilename(
            title="Selecione o Logotipo da sua Empresa (Dimensões: 480x160 px)",
            filetypes=[("Imagens PNG / JPG", "*.png;*.jpg;*.jpeg"), ("Todos os arquivos", "*.*")]
        )
        if not caminho:
            return

        if not PIL_AVAILABLE:
            messagebox.showerror("Erro", "Biblioteca PIL não está disponível.")
            return

        try:
            pil_img = Image.open(caminho).convert("RGBA")
            orig_w, orig_h = pil_img.size

            # Se a imagem tiver dimensões diferentes de 480x160, ajusta e centraliza sem distorcer
            if orig_w == 480 and orig_h == 160:
                final_img = pil_img
            else:
                final_img = Image.new("RGBA", (480, 160), (0, 0, 0, 0))
                ratio = min(480 / orig_w, 160 / orig_h)
                novo_w = max(1, int(orig_w * ratio))
                novo_h = max(1, int(orig_h * ratio))
                redimensionada = pil_img.resize((novo_w, novo_h), Image.Resampling.LANCZOS)
                pos_x = (480 - novo_w) // 2
                pos_y = (160 - novo_h) // 2
                final_img.paste(redimensionada, (pos_x, pos_y), redimensionada)

            # Salva na pasta base da aplicação como custom_logo.png
            destino = os.path.join(self._obter_caminho_base_app(), "custom_logo.png")
            final_img.save(destino, "PNG")

            # Persiste no banco de dados SQLite
            db.salvar_config("custom_logo_path", destino)

            # Atualiza o preview no Dashboard
            self._atualizar_preview_logotipo()

            # Notifica a janela principal para atualizar a barra lateral imediatamente
            app = self.winfo_toplevel()
            if hasattr(app, "atualizar_logotipo_sidebar"):
                app.atualizar_logotipo_sidebar()

            messagebox.showinfo(
                "Logotipo Atualizado",
                "O logotipo da empresa foi atualizado com sucesso e padronizado em 480×160 px!\nA barra lateral já reflete a alteração."
            )
        except Exception as e:
            messagebox.showerror("Erro ao Processar Imagem", f"Não foi possível carregar a imagem selecionada:\n{str(e)}")

    def _acao_restaurar_logotipo(self):
        """Restaura o logotipo original do sistema."""
        caminho_custom = db.obter_config("custom_logo_path", "")
        if not caminho_custom:
            messagebox.showinfo("Aviso", "O sistema já está utilizando o logotipo padrão.")
            return

        if not messagebox.askyesno("Restaurar Padrão", "Deseja restaurar o logotipo padrão do sistema?"):
            return

        db.salvar_config("custom_logo_path", "")
        if os.path.exists(caminho_custom):
            try:
                os.remove(caminho_custom)
            except Exception:
                pass

        self._atualizar_preview_logotipo()

        app = self.winfo_toplevel()
        if hasattr(app, "atualizar_logotipo_sidebar"):
            app.atualizar_logotipo_sidebar()

        messagebox.showinfo("Logotipo Restaurado", "O logotipo padrão foi restaurado com sucesso.")

    def _construir_card_tela_descanso(self):
        """Constrói o card de configuração da tela de descanso inteligente (screensaver)."""
        card = ctk.CTkFrame(self.row_customizacao, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        card.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=4)

        # Cabeçalho
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(head, text="🌙 Tela de Descanso Inteligente (Inatividade)", font=ctk.CTkFont(size=13, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(head, text="Ativa uma tela protetora quando o sistema não registrar vendas ou toques.", font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY).pack(anchor="w")

        # Corpo
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        # 1. Seletor de Tempo de Inatividade
        row_tempo = ctk.CTkFrame(body, fg_color="transparent")
        row_tempo.pack(fill="x", pady=(2, 6))

        ctk.CTkLabel(row_tempo, text="⏱️ Ativar após inatividade:", font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")

        mapa_opcoes_tempo = {
            "0.5": "30 segundos (Padrão)",
            "1": "1 minuto",
            "2": "2 minutos",
            "3": "3 minutos",
            "5": "5 minutos",
            "10": "10 minutos",
            "15": "15 minutos",
            "0": "Desativado",
        }
        self._inverso_tempo = {v: k for k, v in mapa_opcoes_tempo.items()}

        tempo_salvo = db.obter_config("screensaver_timeout_min", "0.5")
        valor_menu = mapa_opcoes_tempo.get(tempo_salvo, "30 segundos (Padrão)")

        self.menu_tempo = ctk.CTkOptionMenu(
            row_tempo,
            values=list(mapa_opcoes_tempo.values()),
            width=160,
            height=28,
            corner_radius=6,
            fg_color=theme.INNER_CARD_BG,
            button_color=theme.ACCENT_BLUE,
            command=self._ao_alterar_tempo_descanso,
        )
        self.menu_tempo.set(valor_menu)
        self.menu_tempo.pack(side="right")

        # 2. Seletor de Modo / Tema Visual da Tela
        row_modo = ctk.CTkFrame(body, fg_color="transparent")
        row_modo.pack(fill="x", pady=(2, 6))

        ctk.CTkLabel(row_modo, text="🎨 Estilo visual da tela:", font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")

        mapa_modos = {
            "DEFAULT": "Padrão AstridSoft (Relógio Digital)",
            "CUSTOM": "Personalizado (Banner da Loja)",
        }
        self._inverso_modos = {v: k for k, v in mapa_modos.items()}
        modo_salvo = db.obter_config("screensaver_mode", "DEFAULT")
        modo_menu = mapa_modos.get(modo_salvo, "Padrão AstridSoft (Relógio Digital)")

        self.menu_modo = ctk.CTkOptionMenu(
            row_modo,
            values=list(mapa_modos.values()),
            width=240,
            height=28,
            corner_radius=6,
            fg_color=theme.INNER_CARD_BG,
            button_color=theme.ACCENT_BLUE,
            command=self._ao_alterar_modo_descanso,
        )
        self.menu_modo.set(modo_menu)
        self.menu_modo.pack(side="right")

        # 3. Container Condicional para Seleção do Banner Personalizado
        self.box_custom_banner = ctk.CTkFrame(body, fg_color=theme.INNER_CARD_BG, corner_radius=8, border_width=1, border_color=theme.BORDER_COLOR)

        row_banner_btn = ctk.CTkFrame(self.box_custom_banner, fg_color="transparent")
        row_banner_btn.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(row_banner_btn, text="🖼️ Imagem / Banner:", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")

        btn_sel_banner = ctk.CTkButton(
            row_banner_btn,
            text="📁 Escolher Banner...",
            height=26,
            corner_radius=5,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            command=self._acao_selecionar_banner_custom,
        )
        btn_sel_banner.pack(side="right")

        self.lbl_status_banner = ctk.CTkLabel(self.box_custom_banner, text="", font=ctk.CTkFont(size=9), text_color=theme.TEXT_SECONDARY)
        self.lbl_status_banner.pack(padx=10, pady=(0, 6), anchor="w")

        # 4. Linha de Ações (Testar Agora)
        row_acoes = ctk.CTkFrame(body, fg_color="transparent")
        row_acoes.pack(fill="x", pady=(8, 0))

        btn_testar = ctk.CTkButton(
            row_acoes,
            text="👁️ Testar Tela de Descanso Agora",
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            text_color="#FFFFFF",
            command=self._acao_testar_descanso,
        )
        btn_testar.pack(fill="x")

        # Sincroniza visibilidade do container do banner
        self._sincronizar_visibilidade_banner()

    def _ao_alterar_tempo_descanso(self, opcao_texto: str):
        cod = self._inverso_tempo.get(opcao_texto, "0.5")
        db.salvar_config("screensaver_timeout_min", cod)

    def _ao_alterar_modo_descanso(self, opcao_texto: str):
        modo = self._inverso_modos.get(opcao_texto, "DEFAULT")
        db.salvar_config("screensaver_mode", modo)
        self._sincronizar_visibilidade_banner()

    def _sincronizar_visibilidade_banner(self):
        modo = db.obter_config("screensaver_mode", "DEFAULT")
        caminho_banner = db.obter_config("screensaver_custom_path", "")
        if modo == "CUSTOM":
            self.box_custom_banner.pack(fill="x", pady=(4, 6))
            if caminho_banner and os.path.exists(caminho_banner):
                self.lbl_status_banner.configure(text=f"Banner ativo: {os.path.basename(caminho_banner)}")
            else:
                self.lbl_status_banner.configure(text="Nenhum banner selecionado (clique em Escolher Banner)")
        else:
            self.box_custom_banner.pack_forget()

    def _acao_selecionar_banner_custom(self):
        caminho = filedialog.askopenfilename(
            title="Selecione o Banner ou Imagem Promocional para a Tela de Descanso",
            filetypes=[("Imagens PNG / JPG", "*.png;*.jpg;*.jpeg"), ("Todos os arquivos", "*.*")]
        )
        if not caminho:
            return

        try:
            pil_img = Image.open(caminho)
            destino = os.path.join(self._obter_caminho_base_app(), "custom_screensaver.png")
            pil_img.save(destino)
            db.salvar_config("screensaver_custom_path", destino)
            self._sincronizar_visibilidade_banner()
            messagebox.showinfo("Banner Salvo", "A imagem personalizada de descanso foi configurada com sucesso!")
        except Exception as e:
            messagebox.showerror("Erro ao Processar Imagem", f"Não foi possível salvar o banner:\n{str(e)}")

    def _acao_testar_descanso(self):
        app = self.winfo_toplevel()
        if hasattr(app, "ativar_screensaver_manual"):
            app.ativar_screensaver_manual()
        else:
            messagebox.showwarning("Aviso", "Protetor de tela não está disponível no momento.")

    def _construir_cards_kpi(self):
        kpis_def = [
            ("fat", "FATURAMENTO LÍQUIDO", "R$ 0,00", "Volume de vendas ativas", "#3B82F6"),
            ("lucro", "LUCRO LÍQUIDO REAL", "R$ 0,00", "Margem líquida", "#10B981"),
            ("cancel", "ESTORNOS / CANCELADAS", "R$ 0,00", "0 canceladas", "#EF4444"),
            ("ticket", "TICKET MÉDIO", "R$ 0,00", "Média por compra", "#8B5CF6"),
            ("vendas", "VENDAS CONCLUÍDAS", "0", "Clientes atendidos", "#06B6D4"),
            ("cmv", "CUSTO TOTAL (CMV)", "R$ 0,00", "Custo das mercadorias", "#F59E0B"),
        ]

        for idx, (cod, tit, val_padrao, sub_padrao, cor) in enumerate(kpis_def):
            c = ctk.CTkFrame(self.grid_kpis, corner_radius=10, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
            c.grid(row=0, column=idx, sticky="ew", padx=3, pady=4)

            # Barra superior colorida
            bar_t = ctk.CTkFrame(c, height=3, fg_color=cor, corner_radius=2)
            bar_t.pack(fill="x", padx=10, pady=(6, 4))

            ctk.CTkLabel(c, text=tit, font=ctk.CTkFont(size=9, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=10, pady=(2, 0))

            lbl_v = ctk.CTkLabel(c, text=val_padrao, font=ctk.CTkFont(size=15, weight="bold"), text_color=theme.TEXT_PRIMARY)
            lbl_v.pack(anchor="w", padx=10, pady=(2, 2))

            lbl_sub = ctk.CTkLabel(c, text=sub_padrao, font=ctk.CTkFont(size=10), text_color=theme.TEXT_MUTED)
            lbl_sub.pack(anchor="w", padx=10, pady=(0, 8))

            if cod == "fat":
                self.lbl_kpi_fat = lbl_v
                self.lbl_kpi_fat_sub = lbl_sub
            elif cod == "lucro":
                self.lbl_kpi_lucro = lbl_v
                self.lbl_kpi_margem = lbl_sub
            elif cod == "cancel":
                self.lbl_kpi_cancel = lbl_v
                self.lbl_kpi_cancel_sub = lbl_sub
            elif cod == "ticket":
                self.lbl_kpi_ticket = lbl_v
            elif cod == "vendas":
                self.lbl_kpi_vendas = lbl_v
            elif cod == "cmv":
                self.lbl_kpi_cmv = lbl_v

    def _mudar_periodo(self, novo_periodo: str):
        self.periodo_atual = novo_periodo
        for pid, btn in self.botoes_periodo.items():
            if pid == novo_periodo:
                btn.configure(fg_color=theme.ACCENT_BLUE, text_color="#FFFFFF")
            else:
                btn.configure(fg_color=theme.INNER_CARD_BG, text_color=theme.TEXT_SECONDARY)
        self.recarregar_dados()

    def recarregar_dados(self):
        """Consulta as estatísticas do período no banco e renderiza os gráficos."""
        try:
            metricas = db.obter_metricas_dashboard(self.periodo_atual)
            self._atualizar_interface(metricas)
        except Exception as e:
            print(f"Erro ao carregar dados do dashboard: {e}")

    def _atualizar_interface(self, m: Dict[str, Any]):
        # 1. Atualiza KPIs
        fat = m["total_faturamento"]
        fat_bruto = m.get("total_faturamento_bruto", fat)
        cancelado = m.get("total_cancelado", 0.0)
        qtd_canceladas = m.get("total_canceladas", 0)
        lucro = m["total_lucro"]
        margem = m["margem_lucro"]
        ticket = m["ticket_medio"]
        vendas = m["total_vendas"]
        itens = m["total_itens"]
        cmv = m["total_custo"]

        self.lbl_subtitulo.configure(
            text=f"Análise de Desempenho: {m['titulo_periodo']} | {vendas} vendas concluídas, {qtd_canceladas} estorno(s) e {itens} produtos comercializados."
        )

        if self.lbl_kpi_fat:
            self.lbl_kpi_fat.configure(text=reports.formatar_moeda(fat))
        if self.lbl_kpi_fat_sub:
            self.lbl_kpi_fat_sub.configure(text=f"Bruto: {reports.formatar_moeda(fat_bruto)}")
        if self.lbl_kpi_lucro:
            self.lbl_kpi_lucro.configure(text=reports.formatar_moeda(lucro))
        if self.lbl_kpi_margem:
            self.lbl_kpi_margem.configure(text=f"Margem Líquida: {margem}%")
        if self.lbl_kpi_cancel:
            self.lbl_kpi_cancel.configure(text=reports.formatar_moeda(cancelado))
        if self.lbl_kpi_cancel_sub:
            self.lbl_kpi_cancel_sub.configure(text=f"{qtd_canceladas} estorno(s) abatido(s)")
        if self.lbl_kpi_ticket:
            self.lbl_kpi_ticket.configure(text=reports.formatar_moeda(ticket))
        if self.lbl_kpi_vendas:
            self.lbl_kpi_vendas.configure(text=f"{vendas} vendas")
        if self.lbl_kpi_cmv:
            self.lbl_kpi_cmv.configure(text=reports.formatar_moeda(cmv))

        self.lbl_tot_graf_diario.configure(text=reports.formatar_moeda(fat))

        # 2. Desenha Gráficos em Canvas
        self._desenhar_grafico_diario(m.get("vendas_diarias", []))
        self._desenhar_grafico_pagamentos(m.get("formas_pagamento", []), fat)

        # 3. Atualiza Ranking Top Produtos
        self._renderizar_top_produtos(m.get("top_produtos", []))

        # 4. Atualiza Horários de Pico e Insights
        self._renderizar_horarios_e_insights(m)

        # 5. Atualiza Log de Transações & Estornos do Período
        self._renderizar_logs_transacoes(m.get("logs_transacoes", []))

    def _desenhar_grafico_diario(self, dados_diarios: List[Dict[str, Any]]):
        self.canvas_diario.delete("all")
        w = self.canvas_diario.winfo_width()
        h = self.canvas_diario.winfo_height()
        if w < 100:
            w = 520
        if h < 100:
            h = 210

        # Background grid sutil
        self.canvas_diario.create_rectangle(0, 0, w, h, fill="#0F172A", outline="")

        if not dados_diarios:
            self.canvas_diario.create_text(
                w // 2, h // 2,
                text="Nenhuma venda registrada no período selecionado.",
                fill="#64748B", font=("Segoe UI", 11)
            )
            return

        padding_left = 55
        padding_right = 25
        padding_top = 28
        padding_bottom = 35

        area_w = w - padding_left - padding_right
        area_h = h - padding_top - padding_bottom

        max_val = max([d["faturamento"] for d in dados_diarios] + [1.0])
        # Ajusta teto para arredondar
        teto = max_val * 1.15

        # Linhas de grade horizontais
        for i in range(4):
            y_grade = padding_top + (area_h / 3) * i
            val_grade = teto * (1 - i / 3)
            self.canvas_diario.create_line(padding_left, y_grade, w - padding_right, y_grade, fill="#1E293B", dash=(3, 3))
            self.canvas_diario.create_text(
                padding_left - 8, y_grade,
                text=f"R$ {val_grade:,.0f}".replace(",", "."),
                fill="#64748B", font=("Segoe UI", 8), anchor="e"
            )

        n_barras = len(dados_diarios)
        slot_w = area_w / max(n_barras, 1)
        bar_w = min(slot_w * 0.65, 48)

        pontos_linha = []

        for idx, item in enumerate(dados_diarios):
            val = item["faturamento"]
            dia_txt = item["dia_fmt"]

            cx = padding_left + slot_w * idx + (slot_w / 2)
            alt_barra = (val / teto) * area_h if teto > 0 else 0
            y_topo = padding_top + (area_h - alt_barra)
            y_base = padding_top + area_h

            x1 = cx - bar_w / 2
            x2 = cx + bar_w / 2

            # Barra destacada se for a maior do período
            cor_barra = "#10B981" if val == max_val and val > 0 else "#3B82F6"
            self.canvas_diario.create_rectangle(x1, y_topo, x2, y_base, fill=cor_barra, outline="")

            # Valor acima da barra
            if val > 0:
                txt_val = f"R$ {val:,.0f}".replace(",", ".")
                self.canvas_diario.create_text(cx, y_topo - 10, text=txt_val, fill="#F8FAFC", font=("Segoe UI", 9, "bold"))

            # Rótulo da data abaixo do eixo
            self.canvas_diario.create_text(cx, y_base + 14, text=dia_txt, fill="#94A3B8", font=("Segoe UI", 9))

            pontos_linha.extend([cx, y_topo])

        # Linha de tendência suave conectando os topos
        if len(pontos_linha) >= 4:
            self.canvas_diario.create_line(*pontos_linha, fill="#38BDF8", width=2, smooth=True)

    def _desenhar_grafico_pagamentos(self, formas: List[Dict[str, Any]], total_fat: float):
        self.canvas_pgto.delete("all")
        w = self.canvas_pgto.winfo_width()
        h = self.canvas_pgto.winfo_height()
        if w < 100:
            w = 340
        if h < 100:
            h = 210

        self.canvas_pgto.create_rectangle(0, 0, w, h, fill="#0F172A", outline="")

        if not formas or total_fat <= 0:
            self.canvas_pgto.create_text(
                w // 2, h // 2,
                text="Sem movimentação financeira no período.",
                fill="#64748B", font=("Segoe UI", 11)
            )
            return

        # Cores para cada forma
        mapa_cores = {
            "DINHEIRO": "#10B981",
            "PIX": "#06B6D4",
            "CARTAO_DEBITO": "#3B82F6",
            "CARTAO_CREDITO": "#8B5CF6",
            "VALE_ALIMENTACAO": "#F59E0B",
            "OUTROS": "#EC4899",
        }

        # Donut Chart no lado esquerdo do card
        cx = 95
        cy = h // 2
        raio_ext = 65
        raio_int = 40

        angulo_ini = 0.0
        for item in formas:
            f_cod = item["forma"]
            pct = item["percentual"]
            extensao = (pct / 100.0) * 360.0
            cor = mapa_cores.get(f_cod, "#64748B")

            if extensao > 0:
                self.canvas_pgto.create_arc(
                    cx - raio_ext, cy - raio_ext,
                    cx + raio_ext, cy + raio_ext,
                    start=angulo_ini, extent=extensao,
                    fill=cor, outline="#0F172A", width=2
                )
                angulo_ini += extensao

        # Círculo central para transformar em Donut
        self.canvas_pgto.create_oval(
            cx - raio_int, cy - raio_int,
            cx + raio_int, cy + raio_int,
            fill="#0F172A", outline=""
        )
        self.canvas_pgto.create_text(
            cx, cy - 6,
            text="TOTAL", fill="#64748B", font=("Segoe UI", 8, "bold")
        )
        self.canvas_pgto.create_text(
            cx, cy + 8,
            text=f"R$ {total_fat:,.0f}".replace(",", "."),
            fill="#F8FAFC", font=("Segoe UI", 9, "bold")
        )

        # Legenda no lado direito
        legenda_x = 185
        legenda_y = 26
        espaco_y = 30

        nomes_amigaveis = {
            "DINHEIRO": "💵 Dinheiro",
            "PIX": "📱 Pix",
            "CARTAO_DEBITO": "💳 Débito",
            "CARTAO_CREDITO": "💳 Crédito",
            "VALE_ALIMENTACAO": "🎫 Vale",
            "OUTROS": "🪙 Outros",
        }

        for idx, item in enumerate(formas[:5]):
            f_cod = item["forma"]
            val = item["total"]
            pct = item["percentual"]
            cor = mapa_cores.get(f_cod, "#64748B")
            nome = nomes_amigaveis.get(f_cod, f_cod.capitalize())

            y = legenda_y + idx * espaco_y

            # Marcador de cor
            self.canvas_pgto.create_oval(legenda_x, y + 2, legenda_x + 10, y + 12, fill=cor, outline="")
            self.canvas_pgto.create_text(
                legenda_x + 16, y + 2,
                text=nome, fill="#E2E8F0", font=("Segoe UI", 9, "bold"), anchor="w"
            )
            self.canvas_pgto.create_text(
                legenda_x + 16, y + 15,
                text=f"{reports.formatar_moeda(val)} ({pct}%)",
                fill="#94A3B8", font=("Segoe UI", 8), anchor="w"
            )

    def _renderizar_top_produtos(self, produtos: List[Dict[str, Any]]):
        for w in self.box_produtos_lista.winfo_children():
            w.destroy()

        if not produtos:
            ctk.CTkLabel(
                self.box_produtos_lista,
                text="Nenhum produto vendido no período.",
                font=ctk.CTkFont(size=11),
                text_color=theme.TEXT_MUTED,
            ).pack(pady=30)
            return

        max_fat = max([p["faturamento"] for p in produtos] + [1.0])

        for idx, p in enumerate(produtos[:7]):
            row_p = ctk.CTkFrame(self.box_produtos_lista, fg_color=theme.INNER_CARD_BG, corner_radius=8)
            row_p.pack(fill="x", pady=2, padx=2)

            # Medalha / Posição
            badges = {0: "🥇", 1: "🥈", 2: "🥉"}
            med = badges.get(idx, f"#{idx + 1}")

            ctk.CTkLabel(
                row_p, text=med, width=28,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#F59E0B" if idx < 3 else theme.TEXT_SECONDARY
            ).pack(side="left", padx=(8, 4))

            # Nome e Quantidade
            info_box = ctk.CTkFrame(row_p, fg_color="transparent")
            info_box.pack(side="left", fill="both", expand=True, padx=4, pady=4)

            ctk.CTkLabel(
                info_box, text=p["nome"],
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.TEXT_PRIMARY,
                anchor="w",
            ).pack(fill="x")

            # Barra visual de proporção do faturamento
            barra_bg = ctk.CTkFrame(info_box, height=4, fg_color="#1E293B", corner_radius=2)
            barra_bg.pack(fill="x", pady=(2, 0))
            largura_pct = min(1.0, p["faturamento"] / max_fat)
            barra_prog = ctk.CTkFrame(barra_bg, width=int(180 * largura_pct), height=4, fg_color=theme.ACCENT_BLUE, corner_radius=2)
            barra_prog.pack(side="left")

            # Quantidade e Faturamento
            ctk.CTkLabel(
                row_p, text=f"{p['quantidade']} un",
                font=ctk.CTkFont(size=11),
                text_color=theme.TEXT_SECONDARY,
                width=50,
            ).pack(side="left", padx=4)

            tot_box = ctk.CTkFrame(row_p, fg_color="transparent")
            tot_box.pack(side="right", padx=(4, 12), pady=4)

            ctk.CTkLabel(
                tot_box, text=reports.formatar_moeda(p["faturamento"]),
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.PRICE_COLOR,
                anchor="e",
            ).pack(anchor="e")

            ctk.CTkLabel(
                tot_box, text=f"Lucro: {reports.formatar_moeda(p['lucro'])} ({p['margem']}%)",
                font=ctk.CTkFont(size=9),
                text_color=theme.STOCK_COLOR[1],
                anchor="e",
            ).pack(anchor="e")

    def _renderizar_horarios_e_insights(self, m: Dict[str, Any]):
        for w in self.box_insights_conteudo.winfo_children():
            w.destroy()

        faixas = m.get("faixas_horario", {"manha": 0.0, "tarde": 0.0, "noite": 0.0})
        tot_faixas = faixas["manha"] + faixas["tarde"] + faixas["noite"]

        horarios = [
            ("☀️ Manhã (06h às 12h)", faixas["manha"], "#F59E0B"),
            ("⛅ Tarde (12h às 18h)", faixas["tarde"], "#3B82F6"),
            ("🌙 Noite (18h às 24h)", faixas["noite"], "#8B5CF6"),
        ]

        for rot, val, cor in horarios:
            card_h = ctk.CTkFrame(self.box_insights_conteudo, fg_color=theme.INNER_CARD_BG, corner_radius=8)
            card_h.pack(fill="x", pady=3)

            pct = round((val / tot_faixas * 100), 1) if tot_faixas > 0 else 0.0

            inner = ctk.CTkFrame(card_h, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=6)

            ctk.CTkLabel(inner, text=rot, font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")
            ctk.CTkLabel(inner, text=f"{reports.formatar_moeda(val)} ({pct}%)", font=ctk.CTkFont(size=11, weight="bold"), text_color=cor).pack(side="right")

            # Mini barra de progresso
            b_bg = ctk.CTkFrame(card_h, height=3, fg_color="#1E293B")
            b_bg.pack(fill="x", padx=12, pady=(0, 6))
            if pct > 0:
                ctk.CTkFrame(b_bg, width=int(260 * (pct / 100.0)), height=3, fg_color=cor).pack(side="left")

        # Caixa de Insight Automatizado
        card_dica = ctk.CTkFrame(self.box_insights_conteudo, fg_color="#1E293B", corner_radius=8, border_width=1, border_color="#334155")
        card_dica.pack(fill="x", pady=(10, 0))

        # Gera insight inteligente
        formas = m.get("formas_pagamento", [])
        top_prods = m.get("top_produtos", [])

        insight_txt = "💡 Resumo Estratégico:"
        if top_prods:
            p_top = top_prods[0]
            insight_txt += f"\n• O carro-chefe é '{p_top['nome']}' ({p_top['quantidade']} un vendidas)."
        if formas:
            f_top = formas[0]
            insight_txt += f"\n• O meio de recebimento preferido é {f_top['forma']} ({f_top['percentual']}% do volume)."
        if m["margem_lucro"] >= 40:
            insight_txt += f"\n• Excelente saúde financeira: margem real apurada de {m['margem_lucro']}%."

        ctk.CTkLabel(
            card_dica,
            text=insight_txt,
            font=ctk.CTkFont(size=10),
            text_color="#94A3B8",
            justify="left",
        ).pack(padx=12, pady=10, anchor="w")

    def _renderizar_logs_transacoes(self, logs: List[Dict[str, Any]]):
        for w in self.box_logs_conteudo.winfo_children():
            w.destroy()

        if not logs:
            ctk.CTkLabel(
                self.box_logs_conteudo,
                text="Nenhuma transação registrada no período selecionado.",
                font=ctk.CTkFont(size=12, slant="italic"),
                text_color=theme.TEXT_MUTED,
            ).pack(pady=20)
            return

        # Cabeçalho da Tabela de Logs
        header_grid = ctk.CTkFrame(self.box_logs_conteudo, height=32, fg_color=theme.INNER_CARD_BG, corner_radius=6)
        header_grid.pack(fill="x", pady=(0, 6))

        col_configs = [
            ("ID", 50, "center"),
            ("Data/Hora", 110, "center"),
            ("Produto / Operação", 240, "w"),
            ("Qtd", 60, "center"),
            ("Unitário", 95, "e"),
            ("Total Bruto", 105, "e"),
            ("Forma Pagto", 110, "center"),
            ("Status", 130, "center"),
            ("Impacto no Caixa", 145, "e"),
        ]

        for nome_col, largura, alinhamento in col_configs:
            lbl = ctk.CTkLabel(
                header_grid,
                text=nome_col,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=theme.TEXT_SECONDARY,
                width=largura,
                anchor=alinhamento,
            )
            if alinhamento == "w":
                lbl.pack(side="left", fill="x", expand=True, padx=8)
            else:
                lbl.pack(side="left", padx=4)

        # Renderização dos Registros
        mapa_pgto_icones = {
            "DINHEIRO": "💵 Dinheiro",
            "PIX": "📱 Pix",
            "CARTAO_DEBITO": "💳 Débito",
            "CARTAO_CREDITO": "💳 Crédito",
        }

        for tx in logs:
            is_canc = (tx.get("status") == "CANCELADA")
            cor_bg = "#261313" if is_canc else theme.INNER_CARD_BG
            cor_borda = "#7F1D1D" if is_canc else theme.BORDER_COLOR
            cor_texto = theme.TEXT_MUTED if is_canc else theme.TEXT_PRIMARY

            linha = ctk.CTkFrame(
                self.box_logs_conteudo,
                height=36,
                fg_color=cor_bg,
                corner_radius=6,
                border_width=1,
                border_color=cor_borda,
            )
            linha.pack(fill="x", pady=3)

            # ID
            ctk.CTkLabel(
                linha, text=f"#{tx['id']}",
                font=ctk.CTkFont(size=10),
                text_color=theme.TEXT_SECONDARY,
                width=50,
            ).pack(side="left", padx=4)

            # Data/Hora
            d_str = tx["data_hora"]
            try:
                dt_obj = datetime.strptime(d_str[:19], "%Y-%m-%d %H:%M:%S")
                d_fmt = dt_obj.strftime("%d/%m %H:%M")
            except Exception:
                d_fmt = d_str
            ctk.CTkLabel(
                linha, text=d_fmt,
                font=ctk.CTkFont(size=10),
                text_color=cor_texto,
                width=110,
            ).pack(side="left", padx=4)

            # Produto / Operação
            lbl_prod = ctk.CTkLabel(
                linha, text=tx["produto_nome"],
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=cor_texto,
                anchor="w",
            )
            lbl_prod.pack(side="left", fill="x", expand=True, padx=8)

            # Quantidade
            ctk.CTkLabel(
                linha, text=f"{tx['quantidade']} un",
                font=ctk.CTkFont(size=10),
                text_color=cor_texto,
                width=60,
            ).pack(side="left", padx=4)

            # Unitário
            ctk.CTkLabel(
                linha, text=reports.formatar_moeda(tx["preco_unitario"]),
                font=ctk.CTkFont(size=10),
                text_color=theme.TEXT_MUTED if is_canc else theme.TEXT_SECONDARY,
                width=95,
                anchor="e",
            ).pack(side="left", padx=4)

            # Total Bruto
            ctk.CTkLabel(
                linha, text=reports.formatar_moeda(tx["valor_total"]),
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=theme.TEXT_MUTED if is_canc else theme.PRICE_COLOR,
                width=105,
                anchor="e",
            ).pack(side="left", padx=4)

            # Forma Pagamento
            pg_rot = mapa_pgto_icones.get(tx.get("forma_pagamento", "DINHEIRO").upper(), tx.get("forma_pagamento", "Dinheiro"))
            ctk.CTkLabel(
                linha, text=pg_rot,
                font=ctk.CTkFont(size=10),
                text_color=cor_texto,
                width=110,
            ).pack(side="left", padx=4)

            # Status Badge
            status_box = ctk.CTkFrame(linha, width=130, height=24, fg_color="transparent")
            status_box.pack(side="left", padx=4)
            status_box.pack_propagate(False)

            if is_canc:
                ctk.CTkLabel(
                    status_box,
                    text="🔴 CANCELADA",
                    font=ctk.CTkFont(size=9, weight="bold"),
                    text_color="#EF4444",
                ).pack(expand=True)
            else:
                ctk.CTkLabel(
                    status_box,
                    text="🟢 CONCLUÍDA",
                    font=ctk.CTkFont(size=9, weight="bold"),
                    text_color="#10B981",
                ).pack(expand=True)

            # Impacto no Caixa
            if is_canc:
                txt_impacto = f"- {reports.formatar_moeda(tx['valor_total'])} (Estornado)"
                cor_impacto = "#EF4444"
            else:
                txt_impacto = f"+ {reports.formatar_moeda(tx['valor_total'])}"
                cor_impacto = "#10B981"

            ctk.CTkLabel(
                linha, text=txt_impacto,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=cor_impacto,
                width=145,
                anchor="e",
            ).pack(side="left", padx=(4, 8))

    def _exportar_relatorio_excel(self):
        """Exporta os dados consolidados do dia para Excel protegido."""
        sucesso, msg, arq = reports.gerar_relatorio_diario_excel()
        from tkinter import messagebox
        if sucesso:
            messagebox.showinfo("Exportação Concluída", f"Relatório gerado com sucesso!\n{os.path.basename(arq)}")
        else:
            messagebox.showerror("Erro na Exportação", msg)
