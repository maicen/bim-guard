"""Diagnostic: verify FastHTML wizard component renders buttons correctly.
Uses to_xml() to properly serialize FT nodes (not str() which returns ID).
"""

import re

import pytest
from fasthtml.common import to_xml

from app.components.project_setup_wizard import ProjectSetupWizard

#: Button labels each step is expected to render, keyed by the button's
#: ``value`` -- the ``action`` that ``handle_wizard_post`` dispatches on.
EXPECTED = {
    1: {"next": "Next →"},
    2: {"prev": "← Back", "next": "Next →"},
    3: {"prev": "← Back", "next": "Next →"},
    4: {"prev": "← Back", "next": "Next →"},
    5: {"prev": "← Back", "submit": "Create Project & Proceed"},
}

BUTTON_RE = re.compile(r'<button[^>]*value="(\w+)"[^>]*>([^<]*)</button>')


def buttons_in(html: str) -> dict[str, str]:
    """Return ``{action: label}`` for every button in ``html``, unescaped.

    Matching on the ``value`` attribute rather than the label text avoids a
    false negative on step 5, whose label serialises as
    ``Create Project &amp; Proceed``.
    """
    return {
        action: label.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        for action, label in BUTTON_RE.findall(html)
    }


def form_markup(html: str) -> str:
    """Return the ``<form>...</form>`` slice of ``html``, or ``""`` if absent.

    Every structural assertion runs against this slice rather than the whole
    document, because the rendered node also carries a ``<style>`` block whose
    rules and comments mention ``wiz-foot`` and ``<button>`` literally.
    """
    if "<form" not in html or "</form>" not in html:
        return ""
    return html[html.find("<form"):html.find("</form>") + len("</form>")]


@pytest.mark.parametrize("step", sorted(EXPECTED))
def test_wizard_buttons(step):
    """Each step renders its expected buttons, inside the form, as submits."""
    wizard = ProjectSetupWizard()

    # str() on an FT node returns the element's id ("wizard"), NOT markup.
    # Serialising with to_xml() is what makes these assertions meaningful.
    html = to_xml(wizard.render(current_step=step, form_data={}))

    form = form_markup(html)
    assert form, f"step {step} rendered no <form>"

    assert 'class="wiz-foot"' in form, (
        f"step {step}: wiz-foot is not inside the form, so its buttons "
        f"would submit nothing"
    )

    assert buttons_in(form) == EXPECTED[step], (
        f"step {step}: expected {EXPECTED[step]}, got {buttons_in(form)}"
    )

    for match in re.finditer(r"<button[^>]*>", form):
        tag = match.group(0)
        assert 'type="submit"' in tag, f"step {step}: non-submit button {tag}"
        assert 'name="action"' in tag, f"step {step}: button without action {tag}"


def test_str_does_not_serialise_markup():
    """Guard the FastHTML trap this module's docstring warns about.

    ``str()`` on an FT node yields its id, so substring assertions written
    against ``str(node)`` silently check nothing.
    """
    node = ProjectSetupWizard().render(current_step=1, form_data={})
    assert str(node) == "wizard"
    assert len(to_xml(node)) > 1000
