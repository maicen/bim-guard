"""Tests for IFC Pre-Flight Validation Service & Upload Gateway."""

from app.modules.phase_6.phase_6a_upload import FileUploadService
from app.services.ifc_validation_service import IFCValidationService

SAMPLE_VALID_IFC = b"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
FILE_NAME('sample.ifc','2026-09-01T10:00:00',('Author'),('Org'),'Preprocessor','OriginatingSystem','Authorization');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPROJECT('2O2Fr$t4X7Zf8NOew3FL01',#2,'BIMGuard Test Project',$,$,$,$,(#3),#4);
#2=IFCOWNERHISTORY(#5,#6,$,.ADDED.,$,$,$,$);
#3=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#7,$);
#4=IFCUNITASSIGNMENT((#8));
#5=IFCPERSONANDORGANIZATION(#9,#10,$);
#6=IFCAPPLICATION(#10,'2026','BIMGuard App','BIMGuard');
#7=IFCAXIS2PLACEMENT3D(#11,#12,#13);
#8=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);
#9=IFCPERSON($,'Engineer',$,$,$,$,$,$);
#10=IFCORGANIZATION($,'BIMGuard AI',$,$,$);
#11=IFCCARTESIANPOINT((0.,0.,0.));
#12=IFCDIRECTION((0.,0.,1.));
#13=IFCDIRECTION((1.,0.,0.));
#20=IFCBUILDING('2O2Fr$t4X7Zf8NOew3FL02',#2,'Building A',$,$,#7,$,$,.ELEMENT.,$,$,$);
#21=IFCRELAGGREGATES('2O2Fr$t4X7Zf8NOew3FL03',#2,$,$,#1,(#20));
ENDSEC;
END-ISO-10303-21;
"""

SAMPLE_CORRUPTED_SYNTAX_IFC = b"""NOT_AN_IFC_HEADER;
THIS_IS_CORRUPTED_DATA_WITHOUT_STEP_STRUCTURE
"""

SAMPLE_INVALID_SCHEMA_IFC = b"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('bad_schema.ifc','2026-09-01',(),(),'','','');
FILE_SCHEMA(('IFC_UNKNOWN_CUSTOM_NONSTANDARD_999'));
ENDSEC;
DATA;
#1=IFCPROJECT('2O2Fr$t4X7Zf8NOew3FL01',$,'Project',$,$,$,$,(),$);
ENDSEC;
END-ISO-10303-21;
"""


def test_ifc_validation_valid_file():
    service = IFCValidationService()
    report = service.validate_bytes(SAMPLE_VALID_IFC, filename="sample.ifc")
    assert report.valid is True
    assert report.schema_version == "IFC4"
    assert report.syntax_stage.passed is True
    assert report.schema_stage.passed is True
    assert report.fatal_errors == 0


def test_ifc_validation_corrupted_syntax():
    service = IFCValidationService()
    report = service.validate_bytes(SAMPLE_CORRUPTED_SYNTAX_IFC, filename="corrupt.ifc")
    assert report.valid is False
    assert report.syntax_stage.passed is False
    assert report.fatal_errors > 0
    assert any(i.rule_code == "IFC-SYN-003" for i in report.syntax_stage.details)


def test_ifc_validation_unsupported_schema():
    service = IFCValidationService()
    report = service.validate_bytes(SAMPLE_INVALID_SCHEMA_IFC, filename="bad_schema.ifc")
    assert report.valid is False
    assert report.schema_stage.passed is False
    assert any(i.rule_code == "IFC-SCH-001" for i in report.schema_stage.details)


def test_upload_service_preflight_rejects_corrupted_ifc(tmp_path):
    class MockStorage:
        def save_upload(self, name, content, subdir):
            return f"sb://bucket/{subdir}/{name}"

    class MockTable:
        def insert(self, row):
            return 1

    upload_svc = FileUploadService(storage=MockStorage(), table=MockTable())

    # Corrupted upload should be rejected early
    resp_corrupt = upload_svc.upload("corrupted.ifc", SAMPLE_CORRUPTED_SYNTAX_IFC, kind="ifc")
    assert resp_corrupt.success is False
    assert "IFC Validation Failed" in (resp_corrupt.error or "")

    # Valid upload should succeed with validation report
    resp_valid = upload_svc.upload("valid.ifc", SAMPLE_VALID_IFC, kind="ifc")
    assert resp_valid.success is True
    assert resp_valid.validation_report is not None
    assert resp_valid.validation_report.valid is True
