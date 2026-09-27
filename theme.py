"""
Módulo de Tema e Paleta Visual Dinâmica
Arquivo: theme.py

Define tuplas de cores dinâmicas no padrão CustomTkinter: (modo_claro, modo_escuro).
Permite que todos os componentes gráficos da aplicação se adaptem instantaneamente
quando o usuário alternar entre Dark e Light mode.
"""

# Fundos Principais
BG_COLOR = ("#F1F5F9", "#0F172A")          # Slate 100 / Slate 900
SIDEBAR_BG = ("#E2E8F0", "#1E293B")        # Slate 200 / Slate 800
HEADER_BG = ("#E2E8F0", "#1E293B")         # Header HUD
CARD_BG = ("#FFFFFF", "#1E293B")           # White / Slate 800
INNER_CARD_BG = ("#F8FAFC", "#0F172A")     # Slate 50 / Slate 900
MODAL_BG = ("#FFFFFF", "#0F172A")          # Janelas modais

# Bordas e Linhas Divisórias
BORDER_COLOR = ("#CBD5E1", "#334155")      # Slate 300 / Slate 700
BORDER_LIGHT = ("#E2E8F0", "#1E293B")

# Cores de Texto
TEXT_PRIMARY = ("#0F172A", "#F8FAFC")      # Slate 900 / Slate 50
TEXT_SECONDARY = ("#475569", "#94A3B8")    # Slate 600 / Slate 400
TEXT_MUTED = ("#64748B", "#64748B")        # Slate 500

# Campos de Entrada (Entry, ComboBox, OptionMenu)
ENTRY_BG = ("#FFFFFF", "#0F172A")
ENTRY_BORDER = ("#CBD5E1", "#334155")
ENTRY_TEXT = ("#0F172A", "#F8FAFC")

# Botões de Ação Secundária / Neutros
BTN_SECONDARY_BG = ("#E2E8F0", "#334155")
BTN_SECONDARY_HOVER = ("#CBD5E1", "#475569")
BTN_SECONDARY_TEXT = ("#1E293B", "#F1F5F9")

# Botões de Ação Primária (Azul)
ACCENT_BLUE = ("#2563EB", "#3B82F6")
ACCENT_BLUE_HOVER = ("#1D4ED8", "#2563EB")
ACCENT_BLUE_TEXT = ("#FFFFFF", "#FFFFFF")

# Confirmações e Sucesso (Verde)
ACCENT_GREEN = ("#059669", "#10B981")
ACCENT_GREEN_HOVER = ("#047857", "#059669")

# Perigo / Exclusão / Erro (Vermelho)
ACCENT_RED = ("#DC2626", "#EF4444")
ACCENT_RED_HOVER = ("#B91C1C", "#DC2626")

# Destaques Financeiros
PRICE_COLOR = ("#0284C7", "#38BDF8")
STOCK_COLOR = ("#059669", "#10B981")
WARNING_COLOR = ("#D97706", "#F59E0B")
