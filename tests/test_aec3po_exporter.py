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

    # Check statement and links
    statement = BIMGUARD["statement/NZBC-C2-2"]
    assert (statement, RDF.type, AEC3PO.Statement) in graph
    assert (doc, AEC3PO.hasPart, statement) in graph

    # Check RASE
    assert list(graph.objects(statement, AEC3PO.hasRequirement))
    assert list(graph.objects(statement, AEC3PO.hasApplicability))
    assert list(graph.objects(statement, AEC3PO.hasSelection))
    assert list(graph.objects(statement, AEC3PO.hasException))

    # Check ODRL Duty
    duties = list(graph.objects(statement, ODRL.hasPolicy))
    assert len(duties) == 1
    duty = duties[0]
    assert (duty, RDF.type, ODRL.Duty) in graph
    assert (duty, ODRL.target, BIMGUARD["shape/NZBC-C2-2"]) in graph
