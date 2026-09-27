"""ISO 19650 National Annex container naming conventions and configuration contracts."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

__all__ = ['NamingCodeContract', 'NamingConventionContract', 'NamingTokenContract', 'CdeStatusContract', 'NamingCatalogResponseContract', 'NamingConfigContract', 'NamingConfigUpdateContract', 'NamingPreviewRequestContract', 'NamingPreviewResponseContract']

# ── ISO 19650 naming configuration ───────────────────────────────────────────


class NamingCodeContract(BaseModel):
    """One entry of the ISO 19650 code library: a code and what it stands for."""

    code: str = Field(..., description="The code as it appears in a container name, e.g. G00")
    label: str = Field(..., description="What the code stands for, e.g. Ground")

class NamingConventionContract(BaseModel):
    """One naming convention: a format string over the token vocabulary."""

    id: str = Field(..., description="Stable identifier, e.g. iso19650_date")
    name: str = Field(..., description="Display name")
    format: str = Field(..., description="Format string, e.g. {project}_{originator}_...")
    separator: str = Field("_", description="Field separator this format is written with")
    description: str = Field("", description="When to use this convention")
    preset: bool = Field(False, description="True for the five built-ins, which cannot be edited")
    iso_compliant: bool = Field(
        True, description="False for conventions offered for clash-test names, not for a CDE"
    )

class NamingTokenContract(BaseModel):
    """One token a convention format may contain."""

    token: str = Field(..., description="Token name without braces, e.g. originator")
    label: str = Field(..., description="What the token names")
    source: str = Field(
        ..., description="Where its value comes from: config, library or runtime"
    )

class CdeStatusContract(BaseModel):
    """One row of the CDE status table (ISO 19650-2 Table 1)."""

    code: str = Field(..., description="Status code, e.g. S1")
    label: str = Field(..., description="What the status means")
    colour: str = Field(..., description="Hex colour the status is drawn in")
    selectable: bool = Field(
        True, description="False for the rows shown for reference but not offered as a suitability"
    )

class NamingCatalogResponseContract(BaseModel):
    """The static half of the naming feature: everything not specific to a project."""

    conventions: list[NamingConventionContract] = Field(default_factory=list)
    tokens: list[NamingTokenContract] = Field(default_factory=list)
    codes: dict[str, list[NamingCodeContract]] = Field(
        default_factory=dict, description="Master library keyed by disciplines/volumes/levels/types"
    )
    cde_statuses: list[CdeStatusContract] = Field(default_factory=list)
    date_formats: list[str] = Field(default_factory=list)
    separators: list[str] = Field(default_factory=list)
    default_convention: str = Field("iso19650_date")

class NamingConfigContract(BaseModel):
    """A project's ISO 19650 naming configuration."""

    project_id: int
    is_configured: bool = Field(
        False, description="False when nothing has been saved and these are the defaults"
    )
    project_code: str = ""
    originator_code: str = ""
    type_code: str = "CO"
    suitability: str = "S1"
    revision: str = "01"
    separator: str = "_"
    date_format: str = "YYMMDD"
    class_a: str = ""
    class_b: str = ""
    active_convention: str = "iso19650_date"
    level_codes: list[NamingCodeContract] = Field(default_factory=list)
    type_codes: list[NamingCodeContract] = Field(default_factory=list)
    discipline_codes: list[NamingCodeContract] = Field(default_factory=list)
    volume_codes: list[NamingCodeContract] = Field(default_factory=list)
    custom_conventions: list[NamingConventionContract] = Field(default_factory=list)
    updated_at: Optional[str] = None

class NamingConfigUpdateContract(BaseModel):
    """Fields to write to a project's naming configuration.

    Every field is optional and only the ones supplied are written, so saving
    one tab of the form cannot blank the others.
    """

    project_code: Optional[str] = None
    originator_code: Optional[str] = None
    type_code: Optional[str] = None
    suitability: Optional[str] = None
    revision: Optional[str] = None
    separator: Optional[str] = None
    date_format: Optional[str] = None
    class_a: Optional[str] = None
    class_b: Optional[str] = None
    active_convention: Optional[str] = None
    level_codes: Optional[list[NamingCodeContract]] = None
    type_codes: Optional[list[NamingCodeContract]] = None
    discipline_codes: Optional[list[NamingCodeContract]] = None
    volume_codes: Optional[list[NamingCodeContract]] = None
    custom_conventions: Optional[list[NamingConventionContract]] = None

class NamingPreviewRequestContract(BaseModel):
    """A configuration to render a sample name from, without saving it."""

    config: NamingConfigUpdateContract = Field(
        default_factory=NamingConfigUpdateContract,
        description="The configuration being edited; unset fields fall back to the defaults",
    )
    overrides: dict[str, str] = Field(
        default_factory=dict,
        description="Values for the runtime tokens, e.g. {'sequence': '0042'}",
    )

class NamingPreviewResponseContract(BaseModel):
    """A rendered name and the convention that produced it."""

    name: str = Field(..., description="The rendered information container name")
    convention_id: str = Field(..., description="id of the convention actually applied")
    applied_format: str = Field(
        "",
        description=(
            "The format string as rendered, with the project's separator substituted "
            "for the one the convention was authored with"
        ),
    )
    unresolved_tokens: list[str] = Field(
        default_factory=list,
        description="Tokens left literal because nothing supplied a value for them",
    )
