from rdflib.namespace import RDF

from app.modules.ifc_reader.bot_graph import BIMGUARD
from app.modules.ifc_reader.ontology_namespaces import AEC3PO, ELI, ODRL
from app.modules.rule_builder.aec3po_exporter import export_aec3po


def test_aec3po_exporter_nzbc_c2_2():
    rule = {
        "rule_id": "NZBC-C2-2",
        "rase_requirement": "Doors shall have a clear width >= 900mm",
        "rase_applicability": {"occupancy": "commercial"},
        "rase_selection": {"capacity_gt": 50},
        "rase_exception": {"has_sprinkler": True},
    }

    graph = export_aec3po([rule])

    # Check document and types
    doc = BIMGUARD["document/regulatory_act"]
    assert (doc, RDF.type, AEC3PO.Document) in graph
    assert (doc, RDF.type, ELI.LegalResource) in graph

    # Check statement and links -- a rule is an aec3po:CheckStatement, linked
    # from its document via the ontology's own hasSubdivision (not the
    # generic dct:hasPart AEC3PO.hasPart used to alias).
    statement = BIMGUARD["statement/NZBC-C2-2"]
    assert (statement, RDF.type, AEC3PO.CheckStatement) in graph
    assert (doc, AEC3PO.hasSubdivision, statement) in graph

    # Check RASE: each component is its own typed sub-statement node, linked
    # via the ontology's real requires/appliesTo/selects/except properties,
    # with content on aec3po:DocumentSubdivision_asLiteral.
    requirement = BIMGUARD["statement/NZBC-C2-2/requirement"]
    assert (statement, AEC3PO.requires, requirement) in graph
    assert (requirement, RDF.type, AEC3PO.RequirementStatement) in graph
    assert (requirement, AEC3PO.DocumentSubdivision_asLiteral, None) in graph

    applicability = BIMGUARD["statement/NZBC-C2-2/applicability"]
    assert (statement, AEC3PO.appliesTo, applicability) in graph
    assert (applicability, RDF.type, AEC3PO.ApplicationStatement) in graph

    selection = BIMGUARD["statement/NZBC-C2-2/selection"]
    assert (statement, AEC3PO.selects, selection) in graph
    assert (selection, RDF.type, AEC3PO.SelectionStatement) in graph

    exception = BIMGUARD["statement/NZBC-C2-2/exception"]
    assert (statement, AEC3PO["except"], exception) in graph
    assert (exception, RDF.type, AEC3PO.ExceptionStatement) in graph

    # Check ODRL Duty
    duties = list(graph.objects(statement, ODRL.hasPolicy))
    assert len(duties) == 1
    duty = duties[0]
    assert (duty, RDF.type, ODRL.Duty) in graph
    assert (duty, ODRL.target, BIMGUARD["shape/NZBC-C2-2"]) in graph


def test_aec3po_exporter_skips_empty_rase_fields():
    rule = {"rule_id": "EMPTY-RULE"}

    graph = export_aec3po([rule])

    statement = BIMGUARD["statement/EMPTY-RULE"]
    assert (statement, RDF.type, AEC3PO.CheckStatement) in graph
    for predicate in (AEC3PO.requires, AEC3PO.appliesTo, AEC3PO.selects, AEC3PO["except"]):
        assert list(graph.objects(statement, predicate)) == []
