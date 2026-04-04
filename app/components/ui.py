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


def ViewAction(href: str, title: str = "View", cls=ButtonT.icon):
    return IconLinkButton("eye", href=href, title=title, cls=cls)


def EditAction(href: str, title: str = "Edit", cls=ButtonT.icon):
    return IconLinkButton("pencil", href=href, title=title, cls=cls)


def DeleteAction(action: str, title: str = "Delete", cls=ButtonT.icon):
    return IconPostButton("trash-2", action=action, title=title, cls=cls)


def BackAction(href: str, title: str = "Back", cls=ButtonT.icon):
    return IconLinkButton("arrow-left", href=href, title=title, cls=cls)


def CreateAction(href: str, title: str = "Create", cls=ButtonT.primary):
    return IconLinkButton("plus", href=href, title=title, cls=cls)
