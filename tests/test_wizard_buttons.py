"""Diagnostic: verify the FastHTML wizard component renders its buttons correctly.

Uses to_xml() to properly serialize FT nodes (not str(), which returns the id).

The contract this pins is the wizard's navigation: which actions each step
offers, that they all submit the form they sit in, and that Previous is present
but disabled on step 1 rather than missing. Those are the parts that stay
visually plausible while being broken.
"""

import re

import pytest
from fasthtml.common import to_xml

from app.components.project_setup_wizard import ProjectSetupWizard

#: ``action`` values each step is expected to offer. Reset is rendered on every
#: step (top right), Previous on every step (disabled on the first), and the
#: last step swaps Next for Cancel + Create Project.
EXPECTED_ACTIONS = {
    1: ["reset", "prev", "next"],
    2: ["reset", "prev", "next"],
    3: ["reset", "prev", "next"],
    4: ["reset", "prev", "next"],
    5: ["reset", "prev", "reset", "submit"],
}

#: Label per action, for the steps where it is unambiguous.
EXPECTED_LABELS = {
    "reset": {"Reset", "Cancel"},
    "prev": {"← Previous"},
    "next": {"Next →"},
    "submit": {"Create Project"},
}

BUTTON_TAG_RE = re.compile(r"<button[^>]*>")
BUTTON_RE = re.compile(r'<button[^>]*value="(\w+)"[^>]*>([^<]*)</button>')


def form_markup(html: str) -> str:
    """Return the ``<form>...</form>`` slice of ``html``, or ``""`` if absent.

    Every structural assertion runs against this slice rather than the whole
    document, because the rendered node also carries a ``<script>`` block whose
    source mentions buttons and actions literally.
    """
    if "<form" not in html or "</form>" not in html:
        return ""
    return html[html.find("<form") : html.rfind("</form>") + len("</form>")]


def buttons_in(html: str) -> list[tuple[str, str]]:
    """Return ``[(action, label)]`` for every button in ``html``, unescaped."""
    return [
        (action, label.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip())
        for action, label in BUTTON_RE.findall(html)
    ]


def has_disabled_attr(tag: str) -> bool:
    """Whether ``tag`` carries a real ``disabled`` attribute.

    Checked as a standalone attribute rather than a substring: every button
    carries Tailwind's ``disabled:opacity-40`` in its class list, so a naive
    ``"disabled" in tag`` reports every button as disabled.
    """
    return bool(re.search(r"\sdisabled(\s|>|=)", tag))


@pytest.mark.parametrize("step", sorted(EXPECTED_ACTIONS))
def test_wizard_buttons(step):
    """Each step renders its expected buttons, inside the form, as submits."""
    wizard = ProjectSetupWizard()

    # str() on an FT node returns the element's id ("wizard"), NOT markup.
    # Serialising with to_xml() is what makes these assertions meaningful.
    html = to_xml(wizard.render(current_step=step, form_data={}, documents=[]))

    form = form_markup(html)
    assert form, f"step {step} rendered no <form>"

    assert 'class="wiz-foot' in form or "wiz-foot" in form, (
        f"step {step}: wiz-foot is not inside the form, so its buttons "
        f"would submit nothing"
    )

    found = buttons_in(form)
    assert [action for action, _ in found] == EXPECTED_ACTIONS[step], (
        f"step {step}: expected {EXPECTED_ACTIONS[step]}, got {found}"
    )

    for action, label in found:
        assert label in EXPECTED_LABELS[action], f"step {step}: {action} labelled {label!r}"

    for match in BUTTON_TAG_RE.finditer(form):
        tag = match.group(0)
        assert 'type="submit"' in tag, f"step {step}: non-submit button {tag}"
        assert 'name="action"' in tag, f"step {step}: button without action {tag}"


def test_previous_is_disabled_on_step_one_and_enabled_after():
    """Present but disabled, so the footer does not reflow between steps."""
    wizard = ProjectSetupWizard()

    def prev_tag(step: int) -> str:
        html = to_xml(wizard.render(current_step=step, form_data={}, documents=[]))
        return next(t for t in BUTTON_TAG_RE.findall(html) if 'value="prev"' in t)

    assert has_disabled_attr(prev_tag(1))
    assert not has_disabled_attr(prev_tag(2))


def test_str_does_not_serialise_markup():
    """Guard the FastHTML trap this module's docstring warns about.

    ``str()`` on an FT node yields its id, so substring assertions written
    against ``str(node)`` silently check nothing.
    """
    node = ProjectSetupWizard().render(current_step=1, form_data={}, documents=[])
    assert str(node) == "wizard"
    assert len(to_xml(node)) > 1000
