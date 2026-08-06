"""Best-effort warmup helpers for optional rule-extraction dependencies."""

from __future__ import annotations

from functools import lru_cache
from threading import Lock

_SPACY_DOWNLOAD_LOCK = Lock()


def describe_rule_store() -> str:
    """Return a human-readable label for the active rule storage backend."""
    return "supabase:public.rules"


@lru_cache(maxsize=1)
def warm_optional_rule_pipeline_dependencies() -> tuple[str, ...]:
    """Ensure optional rule-extraction runtime assets are available when possible."""
    warning = _ensure_spacy_model("en_core_web_sm")
    return (warning,) if warning else ()


def _ensure_spacy_model(model_name: str) -> str | None:
    """Download the requested spaCy model on demand when spaCy is installed."""
    try:
        import spacy
    except ImportError:
        return "spaCy is not installed; keyword filtering remains unavailable."

    try:
        spacy.load(model_name)
        return None
    except OSError:
        pass

    with _SPACY_DOWNLOAD_LOCK:
        try:
            spacy.load(model_name)
            return None
        except OSError:
            try:
                from spacy.cli import download

                download(model_name)
                spacy.load(model_name)
                return None
            except Exception as exc:  # pragma: no cover - network/runtime dependent
                return (
                    f"Keyword filter auto-download failed for {model_name} "
                    f"({type(exc).__name__}: {exc})"
                )
