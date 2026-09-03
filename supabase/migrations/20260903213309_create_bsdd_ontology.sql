-- Migration: create_bsdd_ontology
-- Description: Local knowledge graph of buildingSMART Data Dictionary (bSDD)
-- classes, properties, and the class-property relationships between them --
-- seeded by scripts/crawl_bsdd_ontology.py from a curated branch of the IFC
-- 4.3 hierarchy (the classes this app's rules actually target, plus their
-- ancestors and descendants). Powers offline/instant bSDD hover cards,
-- resolving bSDD's `[[Term]]` cross-reference markup to real links, property
-- suggestions when authoring rules, and grounding the rule extraction engine
-- against real bSDD vocabulary -- all without a live bSDD API round trip.
--
-- No foreign keys between the three tables: the crawler inserts classes and
-- properties in discovery order, not topological order (a class's parent or
-- a property's other classes may not exist yet when a row is written), and
-- this is a cache of an external system, not data this app's own writes need
-- to stay referentially consistent with. Soft references, indexed for lookups.

CREATE TABLE IF NOT EXISTS public.bsdd_classes (
    uri TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    dictionary_uri TEXT NOT NULL,
    class_type TEXT NOT NULL DEFAULT 'Class',
    parent_class_uri TEXT,
    definition TEXT,
    description TEXT,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bsdd_classes_parent ON public.bsdd_classes (parent_class_uri);
CREATE INDEX IF NOT EXISTS idx_bsdd_classes_code ON public.bsdd_classes (code);

CREATE TABLE IF NOT EXISTS public.bsdd_properties (
    uri TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    data_type TEXT,
    definition TEXT,
    description TEXT,
    units JSONB NOT NULL DEFAULT '[]'::jsonb,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bsdd_properties_code ON public.bsdd_properties (code);

-- The graph's edges: which properties a class carries, and the per-class
-- specifics of that relation (a property's pset, allowed values, or type can
-- be narrowed per class -- see ClassPropertyContract in the bSDD OpenAPI spec).
CREATE TABLE IF NOT EXISTS public.bsdd_class_properties (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    class_uri TEXT NOT NULL,
    property_uri TEXT NOT NULL,
    property_set TEXT,
    data_type TEXT,
    units JSONB NOT NULL DEFAULT '[]'::jsonb,
    allowed_values JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_required BOOLEAN,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (class_uri, property_uri, property_set)
);

CREATE INDEX IF NOT EXISTS idx_bsdd_class_properties_class ON public.bsdd_class_properties (class_uri);
CREATE INDEX IF NOT EXISTS idx_bsdd_class_properties_property ON public.bsdd_class_properties (property_uri);

-- The app uses the service-role key, which bypasses RLS; enabling it denies
-- anon/authenticated clients by default (matches unstructured_instances).
ALTER TABLE public.bsdd_classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bsdd_properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bsdd_class_properties ENABLE ROW LEVEL SECURITY;
