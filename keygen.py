"""
Gerador de Chaves de Licenciamento (Versão de Demonstração / Showcase para Portfólio)
Arquivo: keygen.py

Autor: Igor Fernando
Ano: 2026

NOTA DE SEGURANÇA E ARQUITETURA (SHOWCASE):
-------------------------------------------------------------------------------
Esta versão pública é um mock demonstrativo (DemoKeyGenerator).
As chaves privadas assimétricas Ed25519 e a autoridade certificadora proprietária
foram completamente desacopladas e omitidas desta branch pública de portfólio.

Este gerador emite chaves no padrão demonstrativo: DEMO-2026-XXXX-XXXX.
-------------------------------------------------------------------------------
"""

import os
import sys
import secrets
import argparse
from datetime import datetime
from typing import Tuple


def gerar_token_licenca_demo(cliente: str = "Cliente Demonstração", plano: str = "LIFETIME") -> Tuple[str, dict]:
    """
    Gera uma chave no padrão genérico do showcase: DEMO-2026-XXXX-XXXX.
    """
    bloco1 = secrets.token_hex(2).upper()
    bloco2 = secrets.token_hex(2).upper()
    chave_demo = f"DEMO-2026-{bloco1}-{bloco2}"

    payload = {
        "client": cliente.strip() if cliente.strip() else "Empresa Modelo LTDA",
        "plan": plano,
        "issued_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "key": chave_demo,
        "demo_mode": True,
        "notice": "Modo de demonstração ativado para fins de portfólio",
    }

    return chave_demo, payload


# ============================================================================
# INTERFACE GRÁFICA DEMONSTRATIVA (CUSTOMTKINTER)
# ============================================================================

def iniciar_interface_grafica():
    import customtkinter as ctk

    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("🔑 Gerador de Chaves de Demonstração (Showcase Portfólio)")
    root.geometry("640x560")
    root.resizable(False, False)
    root.configure(fg_color="#0F172A")

    # Centraliza janela
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 640) // 2
    y = (root.winfo_screenheight() - 560) // 2
    root.geometry(f"+{x}+{y}")

    # Container Principal
    card = ctk.CTkFrame(root, corner_radius=14, fg_color="#1E293B", border_width=1, border_color="#334155")
    card.pack(fill="both", expand=True, padx=24, pady=24)

    # Cabeçalho
    lbl_tit = ctk.CTkLabel(
        card,
        text="🔑 Gerador de Chaves Demo (Portfólio)",
        font=ctk.CTkFont(size=18, weight="bold"),
        text_color="#F8FAFC",
    )
    lbl_tit.pack(pady=(20, 4))

    lbl_sub = ctk.CTkLabel(
        card,
        text="Emissão demonstrativa de chaves no padrão DEMO-2026-XXXX-XXXX.",
        font=ctk.CTkFont(size=12),
        text_color="#94A3B8",
    )
    lbl_sub.pack(pady=(0, 16))

    # Campo: Nome do Cliente
    ctk.CTkLabel(card, text="Nome do Cliente / Estabelecimento (Fictício):", font=ctk.CTkFont(size=12, weight="bold"), text_color="#E2E8F0").pack(anchor="w", padx=28, pady=(4, 2))
    entry_cliente = ctk.CTkEntry(
        card,
        placeholder_text="Ex: Empresa Modelo LTDA",
        height=38,
        corner_radius=8,
        fg_color="#0F172A",
        border_color="#334155",
        font=ctk.CTkFont(size=13),
    )
    entry_cliente.insert(0, "Empresa Modelo LTDA")
    entry_cliente.pack(fill="x", padx=28, pady=(0, 14))

    # Seleção do Plano
    ctk.CTkLabel(card, text="Selecione o Plano da Licença:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#E2E8F0").pack(anchor="w", padx=28, pady=(4, 2))

    planos_map = {
        "⭐ Período de Testes (Trial 15 Dias)": "15_DAYS",
        "Plano Mensal (30 Dias)": "30_DAYS",
        "Plano Bimestral (60 Dias)": "60_DAYS",
        "Plano Trimestral (90 Dias)": "90_DAYS",
        "💎 Licença Vitalícia (LIFETIME)": "LIFETIME",
    }

    combo_plano = ctk.CTkComboBox(
        card,
        values=list(planos_map.keys()),
        height=38,
        corner_radius=8,
        fg_color="#0F172A",
        border_color="#334155",
        button_color="#2563EB",
        button_hover_color="#1D4ED8",
        dropdown_fg_color="#1E293B",
        dropdown_hover_color="#334155",
        font=ctk.CTkFont(size=13),
    )
    combo_plano.set("💎 Licença Vitalícia (LIFETIME)")
    combo_plano.pack(fill="x", padx=28, pady=(0, 16))

    # Botão Gerar Chave
    def _acao_gerar():
        cliente = entry_cliente.get().strip()
        plano_escolhido = combo_plano.get()
        plano_code = planos_map.get(plano_escolhido, "LIFETIME")

        try:
            chave, payload = gerar_token_licenca_demo(cliente, plano_code)
            txt_token.delete("1.0", "end")
            txt_token.insert("1.0", chave)

            msg_status = "✔ Chave Demo gerada com sucesso! Padrão aceito pelo validador."
            lbl_feedback.configure(text=msg_status, text_color="#10B981")
            btn_copiar.configure(state="normal")
        except Exception as e:
            lbl_feedback.configure(text=f"Erro: {str(e)}", text_color="#EF4444")

    btn_gerar = ctk.CTkButton(
        card,
        text="🔑 GERAR CHAVE DEMO (PORTFÓLIO)",
        height=44,
        corner_radius=8,
        font=ctk.CTkFont(size=13, weight="bold"),
        fg_color="#10B981",
        hover_color="#059669",
        command=_acao_gerar,
    )
    btn_gerar.pack(fill="x", padx=28, pady=(4, 12))

    # Caixa de Texto para o Token Gerado
    ctk.CTkLabel(card, text="Chave de Demonstração Gerada:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94A3B8").pack(anchor="w", padx=28, pady=(4, 2))

    txt_token = ctk.CTkTextbox(
        card,
        height=60,
        corner_radius=8,
        fg_color="#0F172A",
        border_color="#334155",
        border_width=1,
        font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
        wrap="char",
    )
    txt_token.pack(fill="x", padx=28, pady=(0, 10))

    # Linha Inferior com Botão Copiar e Feedback
    bot_frame = ctk.CTkFrame(card, fg_color="transparent")
    bot_frame.pack(fill="x", padx=28, pady=(0, 14))

    lbl_feedback = ctk.CTkLabel(
        bot_frame,
        text="",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color="#10B981",
        anchor="w",
    )
    lbl_feedback.pack(side="left", fill="x", expand=True)

    def _copiar_clipboard():
        token = txt_token.get("1.0", "end").strip()
        if token:
            root.clipboard_clear()
            root.clipboard_append(token)
            lbl_feedback.configure(text="📋 Chave copiada para a área de transferência!", text_color="#38BDF8")

    btn_copiar = ctk.CTkButton(
        bot_frame,
        text="📋 Copiar Chave",
        width=130,
        height=36,
        corner_radius=8,
        font=ctk.CTkFont(size=12, weight="bold"),
        fg_color="#2563EB",
        hover_color="#1D4ED8",
        command=_copiar_clipboard,
        state="disabled",
    )
    btn_copiar.pack(side="right")

    root.mainloop()


# ============================================================================
# MODO CLI (LINHA DE COMANDO)
# ============================================================================

def main_cli():
    parser = argparse.ArgumentParser(description="Gerador de Chaves de Demonstração (Portfólio)")
    parser.add_argument("--client", type=str, default="Empresa Modelo LTDA", help="Nome do cliente demonstrativo")
    parser.add_argument("--plan", type=str, default="LIFETIME", help="Plano simulado")

    args = parser.parse_args()
    chave, payload = gerar_token_licenca_demo(args.client, args.plan)

    print("\n" + "=" * 70)
    print("      CHAVE DE DEMONSTRAÇÃO GERADA (SHOWCASE PORTFÓLIO)")
    print("=" * 70)
    print(f"Cliente:      {payload['client']}")
    print(f"Plano:        {payload['plan']}")
    print(f"Aviso:        {payload['notice']}")
    print("-" * 70)
    print(f"CHAVE DEMO:   {chave}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main_cli()
    else:
        iniciar_interface_grafica()
