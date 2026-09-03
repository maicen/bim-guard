"""
ISO 19650 Container Naming & Metadata Validation Engine.

Standard: ISO 19650-2 / UK National Annex naming convention.
Container Naming Format:
    [Project]-[Originator]-[Volume/System]-[Level/Location]-[Type]-[Role]-[Number]
Example:
    PRJ1-BIMG-01-00-M3-A-0001.ifc
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Standard ISO 19650 Suitability Codes
VALID_SUITABILITY_CODES: set[str] = {
    "S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7",
    "A1", "A2", "A3", "A4",
    "B1", "B2", "B3", "B4",
    "CR",
}

# Recognized standard Document/Model Type codes
VALID_TYPE_CODES: set[str] = {
    "M3", "M2", "DR", "RP", "VS", "SH", "CO", "SK", "BQ", "MI",
}

# ISO 19650 UK National Annex regex: 7 hyphen-separated tokens
ISO_19650_FILENAME_REGEX = re.compile(
    r"^(?P<project_code>[A-Za-z0-9]+)-"
    r"(?P<originator>[A-Za-z0-9]+)-"
    r"(?P<volume_system>[A-Za-z0-9]+)-"
    r"(?P<level>[A-Za-z0-9]+)-"
    r"(?P<type>[A-Za-z0-9]+)-"
    r"(?P<role>[A-Za-z0-9]+)-"
    r"(?P<number>[0-9]+)"
    r"(?:_(?P<suitability>[A-Z0-9]+))?"
    r"(?:_(?P<revision>[A-Za-z0-9\.]+))?$",
    re.IGNORECASE
)

# Revision code pattern: e.g. P01.01 (WIP/Preliminary), C01 (Contract/Published)
REVISION_CODE_REGEX = re.compile(r"^(?:P\d{2}(?:\.\d{2})?|C\d{2}|D\d{2})$", re.IGNORECASE)


@dataclass
class ISOValidationResult:
    """Structured response from ISO 19650 naming container validation."""

    is_valid: bool
    fields: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return dictionary representation of validation result."""
        return {
            "is_valid": self.is_valid,
            "fields": self.fields,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class ISO19650Validator:
    """Enforces ISO 19650 National Annex container naming standards."""

    @staticmethod
    def validate_suitability_code(code: str) -> bool:
        """Return True if suitability code matches standard ISO 19650 codes."""
        if not code:
            return False
        return code.upper().strip() in VALID_SUITABILITY_CODES

    @staticmethod
    def validate_revision_code(code: str) -> bool:
        """Return True if revision code matches standard ISO 19650 revision syntax."""
        if not code:
            return False
        return bool(REVISION_CODE_REGEX.match(code.strip()))

    @classmethod
    def validate_filename(cls, filename: str) -> ISOValidationResult:
        """Validate filename against ISO 19650 UK National Annex standard naming string.

        Expected format:
            [Project]-[Originator]-[Volume]-[Level]-[Type]-[Role]-[Number].[ext]
        """
        raw_name = Path(filename).stem
        ext = Path(filename).suffix.lstrip(".").lower()

        match = ISO_19650_FILENAME_REGEX.match(raw_name)
        if not match:
            return ISOValidationResult(
                is_valid=False,
                errors=[
                    f"Filename '{filename}' does not follow ISO 19650 naming format: "
                    "[Project]-[Originator]-[Volume]-[Level]-[Type]-[Role]-[Number]"
                ],
            )

        groups = match.groupdict()
        fields = {
            "project_code": groups["project_code"].upper(),
            "originator": groups["originator"].upper(),
            "volume_system": groups["volume_system"].upper(),
            "level": groups["level"].upper(),
            "type": groups["type"].upper(),
            "role": groups["role"].upper(),
            "number": groups["number"],
            "extension": ext,
        }

        errors: list[str] = []
        warnings: list[str] = []

        if groups.get("suitability"):
            suit = groups["suitability"].upper()
            fields["suitability_code"] = suit
            if not cls.validate_suitability_code(suit):
                errors.append(f"Invalid suitability code '{suit}'. Expected one of {sorted(VALID_SUITABILITY_CODES)}")
        else:
            fields["suitability_code"] = "S0"

        if groups.get("revision"):
            rev = groups["revision"].upper()
            fields["revision_code"] = rev
            if not cls.validate_revision_code(rev):
                warnings.append(f"Non-standard revision format '{rev}'. Standard formats: P01.01, C01, P01")
        else:
            fields["revision_code"] = "P01.01"

        if fields["type"] not in VALID_TYPE_CODES:
            warnings.append(f"Unrecognized Type code '{fields['type']}'. Common codes: {sorted(VALID_TYPE_CODES)}")

        return ISOValidationResult(
            is_valid=len(errors) == 0,
            fields=fields,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def cross_reference_header(
        self, filename: str, header_project_name: str | None
    ) -> ISOValidationResult:
        """Cross-reference parsed file metadata against IFC project header attributes."""
        res = self.validate_filename(filename)
        if not res.is_valid or not header_project_name:
            return res

        header_clean = header_project_name.strip().upper()
        prj_code = res.fields.get("project_code", "")

        if prj_code and prj_code not in header_clean and header_clean not in prj_code:
            res.warnings.append(
                f"Mismatch between filename project_code ('{prj_code}') and IfcProject.Name ('{header_project_name}')"
            )

        return res
