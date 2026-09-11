# **Software Requirements Specification for Semantic Knowledge Graph and Regulatory Ontology Integration in BIM-Guard**

## **System Architecture and Integration Framework**

The BIM-Guard platform operates as an openBIM Automated Code Compliance Checking (ACCC) and quality assurance system [1]. The baseline system relies on a decoupled architecture comprising a FastAPI backend gateway, a Svelte 5 single-page application (SPA) featuring an interactive 3D viewport, persistence layers backed by Supabase Postgres and object storage, and specialized rule-checking engines for seismic clearance (GC-001) and material corrosion interactions (CC-001/MC-001) [1]. The system also incorporates natural language processing pipelines powered by LiteLLM to extract compliance rules from building code documentation [1].

While the existing system successfully extracts rule entities and parses Industry Foundation Classes (IFC) geometry, it relies on procedural checking routines and heuristic parsing [1]. This approach presents limitations in traceability, multi-standard semantic alignment, and verifiable code enforcement [2]. To establish a standards-compliant automated compliance checking framework, BIM-Guard must transition to a Linked Building Data (LBD) architecture [4].

The target system integrates heterogeneous semantic web ontologies into a unified knowledge graph. The system architecture coordinates data ingestion, graph lifting, terminology alignment, and constraint validation through four primary layers:

> 1. The Physical and Spatial Layer ingests IFC STEP physical models, parsing building topology into the Building Topology Ontology (BOT) [5], distribution elements into SAREF4BLDG [7], product assemblies into the Building Product Ontology (BPO), and preserving precise element identities via selective ifcOWL alignments [4].
> 2. The Classification and Terminology Layer connects local model terms to international registries via the buildingSMART Data Dictionary (bSDD) REST API, normalizing classification systems (Uniclass, OmniClass, CoClass) and binding physical properties to the QUDT units of measure ontology [10].
> 3. The Regulatory and Legal Knowledge Layer decomposes statutory text into machine-readable structures using the Architecture, Engineering, Construction Compliance Checking and Permitting Ontology (AEC3PO) [10], European Legislation Identifier (ELI) [10], RASE methodology (Requirement, Applicability, Selection, Exception) [13], Digital Construction Ontologies (DICON) [15], and Open Digital Rights Language (ODRL) deontic policies [16].
> 4. The Execution and Validation Layer combines the domain instance graph and the regulatory shapes graph within an in-memory PyOxigraph triplestore, executing W3C Shapes Constraint Language (SHACL) and SHACL-SPARQL constraints to evaluate compliance and generate verifiable audit trails [18].

The runtime engine coordinates these layers through an asynchronous pipeline. When an IFC model is uploaded, the FastAPI backend initiates structural parsing via IfcOpenShell [1]. Instead of generating a monolithic ifcOWL serialization, the pipeline extracts topological relationships into BOT nodes and routes MEP elements into SAREF4BLDG branches [6]. Simultaneously, classification references query the bSDD cache to bind standard URI identifiers to the elements [11].

The regulatory engine processes ingested standards through LiteLLM, generating structured RASE objects translated into AEC3PO statements and operational SHACL shapes [1]. During the validation phase, the merged graph undergoes SHACL shape validation [18]. Violations trigger the generation of an AEC3PO verification report, which streams progress via Server-Sent Events (SSE) and populates buildingSMART BCF REST endpoints for issue resolution [1].

| Architecture Layer               | Core Standards and Ontologies                           | Target Namespace IRI                                                                                                                     | Functional Responsibility in BIM-Guard                                                                                                    |
| :------------------------------- | :------------------------------------------------------ | :--------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------- |
| **Legal & Regulatory Rules**     | AEC3PO [12], ELI [10], ODRL [16], RASE [13], DICON [15] | https://w3id.org/lbd/aec3po/ http://data.europa.eu/eli/ontology# http://www.w3.org/ns/odrl/2/ https://w3id.org/digitalconstruction/      | Deconstructs statutory building acts, encodes deontic duties/prohibitions, and models verification stages across project lifecycles [12]. |
| **Classifications & Concepts**   | bSDD [11], Uniclass, OmniClass, QUDT [10]               | https://identifier.buildingsmart.org/uri/ http://qudt.org/schema/qudt/                                                                   | Resolves property vocabularies, normalizes product classifications, and standardizes dimensional physical units [10].                     |
| **Building Topology & Elements** | BOT [6], ifcOWL [4], BPO, SAREF4BLDG [7]                | https://w3id.org/bot# http://standards.buildingsmart.org/IFC/DEV/IFC4/ADD2/OWL# https://w3id.org/bpo# https://saref.etsi.org/saref4bldg/ | Represents spatial hierarchies, thermal/egress boundaries, equipment distributions, and composite physical building assemblies [6].       |
| **Execution & Validation**       | W3C SHACL [18], SPARQL 1.1, SWRL [18]                   | http://www.w3.org/ns/shacl# http://www.w3.org/2005/sparql-results#                                                                       | Executes declarative shape constraints and complex multi-variable graph pattern checks to verify design compliance [18].                  |

## **Building Geometry and Spatial Topology Integration**

The physical, spatial, and topological characteristics of uploaded Industry Foundation Classes (IFC) models must be ingested into an RDF graph structure [4]. Converting an entire IFC model into full ifcOWL results in substantial file size growth and deep list nesting that degrades graph query performance [4].

Consequently, BIM-Guard employs a hybrid Linked Building Data approach: core spatial topology is mapped to the Building Topology Ontology (BOT) [5], mechanical systems are mapped to SAREF4BLDG [7], and product breakdowns are mapped to the Building Product Ontology (BPO). Detailed geometric representations from ifcOWL are retained selectively as isolated subgraphs or property literals [4].

The ingestion pipeline uses IfcOpenShell within the Python backend [1]. During pre-flight verification, the file is validated against STEP ISO 10303-21 syntax rules [1]. Once verified, the parser traverses the IFC object tree, extracting spatial entities into BOT instances and MEP systems into SAREF4BLDG instances [6]. This hybrid structure isolates topological and property relationships from complex geometric definitions, providing efficient graph evaluation while preserving spatial context [4].

| IFC Source Entity                 | Target Ontology Class                 | Target Predicate / Relationship                 | Semantic Transformation Description                                                    |
| :-------------------------------- | :------------------------------------ | :---------------------------------------------- | :------------------------------------------------------------------------------------- |
| IfcProject                        | bot:Zone [6]                          | rdf:type bot:Zone                               | Root spatial container representing the overarching project context [6].               |
| IfcSite                           | bot:Site [6]                          | rdf:type bot:Site ; bot:containsZone            | Subsumed by bot:Zone; represents the physical land boundary containing buildings [6].  |
| IfcBuilding                       | bot:Building [6]                      | rdf:type bot:Building ; bot:containsZone        | Physical structure situated within the site hierarchy [6].                             |
| IfcBuildingStorey                 | bot:Storey [6]                        | rdf:type bot:Storey ; bot:containsZone          | Horizontal vertical stratification layer containing spaces and elements [6].           |
| IfcSpace                          | bot:Space [6]                         | rdf:type bot:Space ; bot:hasSpace               | Functional 3D volume utilized for spatial queries, occupancy, and egress analysis [6]. |
| IfcRelAggregates                  | bot:containsZone [6, 25]              | bot:containsZone                                | Spatial hierarchy parent-to-child relationship link [6].                               |
| IfcRelContainedInSpatialStructure | bot:hasElement [6]                    | bot:hasElement                                  | Links a physical component to its immediate containing spatial zone [6].               |
| IfcRelSpaceBoundary               | bot:Interface [6]                     | bot:interfaceOf ; bot:adjacentElement           | Bidirectional connection between an enclosed space and its bounding elements [6].      |
| IfcWall, IfcDoor, IfcSlab         | bot:Element [6]                       | rdf:type bot:Element                            | Physical construction components bounding or occupying building zones [6].             |
| IfcDistributionElement            | s4bldg:DistributionDevice [8, 25]     | rdf:type s4bldg:DistributionDevice              | Core generalization for MEP, piping, and electrical distribution network devices [8].  |
| IfcFlowController                 | s4bldg:FlowController [7]             | rdf:type s4bldg:FlowController                  | Flow regulation devices including dampers, regulators, and valves [7].                 |
| IfcEnergyConversionDevice         | s4bldg:EnergyConversionDevice [7, 25] | rdf:type s4bldg:EnergyConversionDevice          | Energy transfer and conversion units such as boilers, chillers, and coils [7].         |
| IfcSensor, IfcAlarm               | s4bldg:Sensor, s4bldg:Alarm [7, 26]   | rdf:type s4bldg:Sensor ; rdf:type s4bldg:Alarm  | Monitoring instruments, protective devices, and life safety terminals [6].             |
| IfcElementAssembly                | bpo:ProductAssembly                   | rdf:type bpo:ProductAssembly ; bpo:hasComponent | Deconstructed multi-component products, prefabricated modules, or seismic bracing [1]. |

The system executes the extraction process according to strict functional requirements:

- The system shall parse uploaded IFC models via IfcOpenShell and map spatial hierarchy records into valid BOT graph structures conforming to https://w3id.org/bot# [1].
- The system shall convert spatial aggregation relationships into bot:containsZone triples and assign physical building elements to spaces using bot:hasElement [6].
- The system shall map physical boundaries defined in IfcRelSpaceBoundary into instances of bot:Interface, recording topological adjacency between rooms and structural components via bot:adjacentElement and bot:adjacentZone [6].
- The system shall identify distribution systems and MEP components, mapping them into specific SAREF4BLDG classes subsumed under s4bldg:DistributionDevice [7].
- The system shall preserve the global unique identifier (GUID) of each building entity by attaching it as an explicit identity literal, enabling bidirectional synchronization with the upstream IFC model and downstream BCF endpoints [1].

## **Standardized Dictionaries and Classification Services Integration**

BIM authoring platforms often serialize identical architectural parameters under varying names and language conventions [9]. For instance, fire endurance ratings may be labeled FireRating, FRR, REI, or Feuerwiderstand depending on the software vendor and localization template. These naming variations complicate automated compliance rules.

To resolve semantic ambiguity, BIM-Guard integrates the buildingSMART Data Dictionary (bSDD) [1]. The bSDD service acts as an online registry indexing international classification systems (Uniclass, OmniClass, CoClass), standard property sets, and material definitions based on ISO 12006-3 [11].

The integration pipeline automatically maps arbitrary element property sets to stable bSDD uniform resource identifiers (URIs) [11]. When an IFC model is ingested, the system extracts all classification references and queries the bSDD API [11]. If an entity specifies an OmniClass or Uniclass code, the service retrieves its canonical definition, allowed properties, and parent taxonomies [11].

Terminology Resolution and Enrichment Pipeline Flow: An uploaded IFC element (containing an IfcClassificationReference such as "Pr_20_29_21_24" and local properties like "FireResistance = 60 mins") is passed to the bSDD Client Ingestion component. The system checks the local Supabase bsdd_cache table; on a cache match, it retrieves the cached JSON schema and canonical URI, while on a cache miss, it queries the live bSDD REST Endpoint and updates the cache. Finally, Semantic Graph Enrichment assigns the canonical class URI, normalizes properties to predicates like bimguard:fireRatingDuration, and standardizes units via QUDT (e.g., qudt:numericValue 3600.0 ; unit:SEC).

Alongside classification resolution, physical quantities are normalized using the QUDT (Quantities, Units, Dimensions, and Data Types) ontology (http://qudt.org/schema/qudt/) [10]. Building codes specify thresholds in varied units (e.g., millimeters, meters, inches, hours, minutes). The normalization engine converts these values into standardized SI units typed with explicit QUDT individuals (unit:M, unit:SEC, unit:M2, unit:KiloGM) [10].

The dictionary integration operates under specific functional criteria:

- The system shall implement an asynchronous HTTP client connecting to https://api.bsdd.buildingsmart.org to resolve classification and property definitions [11].
- The system shall inspect all IfcClassificationReference nodes and match classification strings against bSDD domains to associate elements with canonical URIs [11].
- The system shall normalize local property set entries into standardized linked data predicates anchored to bSDD property identifiers [11].
- The system shall map physical measurements and dimensional limits to QUDT instances, standardizing numeric values into explicit SI datatypes [10].
- The system shall cache resolved bSDD classifications and property specifications in a Supabase Postgres table (bsdd_cache), enabling offline validation and maintaining sub-second query response times [1].

## **Regulatory, Legal, and Process Ontology Modeling**

Automated compliance checking requires formalizing statutory text into machine-readable knowledge representations [2]. Building regulations consist of complex structures: administrative hierarchies, jurisdictional limits, technical scopes, conditional exemptions, and deontic obligations [12].

To capture these facets, BIM-Guard integrates a suite of regulatory ontologies: the Architecture, Engineering, Construction Compliance Checking and Permitting Ontology (AEC3PO) [10], the European Legislation Identifier (ELI) [10], RASE-based Building Code Ontologies (BCO) [13], the Open Digital Rights Language (ODRL) [16], and Digital Construction Ontologies (DICON) [15].

AEC3PO structures regulatory content into modular components [10]. Regulatory acts are represented as aec3po:Document instances, and individual sections, articles, and paragraphs are modeled as aec3po:DocumentSubdivision linked via aec3po:hasPart [10]. ELI attributes (eli:LegalResource, eli:passed_by, eli:date_document) capture jurisdictional authority and enactment dates to verify legal currency [10].

The requirements within each regulatory clause are modeled using subclasses of aec3po:Statement [10]. Prescriptive thresholds instantiate aec3po:NumericalCheckStatement [10], qualitative conditions instantiate aec3po:BooleanCheckStatement [10], and multi-criteria conditions instantiate aec3po:CheckListStatement [10].

Statutory Clause Decomposition Pipeline Flow: Plain regulatory text (e.g., egress door fire resistance requirements) is processed by the LiteLLM extraction engine to generate RASE semantic facets: Applicability (building type and systems), Selection (target components), Requirement (mandatory thresholds), and Exception (waiver conditions). These facets are then lifted into graph constructs including aec3po:Statement anchors, eli:LegalResource references, ODRL duties/permissions, and DICON constraints.

To bridge natural language regulations and formal graphs, BIM-Guard updates its LiteLLM extraction pipeline to structure extracted clauses according to the RASE methodology [1]:

- Requirement (R) defines the mandatory condition or threshold that must be achieved [13].
- Applicability (A) specifies the building classification, height, occupancy, or regional context that triggers the rule [13].
- Selection (S) identifies the target building components governed by the clause [13].
- Exception (E) specifies criteria under which the requirement is waived or superseded [13].

These RASE components are mapped into the AEC3PO RASE module (aec3po:RequirementStatement, aec3po:ApplicationStatement, aec3po:SelectionStatement, aec3po:ExceptionStatement) using corresponding properties (aec3po:requires, aec3po:appliesTo, aec3po:selects, aec3po:except) [10].

Statutory requirements express legal modalities that must be enforced during validation. These are represented using the Open Digital Rights Language (ODRL) ontology (http://www.w3.org/ns/odrl/2/) [16].

Mandatory requirements are instantiated as odrl:duty policies [16]. Design permissions and explicit code exemptions are modeled as odrl:permission policies [16]. Prohibited configurations—such as installing non-isolated dissimilar metals in corrosive environments or running unprotected conduits through fire exits—are modeled as odrl:prohibition policies [1].

Temporal constraints, construction milestones, and changing design variables are captured using Digital Construction Ontologies (DICON) [15]. DICON links building elements to project phases, environmental parameters, and verification activities using dicc:Constraint and dicv:Variable, ensuring compliance checks reflect the appropriate lifecycle stage under ISO 19650 workflows [1].

| Regulatory Concept         | Ontology Modeling Construct          | Semantic Class or Predicate             | Operational Compliance Role                                                 |
| :------------------------- | :----------------------------------- | :-------------------------------------- | :-------------------------------------------------------------------------- |
| **Statutory Document**     | AEC3PO Document Module [10]          | aec3po:Document                         | Anchors legal acts, specifications, or regional standards [10].             |
| **Document Section**       | AEC3PO Document Module [10]          | aec3po:DocumentSubdivision              | Encodes hierarchical sections, chapters, or clauses [10].                   |
| **Legislative Provenance** | European Legislation Identifier [10] | eli:LegalResource [10]                  | Tracks official publication source, authority, and date [10].               |
| **Prescriptive Limit**     | AEC3PO Statement Module [10]         | aec3po:NumericalCheckStatement [10, 28] | Defines computable limits (e.g., minimum door width ≥ 850 mm) [28].         |
| **Qualitative Rule**       | AEC3PO Statement Module [10]         | aec3po:BooleanCheckStatement [10, 12]   | Enforces binary conditions (e.g., presence of emergency exit signage) [12]. |
| **RASE Requirement**       | AEC3PO RASE Module [10]              | aec3po:RequirementStatement [10]        | Represents the primary pass/fail criterion [13].                            |
| **RASE Exception**         | AEC3PO RASE Module [10]              | aec3po:ExceptionStatement [10]          | Relieves elements from compliance when conditions are met [13].             |
| **Legal Obligation**       | ODRL Deontic Profile [16]            | odrl:duty [16, 30]                      | Identifies mandatory conditions requiring design fulfillment [16].          |
| **Legal Prohibition**      | ODRL Deontic Profile [16]            | odrl:prohibition [16, 30]               | Identifies disallowed architectural layouts or material pairings [1].       |
| **Dynamic Constraint**     | DICON Constraints Module [15]        | dicc:Constraint [15]                    | Encapsulates variables evaluated across project lifecycle phases [15].      |

The regulatory ingestion module operates under specific requirements:

- The system shall decompose uploaded statutory texts into aec3po:Document and aec3po:DocumentSubdivision nodes linked via aec3po:hasPart [1].
- The system shall attach legislative metadata (eli:LegalResource, eli:passed_by, eli:first_date_entry_in_force) to each regulatory document node [10].
- The extraction pipeline shall parse regulatory clauses into structured RASE statements, instantiating Requirement, Applicability, Selection, and Exception components within the knowledge graph [10].
- The system shall classify regulatory mandates into ODRL deontic modalities (odrl:duty, odrl:permission, odrl:prohibition), preventing ambiguous rule interpretations [16].
- The system shall bind regulatory thresholds to target building entities via aec3po:hasFeatureOfInterest, linking rules directly to BOT and SAREF4BLDG classes [6].

## **Rule Execution, Validation Engine, and Reporting Architecture**

Once the design instance graph (BOT, SAREF4BLDG, BPO) and regulatory statements (AEC3PO, ODRL, DICON) are merged and enriched with dictionary URIs (bSDD, QUDT), compliance checking executes via declarative graph constraints [6]. W3C Shapes Constraint Language (SHACL) serves as the core execution engine, operationalizing the check methods defined in AEC3PO [18].

In this framework, each aec3po:Statement links to an executable aec3po:SHACLCheckMethod via aec3po:isOperationalizedBy [12]. The validation service loads both the building data graph and the regulatory shapes graph into an in-memory PyOxigraph store [20]. The execution engine validates the data graph against the active SHACL shapes [18].

For direct property evaluations—such as dimensional limits, material classifications, or element presence—standard SHACL core constraints (sh:minInclusive, sh:maxInclusive, sh:datatype, sh:hasValue) execute with minimal overhead [18]. For complex relational and spatial rules—such as egress travel distances, seismic displacement clearances (GC-001), or galvanic corrosion proximity (CC-001/MC-001)—the engine executes advanced sh:sparql constraint components [1].

Compliance Execution and Audit Architecture Flow: Unified PyOxigraph Knowledge Graphs (containing spatial topology, enriched bSDD/QUDT attributes, and AEC3PO SHACL regulatory shapes) are evaluated by the PySHACL In-Memory Graph Validator Core using core shapes and SPARQL constraints. The raw sh:ValidationReport output is transformed into aec3po:ComplianceVerificationReport instances mapping violations to specific elements and severities. These results are dispatched to BuildingSMART BCF endpoints (creating BCF topics with IFC GUIDs) and streamed via Server-Sent Events (SSE) to update the 3D viewer in real time.

When validation concludes, the engine translates the resulting sh:ValidationReport into an aec3po:ComplianceVerificationReport linked to an aec3po:CheckingAct instance [10]. Each detected non-conformance produces an aec3po:ValidationResult capturing the focus element, severity level, human-readable explanatory message, and target legal clause URI [10].

For every failure classified as a violation, the system automatically triggers issue generation via the /api/bcf router [1]. The router converts the validation result into a buildingSMART BCF (v2.1/v3.0) Topic [1]. The issue payload embeds the failing component's IFC GUID, viewpoint coordinates, and ISO 19650 metadata tags, ensuring issues can be exported back to design authoring tools [1]. Real-time audit metrics stream to the web client via Server-Sent Events (/api/events/{project_id}) [1].

The validation engine operates under specific functional criteria:

- The system shall link each aec3po:Statement to one or more aec3po:SHACLCheckMethod instances via aec3po:isOperationalizedBy [12].
- The execution core shall evaluate SHACL shapes against the unified knowledge graph using PySHACL backed by an in-memory PyOxigraph triplestore [18].
- The system shall support both SHACL Core constraint components and advanced sh:sparql constraints to execute complex spatial and physical compliance algorithms [18].
- The engine shall transform sh:ValidationReport data into aec3po:ComplianceVerificationReport structures detailing element focus nodes, severity classes, and legal citation URIs [10].
- The system shall convert compliance violations into BCF Topics containing valid IFC GUID selections, and stream real-time validation metrics to the frontend via Server-Sent Events [1].

## **Concrete Semantic Rule and Constraint Manifests**

To demonstrate how the system formalizes regulatory requirements into executable graph artifacts, this section provides concrete manifests for regulatory clauses and their operational SHACL shapes.

The first manifest encodes a building code egress requirement (NZBC Clause C2.2) concerning clear opening widths for emergency doors. The clause is decomposed into an aec3po:DocumentSubdivision, linked to official legislation via ELI, structured using AEC3PO statement classes, assigned a mandatory deontic duty via ODRL, and typed with QUDT measurement units.

```
@prefix aec3po: <https://w3id.org/lbd/aec3po/> .
@prefix eli: <http://data.europa.eu/eli/ontology#> .
@prefix odrl: <http://www.w3.org/ns/odrl/2/> .
@prefix bot: <https://w3id.org/bot#> .
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex: <https://bimguard.io/rules/> .

ex:NZBC_Clause_C2_2 a aec3po:DocumentSubdivision ;
 aec3po:hasPart ex:Statement_DoorClearWidth ;
 eli:LegalResource <https://www.building.govt.nz/eli/nzbc/c2-2> .

ex:Statement_DoorClearWidth a aec3po:NumericalCheckStatement, aec3po:RequirementStatement ;
 eli:title "Minimum Clear Width for Means of Egress Doors"@en ;
 aec3po:asText "Doors in an escape route must provide a clear opening width of not less than 850 mm."@en ;
 aec3po:hasFeatureOfInterest bot:Element ;
 aec3po:isOperationalizedBy ex:Shape_DoorClearWidth ;
 odrl:duty [
 a odrl:Duty ;
 odrl:action "verifyClearWidth" ;
 odrl:constraint [
odrl:leftOperand "doorClearOpeningWidth" ;
odrl:operator odrl:greaterThanOrEqual ;
odrl:rightOperand "850"^^xsd:decimal ;
qudt:hasUnit unit:MilliM
]
 ] .

ex:Shape_DoorClearWidth a aec3po:SHACLCheckMethod ;
 aec3po:asText "Operational SHACL shape asserting door clear opening width constraints." .
```

The second manifest illustrates the executable W3C SHACL shape that operationalizes the regulatory statement above. It targets building elements flagged on egress escape paths and checks clear opening widths against the prescriptive limit of 850 mm, raising a violation if a door falls below the threshold.

```
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix bot: <https://w3id.org/bot#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex: <https://bimguard.io/rules/> .

ex:DoorClearWidthValidationShape a sh:NodeShape ;
 sh:target [
a sh:SPARQLTarget ;
sh:select """
PREFIX bot: <https://w3id.org/bot#>
SELECT ?this
WHERE {
?this a bot:Element ;
<https://bimguard.io/props/isEgressPath> true .
}
"""
] ;
 sh:property [
sh:path <https://bimguard.io/props/clearOpeningWidth> ;
sh:datatype xsd:decimal ;
sh:minInclusive 850.0 ;
sh:message "NZBC Clause C2.2 Non-Compliance: Means of egress door clear width is less than 850 mm."@en ;
sh:severity sh:Violation ;
] .
```

The third manifest provides an advanced SHACL-SPARQL shape operationalizing the CC-001/MC-001 corrosion analysis engine. It evaluates the physical and topological proximity of connected MEP devices in SAREF4BLDG, calculating the anodic index potential differential between adjacent metallic components to detect galvanic corrosion risks where dielectric insulation is absent.

```
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix bot: <https://w3id.org/bot#> .
@prefix s4bldg: <https://saref.etsi.org/saref4bldg/> .
@prefix bpo: <https://w3id.org/bpo#> .
@prefix ex: <https://bimguard.io/rules/> .

ex:GalvanicCorrosionValidationShape a sh:NodeShape ;
 sh:targetClass s4bldg:DistributionDevice ;
 sh:sparql [
 a sh:SPARQLConstraint ;
 sh:message "CC-001 Violation: Direct connection between dissimilar metals (anodic potential delta > 0.25 V) without dielectric insulation in an exposed environment."@en ;
 sh:prefixes [
 sh:declare [ sh:prefix "s4bldg" ; sh:namespace "https://saref.etsi.org/saref4bldg/" ] ;
 sh:declare [ sh:prefix "bot" ; sh:namespace "https://w3id.org/bot#" ] ;
 sh:declare [ sh:prefix "bpo" ; sh:namespace "https://w3id.org/bpo#" ]
 ] ;
 sh:select """
 SELECT $this (?adjacentElement AS ?value)
 WHERE {
 $this bpo:hasMaterial ?matA ;
 bot:adjacentElement ?adjacentElement .
 ?adjacentElement a s4bldg:DistributionDevice ;
 bpo:hasMaterial ?matB .
 ?matA <https://bimguard.io/props/anodicPotential> ?potA .
 ?matB <https://bimguard.io/props/anodicPotential> ?potB .
 FILTER (ABS(?potA - ?potB) > 0.25)
 FILTER NOT EXISTS {
 $this <https://bimguard.io/props/hasDielectricIsolation> true .
 }
 }
 """
 ] .
```

## **System Interfaces and Data Flows**

Integrating semantic ontologies modifies the backend interface structure and internal communication channels of BIM-Guard [1]. The FastAPI application serves as the central orchestration gateway, exposing dedicated endpoints for model triplification, rule management, and query resolution [1].

The ingestion and validation lifecycle follows an ordered communication sequence:

> 1. A client initiates a model upload via POST /api/projects/{project_id}/models. The model is stored in Supabase object storage, and pre-flight validation checks STEP ISO 10303-21 compliance and schema validity [1].
> 2. The IFC-to-LBD triplification service parses the model into BOT, SAREF4BLDG, and BPO subgraphs, querying the bSDD cache to bind stable classification URIs and normal measurement units [6].
> 3. The regulatory service accepts rule packages via POST /api/rules/semantic/upload, storing AEC3PO statement graphs in the database [1].
> 4. The client triggers validation via POST /api/analyze/lbd/{project_id}. The orchestrator loads the merged graphs into an in-memory PyOxigraph store and invokes PySHACL [20].
> 5. Validation results stream incrementally to the frontend over Server-Sent Events (GET /api/events/{project_id}) [1]. Detected violations are converted into BCF topics accessible via GET /api/bcf/v2.1/projects/{project_id}/topics [1].
> 6. External systems or reporting tools can perform federated graph queries against the project knowledge graph via the SPARQL endpoint (POST /api/sparql/{project_id}) [20].

FastAPI Application Gateway Semantic Endpoints Summary: The gateway provides endpoints for rule ingesting (POST /api/rules/semantic/upload), running LBD constraint analysis (POST /api/analyze/lbd/{project_id}), querying graphs via SPARQL (POST /api/sparql/{project_id}), streaming real-time SSE events (GET /api/events/{project_id}), downloading openCDE-compliant Linked Data graphs (GET /api/cde/v1/projects/{project_id}/kg), and managing buildingSMART BCF topics for detected issues (GET /api/bcf/v2.1/projects/{project_id}/topics).

On the frontend, the Svelte 5 Single-Page Application incorporates these endpoints into the user workflow [1]. The Rule Library interface (frontend/src/routes/library/rules) allows auditors to view rules organized by RASE indicators (Requirement, Applicability, Selection, Exception tags) and inspect underlying SHACL shapes [1].

The 3D Viewer (frontend/src/routes/viewer) connects the ThatOpenCompany Web-IFC viewport with the PyOxigraph store [1]. When a user selects a component in the 3D model, the viewer queries the graph for its BOT spatial containment, SAREF4BLDG device properties, and attached bSDD classifications [6]. If the element has associated violations in the active aec3po:ComplianceVerificationReport, the viewer highlights the geometry and displays the explanatory violation message [1].

## **Non-Functional Requirements and System Quality Attributes**

Automated compliance checking across commercial building models involves datasets containing hundreds of thousands of geometric entities and relational properties [3]. The semantic architecture must maintain high performance, computational determinism, and data isolation to support enterprise adoption.

System Quality Attributes Summary: Key performance and quality requirements include triplification rates exceeding 15,000 triples/second, validation execution taking under 30 seconds for 100 SHACL rules on 500k triples, and a RAM ceiling of 2.5 GB per worker process. Reliability demands 100% reproducible validation reports, transparent fallback to local Supabase cache during bSDD network outages within 500 ms, and pre-flight STEP ISO 10303-21 verification. Security features include named graph tenant isolation and immutable write-locks on published compliance runs with SHA-256 integrity checksums.

### **Performance, Scalability, and Concurrency**

- The system shall convert IFC models into RDF graphs (BOT, SAREF4BLDG, BPO) at a sustained rate of ≥ 15,000 triples/second on standard infrastructure (8 vCPU, 16 GB RAM) [6]. Models up to 100 MB in STEP size must complete parsing and serialization within 60 seconds.
- The system shall evaluate a standard test suite of 100 SHACL shapes against a knowledge graph of up to 500,000 triples within 30 seconds using PyOxigraph and optimized SPARQL join indices [18].
- Peak memory utilization shall remain below 2.5 GB of RAM per worker process during graph validation. When a project graph exceeds 1,000,000 triples, the system shall spill graph operations from memory to persistent disk-backed Oxigraph storage instances [20].

### **Reliability, Determinism, and Fault Tolerance**

- Compliance validation must be completely deterministic. Repeated evaluations of identical SHACL shapes against the same model graph must produce identical aec3po:ComplianceVerificationReport results without state drift or ordering discrepancies [10].
- Outages, HTTP timeouts, or latency spikes in the external bSDD API must not disrupt active compliance checks [1]. The system must fall back to cached classifications in Supabase within 500 ms [1].
- The pre-flight validation gateway must verify incoming IFC models against STEP ISO 10303-21 syntax rules, check schema definitions (IFC2X3, IFC4, IFC4.3), and confirm spatial containment integrity before graph lifting begins [1]. Malformed models must fail gracefully with structured diagnostic logs [1].

### **Security, Multi-Tenancy, and Regulatory Integrity**

- In multi-tenant environments, project graphs must be partitioned using isolated Named Graph URIs (https://bimguard.io/graphs/{tenant_id}/{project_id}) enforced through Supabase Row-Level Security (RLS) policies [1]. Cross-tenant SPARQL queries must be rejected at the API gateway.
- Once a compliance verification report is promoted to the PUBLISHED state within the ISO 19650 workflow, its graph snapshot and associated BCF issues must become immutable via database write-locks and SHA-256 integrity checksums [1].
- | Metric ID  | Parameter                      | Nominal Operating Target  | Degradation Limit | Corrective System Action                               |
  | :--------- | :----------------------------- | :------------------------ | :---------------- | :----------------------------------------------------- |
  | **MTR-01** | Model Parsing & Triplification | ≤ 45 s per 100 MB IFC     | > 90 s            | Alerts worker monitor; initiates memory profiling.     |
  | **MTR-02** | SHACL Execution Rate           | ≥ 20 shapes/second        | < 5 shapes/second | Terminates lagging query; falls back to indexed joins. |
  | **MTR-03** | bSDD Cache Hit Ratio           | ≥ 90% for active domains  | < 70%             | Triggers background cache pre-fetching job.            |
  | **MTR-04** | SSE Event Stream Latency       | ≤ 100 ms per report batch | > 500 ms          | Batches outbound SSE events to reduce socket overhead. |
  | **MTR-05** | In-Memory Graph RAM            | ≤ 1.5 GB (50 MB model)    | > 2.5 GB          | Evicts completed graphs; spills triples to disk store. |

## **Verification, Traceability, and Acceptance Matrix**

To ensure system compliance against these specifications, all functional requirements must be tested through automated unit, integration, and performance verification suites.

| Requirement ID    | Specification Area        | Target Ontology or Standard                | Verification Method       | Acceptance Pass Criteria                                                                          |
| :---------------- | :------------------------ | :----------------------------------------- | :------------------------ | :------------------------------------------------------------------------------------------------ |
| **REQ-TOPO-001**  | Building Topology         | BOT (bot:Zone, bot:Element) [6]            | Automated Unit Test       | Generated graph parses with 100% valid Turtle syntax and zero unbound element nodes [6].          |
| **REQ-TOPO-002**  | Spatial Containment       | BOT Spatial Hierarchy [6]                  | Integration SPARQL Query  | SPARQL query returns matching topological hierarchy from root bot:Site to leaf bot:Space [6].     |
| **REQ-MEP-001**   | MEP Distribution          | SAREF4BLDG (s4bldg:DistributionDevice) [7] | Automated Unit Test       | 100% of IfcDistributionElement entities map to valid SAREF4BLDG subclasses [7].                   |
| **REQ-DICT-001**  | Classification Registry   | bSDD REST API Connector [11]               | Mocked Integration Test   | Correctly resolves classification JSON payloads and binds stable URI triples to elements [11].    |
| **REQ-DICT-004**  | Physical Quantities       | QUDT Units of Measure [10]                 | Unit Normalization Test   | Normalizes dimensional literals into standard SI units with valid qudt:Unit URIs [10].            |
| **REQ-REG-001**   | Statutory Structure       | AEC3PO Document Module [12]                | Graph Validation Test     | Regulatory document hierarchy parses into aec3po:Document and subdivisions [12].                  |
| **REQ-RASE-001**  | Regulatory Deconstruction | RASE Methodology [13]                      | Pipeline Benchmark Test   | Regulatory text parses into Requirement, Applicability, Selection, and Exception components [13]. |
| **REQ-DEON-001**  | Deontic Modalities        | ODRL (odrl:duty, odrl:prohibition) [16]    | Logical Inference Test    | Evaluates mandatory obligations and prohibitions correctly across varying test criteria [16].     |
| **REQ-SHACL-001** | Constraint Execution      | W3C SHACL Core [18]                        | SHACL Test Suite          | Detects non-compliant properties and generates conformant sh:ValidationReport graphs.             |
| **REQ-SHACL-005** | Complex Rule Logic        | SHACL-SPARQL Constraints [18]              | Engine GC-001/CC-001 Test | Evaluates multi-element spatial clashes and material galvanic potential deltas correctly [1].     |
| **REQ-REP-001**   | Compliance Reporting      | AEC3PO CheckingAct Module [10]             | End-to-End Pipeline Test  | Converts SHACL validation output into structured aec3po:ComplianceVerificationReport graphs [10]. |
| **REQ-REP-003**   | Interoperability Export   | buildingSMART BCF REST API [1]             | REST Endpoint Integration | Produces BCF topics containing valid viewpoints, IFC GUIDs, and ISO 19650 metadata tags [1].      |

## **Technical Synthesis**

Integrating these semantic ontologies provides the architectural foundation needed to advance BIM-Guard from an application reliant on hardcoded geometric scripts into a standards-based, verifiable automated compliance checking platform [1].

Adopting BOT, SAREF4BLDG, and BPO establishes a lightweight topological graph backbone that avoids the high memory overhead of full ifcOWL parsing while maintaining spatial and physical connectivity [4]. Harmonizing classifications through the buildingSMART Data Dictionary (bSDD) bridges authoring naming differences by anchoring attributes to international vocabularies and standardized QUDT physical units [10].

Formalizing regulations through AEC3PO, RASE, ODRL, and ELI structures statutory mandates into computable logic [10]. This structure allows the platform's natural language extraction pipeline to produce machine-verifiable rule graphs rather than unverified heuristic rules [1].

Executing these rules via W3C SHACL and SHACL-SPARQL creates a deterministic, open-standard validation engine capable of verifying architectural, structural, and material constraints [18]. The resulting compliance reports integrate with openCDE and BCF workflows, establishing an auditable automated compliance checking lifecycle aligned with ISO 19650 standards [1].

#### **Works cited**

> 1. maicen/bim-guard - GitHub, [https://github.com/maicen/bim-guard](https://github.com/maicen/bim-guard)
> 2. BIM, NLP, and AI for Automated Compliance Checking - NSF PAR, [https://par.nsf.gov/servlets/purl/10347911](https://par.nsf.gov/servlets/purl/10347911)
> 3. (PDF) Investigation of IFC file format for BIM based automated code, [https://www.researchgate.net/publication/342599057_Investigation_of_IFC_file_format_for_BIM_based_automated_code_compliance_checking](https://www.researchgate.net/publication/342599057_Investigation_of_IFC_file_format_for_BIM_based_automated_code_compliance_checking)
> 4. mep domain object classification through interdomain rule-based, [https://ec-3.org/wp-content/uploads/2025/10/EC32023_165.pdf](https://ec-3.org/wp-content/uploads/2025/10/EC32023_165.pdf)
> 5. Two Fundamental Questions Concerning BIM Data Representation, [https://itc.scix.net/pdfs/w78-2024-paper_25.pdf](https://itc.scix.net/pdfs/w78-2024-paper_25.pdf)
> 6. A Survey on Semantic Modeling for Building Energy Management, [https://arxiv.org/html/2404.11716v1](https://arxiv.org/html/2404.11716v1)
> 7. SAREF4BLDG: an extension of SAREF for the building domain, [https://saref.etsi.org/saref4bldg/](https://saref.etsi.org/saref4bldg/)
> 8. Extending the SAREF ontology for building devices and topology?, [https://ceur-ws.org/Vol-2159/02paper.pdf](https://ceur-ws.org/Vol-2159/02paper.pdf)
> 9. A Method to Unify Custom Properties in IFC to Linked Building Data, [https://ceur-ws.org/Vol-3824/short2.pdf](https://ceur-ws.org/Vol-3824/short2.pdf)
> 10. AEC3PO, [https://ci.mines-stetienne.fr/aec3po/](https://ci.mines-stetienne.fr/aec3po/)
> 11. bSDD intro - Slides, [https://slides.com/arturtomczak/bsdd-0992d5](https://slides.com/arturtomczak/bsdd-0992d5)
> 12. AEC3PO Ontology Documentation - ACCORD project, [https://accordproject.eu/aec3po/](https://accordproject.eu/aec3po/)
> 13. automated generation of sparql queries from semantic mark-up, [https://ec-3.org/wp-content/uploads/2025/10/EC32023_207.pdf](https://ec-3.org/wp-content/uploads/2025/10/EC32023_207.pdf)
> 14. How to Automate Building Information Modeling Rule Checking, [https://eureka.patsnap.com/report/how-to-automate-building-information-modeling-rule-checking](https://eureka.patsnap.com/report/how-to-automate-building-information-modeling-rule-checking)
> 15. Digital Construction Ontologies (DiCon), [https://digitalconstruction.github.io/v/0.5/](https://digitalconstruction.github.io/v/0.5/)
> 16. ODRL Policy Modelling and Compliance Checking - Semantic Scholar, [https://www.semanticscholar.org/paper/ODRL-Policy-Modelling-and-Compliance-Checking-Vos-Kirrane/68ef0a1d08ac6f801e0240968e57d5dc77d2904c](https://www.semanticscholar.org/paper/ODRL-Policy-Modelling-and-Compliance-Checking-Vos-Kirrane/68ef0a1d08ac6f801e0240968e57d5dc77d2904c)
> 17. Bridging DPV and ODRL for Legally-Oriented Usage Control in Data, [https://beatrizesteves.org/assets/documents/2026/SDS/dpv-odrl.pdf](https://beatrizesteves.org/assets/documents/2026/SDS/dpv-odrl.pdf)
> 18. AEC3PO: Check Method, [https://ci.mines-stetienne.fr/aec3po/check_method](https://ci.mines-stetienne.fr/aec3po/check_method)
> 19. OLIVAW: ACIMOV's GitHub robot assisting agile collaborative ... - arXiv, [https://arxiv.org/html/2510.17184v1](https://arxiv.org/html/2510.17184v1)
> 20. pyoxigraph 0.5.11 documentation, [https://pyoxigraph.readthedocs.io/](https://pyoxigraph.readthedocs.io/)
> 21. Converting Fire Safety Regulations to SHACL Shapes Using Natural, [https://ceur-ws.org/Vol-3874/paper7.pdf](https://ceur-ws.org/Vol-3874/paper7.pdf)
> 22. Temporally Qualified Building Elements: A DOLCE-Based Ontology, [https://www.mdpi.com/2227-7080/14/7/413](https://www.mdpi.com/2227-7080/14/7/413)
> 23. BIM-Based Automated Means-of-Egress Compliance Checking, [https://www.mdpi.com/2071-1050/18/16/8023](https://www.mdpi.com/2071-1050/18/16/8023)
> 24. SHACL is for LBD what mvdXML is for IFC - ResearchGate, [https://www.researchgate.net/publication/355425860_SHACL_is_for_LBD_what_mvdXML_is_for_IFC](https://www.researchgate.net/publication/355425860_SHACL_is_for_LBD_what_mvdXML_is_for_IFC)
> 25. Building ontology, [https://bimerr.iot.linkeddata.es/def/building/](https://bimerr.iot.linkeddata.es/def/building/)
> 26. dataModel.S4BLDG/Alarm/doc/spec.md at master · smart-data, [https://github.com/smart-data-models/dataModel.S4BLDG/blob/master/Alarm/doc/spec.md](https://github.com/smart-data-models/dataModel.S4BLDG/blob/master/Alarm/doc/spec.md)
> 27. bSDD API list class properties - buildingSMART Forums, [https://forums.buildingsmart.org/t/bsdd-api-list-class-properties/6114](https://forums.buildingsmart.org/t/bsdd-api-list-class-properties/6114)
> 28. FI3-CO2_Emission-AEC3PO.ttl - GitHub, [https://github.com/Accord-Project/aec3po/blob/main/examples/Finland/FI3-CO2_Emission-AEC3PO.ttl](https://github.com/Accord-Project/aec3po/blob/main/examples/Finland/FI3-CO2_Emission-AEC3PO.ttl)
> 29. Facilitating Knowledge Transfer during Code Compliance Checking, [https://ascelibrary.org/doi/10.1061/JCCEE5.CPENG-4884](https://ascelibrary.org/doi/10.1061/JCCEE5.CPENG-4884)
> 30. What Does ODRL Mean? A Cross-Level Ontological Grounding of, [https://publica.fraunhofer.de/bitstreams/74aee3aa-b4ff-4b4d-ac06-490fbe20c807/download](https://publica.fraunhofer.de/bitstreams/74aee3aa-b4ff-4b4d-ac06-490fbe20c807/download)
> 31. pyoxigraph · PyPI, [https://pypi.org/project/pyoxigraph/](https://pypi.org/project/pyoxigraph/)
> 32. SEMANTIC WEB BASED INTEGRATION BETWEEN BIM COST AND, [https://re.public.polimi.it/retrieve/ccca5104-fb33-4098-92b7-3a071091b551/SEMANTIC%20WEB%20BASED%20INTEGRATION%20BETWEEN%20BIM%20COST%20AND%20GEOMETRIC%20DOMAINS.pdf](https://re.public.polimi.it/retrieve/ccca5104-fb33-4098-92b7-3a071091b551/SEMANTIC%20WEB%20BASED%20INTEGRATION%20BETWEEN%20BIM%20COST%20AND%20GEOMETRIC%20DOMAINS.pdf)
