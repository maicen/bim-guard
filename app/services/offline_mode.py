"""Single operator switch for air-gapped / fully offline deployments.

``BIMGUARD_OFFLINE=true`` means this installation must not depend on the public
internet. Services consult :func:`offline_mode_enabled` and degrade to their
local data instead of attempting (and waiting on) outbound requests:

* bSDD lookups read only the bundled DuckDB ontology
  (``data/reference/bsdd``) and the runtime cache; there is no live fallback.
* LLM provider base URLs may point at private-network model servers
  (see ``ssrf_protection.private_llm_hosts_allowed``), because a hosted
  provider is unreachable by definition.
* The 3D viewer is served as a self-contained bundle when the image was built
  with ``VENDOR_VIEWER=true`` (see ``scripts/vendor_viewer.mjs``); that part is
  decided at image build time, not by this flag.

Off by default so the hosted bim-guard.xyz deployment is unchanged.
"""

from __future__ import annotations

import os

OFFLINE_ENV = "BIMGUARD_OFFLINE"
_TRUTHY = {"1", "true", "yes", "on"}


def offline_mode_enabled() -> bool:
    """Whether the operator has declared this deployment offline / air-gapped."""
    return os.environ.get(OFFLINE_ENV, "").strip().lower() in _TRUTHY
