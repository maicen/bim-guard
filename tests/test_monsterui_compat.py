import monsterui.all as monsterui_all

from app.compat.monsterui import ensure_monsterui_compat


def test_monsterui_compat_exposes_card_content() -> None:
    ensure_monsterui_compat()

    assert hasattr(monsterui_all, "CardContent")
    from app.components.ui.card import CardContent as app_card_content

    assert app_card_content is monsterui_all.CardContent