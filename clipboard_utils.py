"""
Módulo Utilitário de Área de Transferência (Clipboard) e Menus de Contexto
Arquivo: clipboard_utils.py

Fornece integração direta com a API nativa do Windows (Win32 / OLE) para cópia e colagem:
1. Persistência de dados: a chave copiada pelo Keygen NÃO se perde ao fechar a janela (OleFlushClipboard).
2. Compatibilidade universal: leitura direta de formatos Unicode (CF_UNICODETEXT) e ANSI (CF_TEXT).
3. Bypass de bugs do Tcl/Tk: evita a falha 'CLIPBOARD selection doesn't exist or form STRING not defined'.
4. Suporte a menu de contexto (botão direito) e atalhos (Ctrl+V, Ctrl+A, Ctrl+C) em CTkTextbox e CTkEntry.
"""

import sys
import os
from typing import Optional, Callable, Any
import tkinter as tk

# Inicialização de bibliotecas nativas do Windows via ctypes
_TEM_WIN32 = False
if sys.platform.startswith("win"):
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        try:
            ole32 = ctypes.windll.ole32
            ole32.OleInitialize(None)
        except Exception:
            ole32 = None

        CF_TEXT = 1
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002

        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        user32.IsClipboardFormatAvailable.restype = wintypes.BOOL

        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL

        _TEM_WIN32 = True
    except Exception:
        _TEM_WIN32 = False


def definir_texto_clipboard(texto: str, widget: Optional[Any] = None) -> bool:
    """
    Copia texto para a área de transferência do Windows de maneira persistente.
    Usa Win32 API e OleFlushClipboard para que o texto NÃO desapareça ao fechar o Keygen.
    """
    sucesso = False

    if _TEM_WIN32:
        try:
            if user32.OpenClipboard(None):
                try:
                    user32.EmptyClipboard()
                    data = str(texto).encode("utf-16-le") + b"\x00\x00"
                    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                    if h_mem:
                        p_mem = kernel32.GlobalLock(h_mem)
                        if p_mem:
                            ctypes.memmove(p_mem, data, len(data))
                            kernel32.GlobalUnlock(h_mem)
                            if user32.SetClipboardData(CF_UNICODETEXT, h_mem):
                                sucesso = True
                finally:
                    user32.CloseClipboard()

            if ole32:
                try:
                    ole32.OleFlushClipboard()
                except Exception:
                    pass
        except Exception:
            pass

    # Sincroniza também no Tkinter se um widget for fornecido
    if widget:
        try:
            widget.clipboard_clear()
            widget.clipboard_append(texto)
            widget.update_idletasks()
            sucesso = True
        except Exception:
            pass

    return sucesso


def obter_texto_clipboard(widget: Optional[Any] = None) -> str:
    """
    Lê o texto da área de transferência do Windows.
    Primeiro tenta a API nativa do Windows (suporta Unicode, WhatsApp, navegadores, Keygen).
    Se falhar, recorre ao método nativo do Tkinter (fallback).
    """
    if _TEM_WIN32:
        try:
            if user32.OpenClipboard(None):
                try:
                    if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                        h_data = user32.GetClipboardData(CF_UNICODETEXT)
                        if h_data:
                            p_data = kernel32.GlobalLock(h_data)
                            if p_data:
                                try:
                                    val = ctypes.c_wchar_p(p_data).value
                                    if val is not None and str(val).strip():
                                        return str(val)
                                finally:
                                    kernel32.GlobalUnlock(h_data)
                    elif user32.IsClipboardFormatAvailable(CF_TEXT):
                        h_data = user32.GetClipboardData(CF_TEXT)
                        if h_data:
                            p_data = kernel32.GlobalLock(h_data)
                            if p_data:
                                try:
                                    val = ctypes.c_char_p(p_data).value
                                    if val is not None and str(val).strip():
                                        return val.decode("latin1", errors="replace")
                                finally:
                                    kernel32.GlobalUnlock(h_data)
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass

    # Fallback via Tkinter
    if widget:
        for t in ["STRING", "UTF8_STRING"]:
            try:
                val_tk = widget.clipboard_get(type=t)
                if val_tk and str(val_tk).strip():
                    return str(val_tk)
            except Exception:
                pass

    return ""


def sanitizar_chave(chave_bruta: str) -> str:
    """
    Remove caracteres invisíveis, quebras de linha automáticas de e-mails/WhatsApp,
    espaços laterais e aspas que possam ter sido copiadas acidentalmente.
    """
    if not chave_bruta:
        return ""
    limpa = chave_bruta.strip().strip("\"'").strip()
    # Remove quebras de linha e espaços no meio do token
    limpa = "".join(limpa.split())
    return limpa


def habilitar_menu_e_atalhos(
    widget: Any,
    callback_ao_colar: Optional[Callable[[str], None]] = None,
    apenas_leitura: bool = False,
):
    """
    Habilita menu de contexto com botão direito e atalhos universais
    (Ctrl+V, Ctrl+A, Ctrl+C, Ctrl+X) em CTkTextbox, CTkEntry, tk.Text ou tk.Entry.
    """
    inner = getattr(widget, "_textbox", None) or getattr(widget, "_entry", None) or widget

    # Cria menu suspenso nativo com estilo limpo
    menu = tk.Menu(widget, tearoff=0)

    def _ao_copiar():
        try:
            texto_sel = ""
            if isinstance(inner, tk.Text):
                try:
                    texto_sel = inner.get("sel.first", "sel.last")
                except Exception:
                    texto_sel = inner.get("1.0", "end-1c")
            elif isinstance(inner, tk.Entry):
                try:
                    texto_sel = inner.selection_get()
                except Exception:
                    texto_sel = inner.get()
            if texto_sel:
                definir_texto_clipboard(texto_sel, widget)
        except Exception:
            pass

    def _ao_colar(event=None):
        if apenas_leitura:
            return "break"
        texto = obter_texto_clipboard(widget)
        if texto:
            try:
                if isinstance(inner, tk.Text):
                    try:
                        inner.delete("sel.first", "sel.last")
                    except Exception:
                        pass
                    inner.insert("insert", texto)
                elif isinstance(inner, tk.Entry):
                    try:
                        inner.delete("sel.first", "sel.last")
                    except Exception:
                        pass
                    inner.insert("insert", texto)
            except Exception:
                pass
            if callback_ao_colar:
                callback_ao_colar(texto)
        return "break"

    def _ao_recortar():
        if apenas_leitura:
            return
        _ao_copiar()
        try:
            if isinstance(inner, tk.Text):
                inner.delete("sel.first", "sel.last")
            elif isinstance(inner, tk.Entry):
                inner.delete("sel.first", "sel.last")
        except Exception:
            pass

    def _ao_selecionar_tudo(event=None):
        try:
            if isinstance(inner, tk.Text):
                inner.tag_add("sel", "1.0", "end")
                inner.mark_set("insert", "end")
            elif isinstance(inner, tk.Entry):
                inner.select_range(0, "end")
                inner.icursor("end")
        except Exception:
            pass
        return "break"

    def _ao_limpar():
        if apenas_leitura:
            return
        try:
            if isinstance(inner, tk.Text):
                inner.delete("1.0", "end")
            elif isinstance(inner, tk.Entry):
                inner.delete(0, "end")
        except Exception:
            pass

    if not apenas_leitura:
        menu.add_command(label="📋 Colar", command=_ao_colar)
    menu.add_command(label="📄 Copiar", command=_ao_copiar)
    if not apenas_leitura:
        menu.add_command(label="✂️ Recortar", command=_ao_recortar)
        menu.add_separator()
        menu.add_command(label="🔤 Selecionar Tudo", command=_ao_selecionar_tudo)
        menu.add_command(label="🧹 Limpar Campo", command=_ao_limpar)
    else:
        menu.add_separator()
        menu.add_command(label="🔤 Selecionar Tudo", command=_ao_selecionar_tudo)

    def _exibir_menu(event):
        inner.focus_set()
        menu.tk_popup(event.x_root, event.y_root)

    # Associa clique com botão direito
    inner.bind("<Button-3>", _exibir_menu)
    if widget != inner:
        widget.bind("<Button-3>", _exibir_menu)

    # Associa atalhos de teclado universais
    inner.bind("<Control-v>", _ao_colar)
    inner.bind("<Control-V>", _ao_colar)
    inner.bind("<Control-a>", _ao_selecionar_tudo)
    inner.bind("<Control-A>", _ao_selecionar_tudo)
    inner.bind("<Control-c>", lambda e: _ao_copiar())
    inner.bind("<Control-C>", lambda e: _ao_copiar())
    if not apenas_leitura:
        inner.bind("<Control-x>", lambda e: _ao_recortar())
        inner.bind("<Control-X>", lambda e: _ao_recortar())
