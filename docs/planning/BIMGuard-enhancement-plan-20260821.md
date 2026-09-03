# **BIMGuard: Architectural Analysis & Software Engineering Enhancement Report**

## **Executive Summary**

BIMGuard is an automated BIM quality and compliance platform that bridges natural-language engineering specifications (such as corrosion standards, material compatibility, and MEP guidelines) with Industry Foundation Classes (.ifc) models.  
An audit of the codebase (app/modules, app/components, app/engines, and app/routes) shows a working domain pipeline spanning:

> 1. **Document Parsing** (document_parsing & nlp_annotation)  
> 2. **IFC Parsing & Geometry/Topology Analysis** (ifc_reader)  
> 3. **Rule Generation** (rule_builder)  
> 4. **Compliance & Physics/Corrosion Engines** (comparator & app/engines)  
> 5. **BCF/Reporting Exporters** (reporter)

To make BIMGuard scalable, enterprise-grade, and openBIM-compliant, several core structural shifts are needed. The architectural roadmap below details enhancements across all requested areas.

+-------------------------------------------------------------------------------------------------------+  
|                                          BIMGUARD ARCHITECTURE                                        |  
+-------------------------------------------------------------------------------------------------------+  
|                                                                                                       |  
|  [ INGESTION LAYER ]                                                                                  |  
|    Spec PDFs / Docs  ----->  Docling / PyMuPDF  ----->  Hybrid NLP / LLM  ----->  buildingSMART IDS   |  
|                                                                                    & JSON Rulesets    |  
|                                                                                          |            |  
|  [ DOMAIN & EVALUATION CORE (SOLID / Hexagonal Architecture) ]                           |            |  
|    IFC Models (v2x3 / v4)  -->  IfcOpenShell / BVH Spatial Index                         |            |  
|                                         |                                                |            |  
|                                         +-------------> [ COMPLIANCE ENGINE ] <----------+            |  
|                                                               |                                       |  
|  [ DECOUPLED PIPELINES ]                                      |                                       |  
|               +-----------------------------------------------+-----------------------------------+   |  
|               |                                                                                   |   |  
|               v                                                                                   v   |  
|     (Pipeline A: Read-Only Audit)                                               (Pipeline B: Model    |  
|     - Rule Compliance Results                                                    Enhancement)         |  
|     - BCF 2.1/3.0 Topics & Cost/Schedule Impact                                 - Patch Missing Psets |  
|     - Compliance PDF/HTML Reports                                               - Material Normalizer |  
|                                                                                 - Versioned IFC Store |  
|                                                                                                       |  
|  [ PRESENTATION & CLIENT LAYER ]                                                                      |  
|     Decoupled UI (FastAPI + Modern Web Component Island / ThatOpenPlatform Web-IFC 3D Viewer)        |  
+-------------------------------------------------------------------------------------------------------+

## **1. SOLID Principles Architectural Overhaul**

### **Current Shortcomings in the Codebase**

* **Single Responsibility Principle (SRP):** Classes such as ComplianceOrchestrator, ifc_parser.py, and compliance_runner.py mix IFC geometry extraction, spatial traversal, rule filtering, issue tracking, and direct disk/Supabase persistence in single routines.  
* **Open/Closed Principle (OCP):** Adding a new engine (e.g., Fire Safety, Acoustic, or IDS-based checking) requires editing conditionals in orchestrator.py and compliance_runner.py rather than registering a new RuleEvaluator plugin.  
* **Liskov Substitution Principle (LSP):** Engines (bimguard_corrosion_engine.py, galvanic.py, bimguard_crevice_engine.py) share implicit duck-typing instead of adhering to a formalized abstract contract.  
* **Interface Segregation Principle (ISP):** Downstream reporting tools receive bloated dictionary payloads containing raw IFC entities, engine configs, and file descriptors.  
* **Dependency Inversion Principle (DIP):** High-level orchestrators directly instantiate lower-level services (like concrete Supabase clients, PyMuPDF extractors, and local file storage) instead of relying on domain repositories.

### **Recommended Target Architecture: Ports & Adapters (Hexagonal)**

Define explicit Domain Protocols (using Python's typing.Protocol or abc.ABC):

Python  
from typing import Protocol, List, Dict, Any  
from dataclasses import dataclass

@dataclass(frozen=True)  
class RuleExecutionContext:  
    ifc_model: Any  # ifcopenshell.file  
    spatial_index: Any  
    parameters: Dict[str, Any]

class IRuleEvaluator(Protocol):  
    """Open/Closed: New rule checkers implement this protocol."""  
    @property  
    def rule_type(self) -> str: ...  

    def evaluate(self, context: RuleExecutionContext) -> List["Issue"]: ...

class IModelStorage(Protocol):  
    """Dependency Inversion: Decouple from Supabase/Local S3."""  
    async def load_ifc(self, model_id: str) -> bytes: ...  
    async def save_ifc(self, model_id: str, content: bytes, version: int) -> str: ...

class IIssueSink(Protocol):  
    """Interface Segregation: Exporters only consume structured issues."""  
    def record_issues(self, run_id: str, issues: List["Issue"]) -> None: ...

#### **Refactoring Plan**

> 1. **Rule Engine Registry:** Replace hardcoded if/elif dispatchers with a central registry:  
>    Python  
>    class RuleEngineRegistry:  
>        _evaluators: Dict[str, IRuleEvaluator] = {}

>        @classmethod  
>        def register(cls, evaluator: IRuleEvaluator):  
>            cls._evaluators[evaluator.rule_type] = evaluator

>        @classmethod  
>        def get(cls, rule_type: str) -> IRuleEvaluator:  
>            return cls._evaluators[rule_type]

> 1. **Dependency Injection:** Inject IModelStorage, IIssueSink, and evaluators into ComplianceRunner through **init**, enabling simple unit testing with mock repositories.

## **2. Frontend & UI Modernization Strategy**

### **Current Limitations**

* The app uses server-rendered HTML (FastHTML / MonsterUI with HTMX snippets).  
* **The Problem:** 3D BIM rendering (Three.js / Web-IFC) requires an active WebGL/WebGPU context, client-side scene graphs, mesh picking, and camera manipulation. Server-side fragment swaps (hx-swap) risk resetting the 3D viewport canvas and struggle to provide responsive feedback when filtering through thousands of building elements.

### **Recommended Approaches**

| Strategy | Architecture | Pros | Cons | Best For |
| :---- | :---- | :---- | :---- | :---- |
| **Option A: Island Architecture (Recommended for FastHTML)** | FastHTML + Web Component Island (Vite + ThatOpenPlatform / @thatopen/components) | Retains Python-centric backend, minimal rewrite, isolates the 3D canvas from HTMX swaps | Requires a standard Custom-Event bridge between HTMX and the Web Component | Quickest performance boost with lowest rewrite cost |
| **Option B: Full Decoupling (SPA + API)** | Next.js / Vite React 19 + TypeScript + Shadcn UI + FastAPI backend | Maximum performance, client-side filtering, rich state handling for complex 3D BIM manipulation | Complete rewrite of the UI layer | Long-term enterprise multi-tenant SaaS |

### **Implementing the Island Architecture (Option A)**

> 1. **Encapsulate the BIM Viewer as a Custom Element (<bim-guard-viewer>):**  
>
   * Built with @thatopen/components (the successor to IFC.js) or three.js + web-ifc.  
* Compiled via Vite into a single bundle (/static/js/bim-viewer.js).  
>
> 1. **Coordinate with Server State via Custom Events:**  
>    HTML  
>    <!-- FastHTML View Component -->  
>    <div id="workspace-container" class="grid grid-cols-12 gap-4">  
>      <div class="col-span-8 h-[750px] relative">  
>        <!-- 3D Island -->  
>        <bim-guard-viewer
>          id="main-viewer"  
>          model-url="/api/projects/123/model/file"  
>          enhanced-url="/api/projects/123/model/enhanced-file">  
>        </bim-guard-viewer>  
>      </div>  
>      <div class="col-span-4"
>           hx-get="/api/issues/123"
>           hx-trigger="issue-selected from:body"
>           hx-target="#issue-inspector">  
>        <!-- HTMX Server Rendered Properties Panel -->  
>        <div id="issue-inspector">Select an issue or 3D element...</div>  
>      </div>  
>    </div>

> 1. **Add Web Workers for Background Processing:** Run .ifc parsing, mesh extraction, and bounding-box calculations inside browser Web Workers to keep UI interaction smooth at 60 FPS.

## **3. Documentation & Instruction Standards**

### **Current State**

Instructions are spread across .github/instructions/, .github/copilot-instructions.md, CLAUDE.md, and skills directories.

### **Recommendations**

docs/  
├── adr/                        # Architecture Decision Records  
│   ├── 0001-hexagonal-architecture.md  
│   ├── 0002-buildingsmart-ids-integration.md  
│   └── 0003-split-audit-and-enhancement.md  
├── api/                        # OpenAPI specifications & endpoints  
├── architecture/               # System diagrams, data flowcharts  
│   ├── pipeline_flow.md  
│   └── domain_models.md  
├── engines/                    # Developer guides for adding custom rules  
│   └── writing_a_custom_engine.md  
└── specs/                      # openBIM specifications & schemas

#### **Actionable Improvements**

> 1. **Adopt Architecture Decision Records (ADRs):** Document architectural choices (e.g., choosing Docling over unstructured parsers, moving to IDS, separating analysis from enhancement) using the MADR template.  
> 2. **Consolidate Agent/Copilot Instructions:** Combine root guidelines into a unified .github/copilot-instructions.md and AGENTS.md containing:  
>
   * **Domain Invariants:** Units must remain standardized in SI ($mm$, $m$, $m/s$, $^circ C$) before rule execution.  
* **Typing Policy:** Strict Pydantic v2 schemas for all payloads across domain boundaries.  
* **Error Handling:** Domain-specific exceptions (IfcGeometryMissingError, RuleSyntaxError, ModelEnhancementConflictError).  
>
> 1. **Automated Documentation Engine:** Deploy MkDocs-Material with mkdocstrings-python to automatically generate documentation from Python type hints and docstrings during CI/CD.

## **4. BuildingSmart IDS (Information Delivery Specification) Integration**

### **What is IDS and Why Does BIMGuard Need It?**

The buildingSMART **Information Delivery Specification (IDS)** is the global standard (XML/JSON based) for defining computer-interpretable exchange requirements for BIM models. It governs:

* Applicability (which elements the rule applies to: e.g., IfcPipeSegment, IfcValve).  
* Requirements (attributes, property sets, material names, classifications, and part-of relationships).

   Natural Language Engineering Spec (PDF)  
                      │  
                      ▼  
   [ Module 1 & 1b: NLP + LLM Extraction ]  
                      │  
                      ▼  
       [ IDS Rule Generator (Module 3) ]  
                      │  
            ┌─────────┴─────────┐  
            ▼                   ▼  
    Standard IDS XML     Custom Physics / Topology Rules  
   (Alphanumeric &       (Proximity, Crevice, Galvanic Paths)  
    Pset Validation)            │  
            │                   │  
            ▼                   ▼  
   [ ifcopenshell.ids ]  [ BIMGuard Corrosion Engines ]  
            │                   │  
            └─────────┬─────────┘  
                      ▼  
             Unified Issue Log

### **Applicability Assessment: High Priority Fit**

| Current BIMGuard Custom Rule Structure | buildingSMART IDS Standard Equivalent |
| :---- | :---- |
| target_entity: "IfcPipeSegment" | <ids:applicability><ids:entity><ids:name>IFCPIPESEGMENT</ids:name></ids:entity></ids:applicability> |
| required_property: "CorrosionAllowance" in Pset_PipeSegmentPHistory | <ids:property dataType="IFCLENGTHMEASURE"><ids:propertySet>Pset_PipeSegmentPHistory</ids:propertySet><ids:name>CorrosionAllowance</ids:name></ids:property> |
| prohibited_materials: ["Carbon Steel"] when media is seawater | <ids:material><ids:value><ids:simpleValue>Carbon Steel</ids:simpleValue></ids:value></ids:material> |

### **Implementation Blueprint**

> 1. **Incorporate ifcopenshell.ids:** Use the built-in IDS engine in IfcOpenShell instead of writing custom AST checkers for alphanumeric property verification.  
> 2. **Extend the Rule Converter (rule_builder):** Add an IDSRuleExporter that outputs valid .ids files from extracted NLP specifications.  
> 3. **Maintain a Hybrid Engine Approach:**  
>
   * **Layer 1 (Standard IDS):** Use ifcopenshell.ids for checking entity names, predefined types, property sets, and material names.  
* **Layer 2 (BIMGuard Physics Extensions):** Use BIMGuard's domain engines for geometric calculations that standard IDS cannot check (e.g., galvanic direct-contact topology, electrolyte path continuity, fluid velocity turbulence).  
>
> 1. **Export .ids Files:** Allow users to export extracted specifications as standard .ids files for use in third-party tools like Solibri, BlenderBIM, or Autodesk Construction Cloud.

## **5. Improving the Rules Extraction Workflow**

### **Current Bottlenecks**

* The current pipeline relies on a chain of Regex, keyword heuristics, and basic tokenizers (nlp_annotation/deontic_extractor.py, condition_parser.py, regex_rule_converter.py).  
* Brittle regex patterns frequently break when parsing complex sentence structures, engineering footnotes, multi-column tables, or conditional clauses (e.g., *"Unless protected by sacrificial anodes, carbon steel shall not be within 50mm of 316 stainless steel in submerged zones"*).

### **Recommended Modernization Architecture**

PDF / Spec Document  
       │  
       ▼  
 [ Docling / LayoutLMv3 Document Decomposition ]  
       │  (Extracts clean Markdown + structured HTML tables)  
       ▼  
 [ Context Chunker & Cross-Reference Resolver ]  
       │  (Preserves parent section headings & table captions)  
       ▼  
 [ LLM Structured Extraction (DSPy / Instructor + Pydantic v2) ]  
       │  (Few-shot domain prompts for Deontic, Physical, & Geometric rules)  
       ▼  
 [ Human-in-the-Loop (HITL) Verification UI ]  
       │  (Engineer approves/edits extracted bounds & properties)  
       ▼  
 [ Rule Store / Vector Index ]

### **Key Workflow Enhancements**

> 1. **Schema-Constrained LLM Extraction:** Use Instructor or OpenAI/Anthropic Structured Outputs with strict Pydantic schemas instead of regex parsing:  
>    Python  
>    from pydantic import BaseModel, Field  
>    from typing import List, Literal, Optional

> class ExtractedCorrosionRule(BaseModel):  
> rule_id: str  
> source_clause: str  
> deontic_modality: Literal["SHALL", "SHOULD", "MUST", "PROHIBITED"]  
> target_ifc_entities: List[str] = Field(description="e.g. ['IfcPipeSegment', 'IfcFitting']")  
> primary_material: str  
> environment_condition: str  
> geometric_clearance_mm: Optional[float]  
> required_psets: List[Dict[str, str]]

> 1. **Human-In-The-Loop (HITL) Rule Curation:**  
>
   * Provide an interactive UI (app/components/rule_extraction_ui.py) where engineers can inspect the PDF text snippet side-by-side with the generated rule, verify tolerance values, and approve rules before committing them to the project database.  
>
> 1. **Standardized Seed Catalogues:** Transition hardcoded seed scripts (code_seed_rules.py, code_extended_rules.py) into versioned, schema-validated JSON/YAML repository files loaded at startup.

## **6. Separating Analysis from Model Enhancement**

### **Current Coupling Problem**

In the current setup, analyze.py, compliance_runner.py, and ifc_quality/improver.py run audit checks and model alterations (such as injecting missing Property Sets or adjusting metadata) within the same process. This makes it difficult to audit changes, complicates rollback, and risks unintended modifications to the original IFC file.

### **Proposed Architecture: Two Independent Pipelines**

                             [ Raw Input IFC File ]  
                                        │  
                                        ▼  
                        [ Storage: S3 / Supabase Bucket ]  
                                        │  
                 ┌──────────────────────┴──────────────────────┐  
                 ▼                                             ▼  
     [ Pipeline 1: Audit Service ]                [ Pipeline 2: Enhancement Service ]  
     - Read-only, pure analysis                   - Explicit, user-triggered workflow  
     - Evaluates IDS + Physics rules              - Resolves patchable metadata  
     - Generates BCF + Issue Logs                 - Executes geometry/material fixes  
                 │                                             │  
                 ▼                                             ▼  
     [ Immutable Compliance Report ]              [ Enhanced IFC Model (v2) ]  
     - BCF 2.1/3.0 XML zip                        - Stored in /models/enhanced/  
     - Cost & Schedule Impact Analysis            - Lineage record in Postgres database

### **Implementation Details**

> 1. **Make the Compliance Pipeline Read-Only:**  
>
   * run_compliance_analysis(ifc_file_path, ruleset_id) must treat the IFC file as an immutable input.  
* Outputs: An immutable AnalysisRunResult containing issues, severity scores, BCF topics, and schedule/cost estimates.  
>
> 1. **Make the Model Enhancement Pipeline an Explicit, Tracked Operation:**  
>
   * enhance_model(ifc_file_path, approved_fixes) creates a new IFC file with an incremented version number without modifying the original source model.  
* Maintains complete data provenance using a database ledger:  
     SQL  
     CREATE TABLE model_lineage (  
         id UUID PRIMARY KEY,  
         project_id UUID REFERENCES projects(id),  
         parent_model_id UUID,  
         version INT NOT NULL,  
         file_path TEXT NOT NULL,  
         applied_enhancements JSONB NOT NULL,  
         created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()  
     );

> 1. **Side-by-Side Model Comparison in the Viewer:**  
>
   * Both the original and enhanced IFC files remain accessible through unique storage URLs, allowing the viewer to display visual diffs (e.g., highlighting patched properties in green and missing data in red).

## **7. Additional System-Wide Recommendations**

### **High-Impact Enhancements**

#### **A. Asynchronous Task Processing & Real-Time Events**

* **Problem:** Parsing large IFC files (100MB+) and evaluating complex spatial queries blocks the main web server thread.  
* **Solution:** Introduce an asynchronous task queue (**Celery** or **ARQ** with Redis). The web router enqueues jobs and yields a job_id. The client receives real-time progress updates via Server-Sent Events (SSE) or WebSockets (/api/projects/{id}/analysis-progress).

HTTP POST /analyze ──> [ FastAPI Route ] ──> Enqueue Job (Redis) ──> Return 202 Accepted {job_id}  
                                                                            │  
   [ FastHTML Client / UI ] <── SSE Stream (/events/{job_id}) <── [ Background Worker Task ]

#### **B. Spatial Query Optimization (BVH / R-Tree Indexing)**

* **Problem:** Physics and corrosion checks (like Galvanic distance and Crevice detection) run pairwise comparison loops ($O(N^2)$), causing significant slowdowns on large MEP models.  
* **Solution:** Build a Bounding Volume Hierarchy (BVH) or use an R-Tree index (via trimesh or scipy.spatial.cKDTree) on element centroids/bounding boxes to reduce proximity detection to $O(N log N)$.

#### **C. Native BCF 3.0 API Server Integration**

* **Enhancement:** Expand app/services/bcf_exporter.py beyond basic file downloads to support the buildingSMART **BCF REST API (v3.0)**. This allows native, bi-directional issue syncing with Solibri, Autodesk Construction Cloud (Revit), and BIMcollab directly from BIMGuard.

#### **D. Comprehensive Testing & Continuous Benchmarking**

* Expand app/modules/tests/eval_harness.py into a fully automated CI test suite containing:  
  * **Golden Model Regression Tests:** A test suite of synthetic, intentionally flawed IFC files (testing galvanic couples, missing Psets, and invalid pipe slopes) verified against baseline BCF logs.  
  * **Extraction F1 Benchmarks:** Automated tests evaluating NLP/LLM rule extraction accuracy against verified PDF specification datasets.

## **8. Implementation Roadmap**

+-------------------------------------------------------------------------------------------------------+  
| PHASE 1: CORE REFACTORING & DECOUPLING                                                                |  
| - Introduce Domain Protocols (IRuleEvaluator, IModelStorage, IIssueSink).                             |  
| - Separate the Compliance Pipeline from the Model Enhancement Pipeline.                              |  
| - Implement versioned model storage with a database lineage table.                                   |  
+-------------------------------------------------------------------------------------------------------+  
                                                   │  
                                                   ▼  
+-------------------------------------------------------------------------------------------------------+  
| PHASE 2: openBIM STANDARDS INTEGRATION (IDS & BCF)                                                    |  
| - Integrate ifcopenshell.ids into Module 4 for native alphanumeric and Pset validation.              |  
| - Build an IDS XML/JSON export engine in Module 3.                                                    |  
| - Upgrade BCF generation to support BCF 3.0 API syncing.                                              |  
+-------------------------------------------------------------------------------------------------------+  
                                                   │  
                                                   ▼  
+-------------------------------------------------------------------------------------------------------+  
| PHASE 3: EXTRACTION PIPELINE & UI PERFORMANCE                                                         |  
| - Replace brittle regex extractors with structured, schema-constrained LLM parsing (Pydantic v2).     |  
| - Build a Web Component Island for the 3D Viewer (ThatOpenPlatform / Three.js).                       |  
| - Implement background task workers with Server-Sent Events (SSE) for progress streaming.             |  
+-------------------------------------------------------------------------------------------------------+  
                                                   │  
                                                   ▼  
+-------------------------------------------------------------------------------------------------------+  
| PHASE 4: SCALING & OBSERVABILITY                                                                      |  
| - Add BVH/R-Tree spatial indexing for high-speed MEP proximity checks.                               |  
| - Standardize architecture documentation with MkDocs and Architecture Decision Records (ADRs).        |  
| - Automate CI evaluation suites against gold-standard IFC test datasets.                              |  
+-------------------------------------------------------------------------------------------------------+

### **Suggested Next Steps**

To begin implementing these improvements, we can focus first on either of the following foundations:

> 1. **Refactor Phase 1:** Decouple ComplianceRunner and create the IRuleEvaluator registry alongside the two separate analysis/enhancement pipelines.  
> 2. **Build the IDS Module (Phase 2):** Create the ifcopenshell.ids validation adapter and connect it directly to the rule builder.

Which area would you like to prioritize first?
