from fasthtml.common import A
from monsterui.all import Button, ButtonT, Form, UkIcon


def IconLinkButton(icon_name: str, href: str, title: str, cls=ButtonT.icon):
    return A(
        Button(UkIcon(icon_name, height=15, width=15), cls=cls, aria_label=title),
        href=href,
        title=title,
    )


def IconPostButton(
    icon_name: str,
    action: str | None,
    title: str,
    cls=ButtonT.icon,
    button_type: str = "submit",
):
    button = Button(
        UkIcon(icon_name, height=15, width=15),
        type=button_type,
        title=title,
        cls=cls,
        aria_label=title,
    )
    if action is None:
        return button

    return Form(
        button,
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


def CreateAction(href: str, title: str = "Create", cls=ButtonT.icon):
    return IconLinkButton("plus", href=href, title=title, cls=cls)


def SaveAction(title: str = "Save", cls=ButtonT.icon):
    return IconPostButton(
        "save", action=None, title=title, cls=cls, button_type="submit"
    )


def CancelAction(href: str, title: str = "Cancel", cls=ButtonT.icon):
    return IconLinkButton("x", href=href, title=title, cls=cls)
