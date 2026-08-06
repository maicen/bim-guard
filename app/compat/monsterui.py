"""Compatibility helpers for MonsterUI API differences across versions."""

from __future__ import annotations

import importlib

import monsterui.all as monsterui_all


def _load_attr(module_name: str, attr_name: str):
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def ensure_monsterui_compat() -> None:
    """Expose legacy helpers expected by the app across MonsterUI versions."""
    fallbacks = {
        "Div": ("fasthtml.common", "Div"),
        "P": ("fasthtml.common", "P"),
        "Title": ("fasthtml.common", "Title"),
        "A": ("fasthtml.common", "A"),
    }

    for attr_name, (module_name, symbol_name) in fallbacks.items():
        if not hasattr(monsterui_all, attr_name):
            setattr(monsterui_all, attr_name, _load_attr(module_name, symbol_name))

    if hasattr(monsterui_all, "CardContent"):
        return

    try:
        from app.components.ui.card import CardContent as compat_card_content
    except Exception:
        try:
            compat_card_content = monsterui_all.CardContainer
        except AttributeError:
            return

    setattr(monsterui_all, "CardContent", compat_card_content)
