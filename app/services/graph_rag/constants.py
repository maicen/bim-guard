"""Constants, prompts, and domain mappings for Graph-RAG services."""

# Common architectural IFC types mapped to synonyms in user questions
_IFC_KEYWORD_MAP: dict[str, str] = {
    "door": "IfcDoor",
    "doors": "IfcDoor",
    "exit": "IfcDoor",
    "exits": "IfcDoor",
    "wall": "IfcWall",
    "walls": "IfcWall",
    "partition": "IfcWall",
    "partitions": "IfcWall",
    "space": "IfcSpace",
    "spaces": "IfcSpace",
    "room": "IfcSpace",
    "rooms": "IfcSpace",
    "corridor": "IfcSpace",
    "corridors": "IfcSpace",
    "stair": "IfcStair",
    "stairs": "IfcStair",
    "stairway": "IfcStair",
    "stairways": "IfcStair",
    "window": "IfcWindow",
    "windows": "IfcWindow",
    "column": "IfcColumn",
    "columns": "IfcColumn",
    "beam": "IfcBeam",
    "beams": "IfcBeam",
    "slab": "IfcSlab",
    "slabs": "IfcSlab",
    "roof": "IfcRoof",
    "roofs": "IfcRoof",
    "railing": "IfcRailing",
    "railings": "IfcRailing",
    "floor": "IfcBuildingStorey",
    "floors": "IfcBuildingStorey",
    "storey": "IfcBuildingStorey",
    "storeys": "IfcBuildingStorey",
    "story": "IfcBuildingStorey",
    "stories": "IfcBuildingStorey",
    "level": "IfcBuildingStorey",
    "levels": "IfcBuildingStorey",
    "element": "IfcProduct",
    "elements": "IfcProduct",
    "product": "IfcProduct",
    "products": "IfcProduct",
}

# Thematic domain keywords for LightRAG high-level abstract query routing
_THEME_KEYWORDS: dict[str, list[str]] = {
    "egress": ["egress", "exit", "evacuation", "travel distance", "corridor", "aisle", "escape", "means of egress"],
    "fire_protection": ["fire", "smoke", "rating", "barrier", "partition", "sprinkler", "compartment"],
    "accessibility": ["accessible", "ada", "wheelchair", "clearance", "clear width", "grab bar", "ramp", "threshold"],
    "spatial": ["area", "volume", "height", "width", "dimension", "occupant load", "capacity", "containment"],
    "structural": ["load", "bearing", "column", "beam", "slab", "foundation"],
}

# Generic hub stop-entities excluded or penalized during multi-hop graph expansion
_STOP_ENTITIES: set[str] = {
    "ifcproject",
    "ifcsite",
    "ifcbuilding",
    "project",
    "building",
    "model",
}

# Stopwords for document search to prevent generic question tokens from matching arbitrary clauses
_DOC_QUERY_STOPWORDS: set[str] = {
    "what", "are", "the", "for", "and", "our", "all", "with", "from", "how", "many",
    "this", "that", "these", "those", "project", "projects", "model", "models",
    "tell", "about", "there", "have", "has", "does", "show", "list", "count", "number",
    "much", "can", "you", "please", "exist", "which", "who", "where", "when", "why",
    "give", "get", "find", "describe", "summary", "overview", "total", "item", "items",
    "we", "us", "in", "on", "at", "to", "of", "an", "a", "is",
}

_RAG_SYSTEM_PROMPT = """You are BIM-Guard Graph-RAG Assistant, an expert openBIM architectural compliance and engineering specification assistant.
Your goal is to answer questions strictly grounded in:
1. Document specifications and regulatory requirements extracted from project documents.
2. The project's IFC BIM model graph and model inventory (attached models, elements, spatial containment, properties, fire ratings).
3. The relationship between document provisions and modeled elements.

GUIDELINES:
- Always be accurate, clear, and direct.
- Ground your statements in the retrieved context.
- STAY RELEVANT: Only reference and cite sources that directly answer the user's specific question. If retrieved document provisions or model facts are unrelated to the user's inquiry (for example, general code clauses when the user asked about project models or project metadata), ignore them and do NOT cite or summarize them.
- When asked about model inventory, file names, or model counts, state the exact number of attached models and list their names, roles, and statuses directly.
- Use inline citations: [Doc: <Section/Clause>, p. <Page>] for document references, and [IFC: <Model/Element Name> | ID/GUID: <ID/GUID>] for model entities.
- When answering hybrid compliance questions, explicitly compare the document requirement against the model facts and state whether elements comply or deviate.
- If information is not in the context, state that clearly rather than inventing numbers or GUIDs.
- Conclude with a helpful summary table or bulleted list where relevant.
"""
