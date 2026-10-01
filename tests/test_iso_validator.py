"""Unit tests for ISO19650Validator container naming and metadata engine."""

from __future__ import annotations

from app.modules.document_parsing.iso_validator import (
    ISO19650Validator,
)


def test_valid_standard_7_token_filename():
    filename = "PRJ1-BIMG-01-00-M3-A-0001.ifc"
    result = ISO19650Validator.validate_filename(filename)

    assert result.is_valid is True
    assert result.errors == []
    assert result.fields["project_code"] == "PRJ1"
    assert result.fields["originator"] == "BIMG"
    assert result.fields["volume_system"] == "01"
    assert result.fields["level"] == "00"
    assert result.fields["type"] == "M3"
    assert result.fields["role"] == "A"
    assert result.fields["number"] == "0001"
    assert result.fields["extension"] == "ifc"
    assert result.fields["suitability_code"] == "S0"
    assert result.fields["revision_code"] == "P01.01"


def test_valid_filename_with_suitability_and_revision():
    filename = "PRJ1-BIMG-01-00-M3-A-0001_S2_P02.01.ifc"
    result = ISO19650Validator.validate_filename(filename)

    assert result.is_valid is True
    assert result.errors == []
    assert result.fields["suitability_code"] == "S2"
    assert result.fields["revision_code"] == "P02.01"


def test_contract_revision_c01():
    filename = "HSP-ARCH-ZZ-ZZ-RP-A-0042_A1_C01.pdf"
    result = ISO19650Validator.validate_filename(filename)

    assert result.is_valid is True
    assert result.errors == []
    assert result.fields["suitability_code"] == "A1"
    assert result.fields["revision_code"] == "C01"
    assert result.fields["extension"] == "pdf"


def test_invalid_tokens_count_fails():
    # Only 5 tokens
    filename = "PRJ1-BIMG-01-00-M3.ifc"
    result = ISO19650Validator.validate_filename(filename)

    assert result.is_valid is False
    assert len(result.errors) == 1
    assert "does not follow ISO 19650 naming format" in result.errors[0]


def test_invalid_suitability_code_produces_error():
    filename = "PRJ1-BIMG-01-00-M3-A-0001_INVALID_P01.ifc"
    result = ISO19650Validator.validate_filename(filename)

    assert result.is_valid is False
    assert any("Invalid suitability code 'INVALID'" in err for err in result.errors)


def test_non_standard_revision_produces_warning():
    filename = "PRJ1-BIMG-01-00-M3-A-0001_S0_REV99XYZ.ifc"
    result = ISO19650Validator.validate_filename(filename)

    assert result.is_valid is True
    assert any("Non-standard revision format 'REV99XYZ'" in w for w in result.warnings)


def test_unrecognized_type_produces_warning():
    filename = "PRJ1-BIMG-01-00-ZZ-A-0001.ifc"
    result = ISO19650Validator.validate_filename(filename)

    assert result.is_valid is True
    assert any("Unrecognized Type code 'ZZ'" in w for w in result.warnings)


def test_to_dict_serialization():
    filename = "PRJ1-BIMG-01-00-M3-A-0001.ifc"
    res = ISO19650Validator.validate_filename(filename)
    payload = res.to_dict()

    assert payload["is_valid"] is True
    assert isinstance(payload["fields"], dict)
    assert isinstance(payload["errors"], list)
    assert isinstance(payload["warnings"], list)


def test_cross_reference_header_match():
    filename = "PRJ1-BIMG-01-00-M3-A-0001.ifc"
    res = ISO19650Validator.cross_reference_header(filename, "PRJ1 - Commercial Tower")

    assert res.is_valid is True
    assert not any("Mismatch" in w for w in res.warnings)


def test_cross_reference_header_mismatch():
    filename = "PRJ1-BIMG-01-00-M3-A-0001.ifc"
    res = ISO19650Validator.cross_reference_header(filename, "OTHER_PROJECT_NAME")

    assert res.is_valid is True
    assert any("Mismatch between filename project_code" in w for w in res.warnings)


def test_validate_suitability_code_direct():
    assert ISO19650Validator.validate_suitability_code("S1") is True
    assert ISO19650Validator.validate_suitability_code("CR") is True
    assert ISO19650Validator.validate_suitability_code("") is False
    assert ISO19650Validator.validate_suitability_code("S99") is False


def test_validate_revision_code_direct():
    assert ISO19650Validator.validate_revision_code("P01.01") is True
    assert ISO19650Validator.validate_revision_code("C02") is True
    assert ISO19650Validator.validate_revision_code("D01") is True
    assert ISO19650Validator.validate_revision_code("") is False
    assert ISO19650Validator.validate_revision_code("VERSION_1") is False
