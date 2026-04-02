from fasthtml.common import A
from monsterui.all import Button, ButtonT, Form, UkIcon


def IconLinkButton(icon_name: str, href: str, title: str, cls=ButtonT.icon):
    return A(
        Button(UkIcon(icon_name, height=15, width=15), cls=cls),
        href=href,
        title=title,
    )


def IconPostButton(icon_name: str, action: str, title: str, cls=ButtonT.icon):
    return Form(
        Button(UkIcon(icon_name, height=15, width=15), cls=cls),
        method="post",
        action=action,
        title=title,
    )
