from fasthtml.common import (
    Caption as HtmlCaption,
    Div,
    Table as HtmlTable,
    Tbody as HtmlTbody,
    Td as HtmlTd,
    Tfoot as HtmlTfoot,
    Th as HtmlTh,
    Thead as HtmlThead,
    Tr as HtmlTr,
)

from .utils import cn


def Table(*children, cls: str | None = None, **kwargs):
    return Div(
        HtmlTable(
            *children,
            cls=cn("w-full caption-bottom text-sm", cls),
            **kwargs,
        ),
        cls="relative w-full overflow-x-auto",
    )


def TableHeader(*children, cls: str | None = None, **kwargs):
    return HtmlThead(*children, cls=cn("[&_tr]:border-b", cls), **kwargs)


def TableBody(*children, cls: str | None = None, **kwargs):
    return HtmlTbody(*children, cls=cn("[&_tr:last-child]:border-0", cls), **kwargs)


def TableFooter(*children, cls: str | None = None, **kwargs):
    return HtmlTfoot(
        *children,
        cls=cn("border-t bg-muted/50 font-medium [&>tr]:last:border-b-0", cls),
        **kwargs,
    )


def TableRow(*children, cls: str | None = None, **kwargs):
    return HtmlTr(
        *children,
        cls=cn(
            "border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted",
            cls,
        ),
        **kwargs,
    )


def TableHead(*children, cls: str | None = None, **kwargs):
    return HtmlTh(
        *children,
        cls=cn(
            "h-10 px-2 text-left align-middle font-medium text-muted-foreground "
            "[&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]",
            cls,
        ),
        **kwargs,
    )


def TableCell(*children, cls: str | None = None, **kwargs):
    return HtmlTd(
        *children,
        cls=cn(
            "p-2 align-middle [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]",
            cls,
        ),
        **kwargs,
    )


def TableCaption(*children, cls: str | None = None, **kwargs):
    return HtmlCaption(
        *children, cls=cn("mt-4 text-sm text-muted-foreground", cls), **kwargs
    )
