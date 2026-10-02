-- Baseline schema squash.
--
-- Replaces the 107 migrations archived in supabase/migrations_archive/
-- (20260721135500 .. 20260929034128) with a single snapshot of the
-- public schema as it exists in production as of 2026-10-02.
--
-- Generated via: docker exec supabase-db pg_dump -U postgres -d postgres
--   --schema-only --schema=public --no-owner --no-privileges --no-tablespaces
-- Verified to reproduce an identical public schema (47/47 tables) in an
-- isolated scratch database before being committed.
--
-- Reference/seed data inserted by some archived migrations (default
-- app_settings, static_data_assets, role_permissions, rule_folders
-- categories) and real-organization bootstrap data (org invites,
-- superadmin flag) were intentionally NOT carried into this baseline --
-- the former belongs in supabase/seed.sql for fresh/local environments,
-- the latter is production-specific and already present on the live DB.

--
-- PostgreSQL database dump
--


-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA IF NOT EXISTS public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: allocate_model_enhancement_version(bigint); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.allocate_model_enhancement_version(target_project_id bigint) RETURNS bigint
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO ''
    AS $$
declare
	allocated_version bigint;
begin
	insert into public.model_enhancement_version_counters (project_id, next_version)
	values (
		target_project_id,
		(
			select coalesce(max(lineage.version), 0) + 2
			from public.model_enhancement_lineage as lineage
			where lineage.project_id = target_project_id
		)
	)
	on conflict (project_id) do update
	set next_version = public.model_enhancement_version_counters.next_version + 1
	returning next_version - 1 into allocated_version;

	return allocated_version;
end;
$$;


--
-- Name: default_organization_id(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.default_organization_id() RETURNS bigint
    LANGUAGE sql STABLE
    SET search_path TO 'public'
    AS $$
	select id from public.organizations where slug = 'default' limit 1;
$$;


--
-- Name: prevent_published_cde_mutation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_published_cde_mutation() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'public'
    AS $$
BEGIN
    IF OLD.cde_state IN ('PUBLISHED', 'ARCHIVED') THEN
        -- Allow state transition from PUBLISHED/ARCHIVED if explicitly archiving or updating state,
        -- but block payload/attribute mutations on finalized records.
        IF NEW.cde_state = OLD.cde_state AND (
            NEW.name IS DISTINCT FROM OLD.name OR
            NEW.ifc_file_path IS DISTINCT FROM OLD.ifc_file_path OR
            NEW.revision_code IS DISTINCT FROM OLD.revision_code
        ) THEN
            RAISE EXCEPTION 'Cannot modify % project record in state %', OLD.id, OLD.cde_state;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: prevent_published_cde_mutation_generic(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_published_cde_mutation_generic() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'public'
    AS $$
DECLARE
    old_row jsonb;
    new_row jsonb;
BEGIN
    IF OLD.cde_state IN ('PUBLISHED', 'ARCHIVED') AND NEW.cde_state = OLD.cde_state THEN
        old_row := to_jsonb(OLD) - 'updated_at' - 'cde_approved_by' - 'cde_approved_at';
        new_row := to_jsonb(NEW) - 'updated_at' - 'cde_approved_by' - 'cde_approved_at';
        IF old_row IS DISTINCT FROM new_row THEN
            RAISE EXCEPTION 'Cannot modify record % in state %', OLD.id, OLD.cde_state;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;


SET default_table_access_method = heap;

--
-- Name: app_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_settings (
    key text NOT NULL,
    value text DEFAULT ''::text NOT NULL,
    value_type text DEFAULT 'string'::text NOT NULL,
    scope text DEFAULT 'runtime'::text NOT NULL,
    is_secret integer DEFAULT 0 NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    updated_at text DEFAULT ''::text NOT NULL
);


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id bigint NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    actor_id text NOT NULL,
    actor_email text,
    organization_id bigint,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.audit_log ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: bcf_comments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bcf_comments (
    guid text NOT NULL,
    topic_guid text NOT NULL,
    comment_date text DEFAULT ''::text NOT NULL,
    author text DEFAULT ''::text NOT NULL,
    comment text DEFAULT ''::text NOT NULL,
    modified_date text,
    modified_author text,
    viewpoint_guid text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: bcf_topics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bcf_topics (
    guid text NOT NULL,
    project_id text NOT NULL,
    topic_type text DEFAULT 'Issue'::text NOT NULL,
    topic_status text DEFAULT 'Open'::text NOT NULL,
    title text DEFAULT ''::text NOT NULL,
    priority text DEFAULT 'Normal'::text NOT NULL,
    topic_index integer DEFAULT 1 NOT NULL,
    creation_date text DEFAULT ''::text NOT NULL,
    creation_author text DEFAULT ''::text NOT NULL,
    modified_date text,
    modified_author text,
    assigned_to text,
    description text,
    due_date text,
    labels jsonb DEFAULT '[]'::jsonb NOT NULL,
    stage text,
    component_guids jsonb DEFAULT '[]'::jsonb NOT NULL,
    project_code text,
    originator text,
    suitability_code text,
    revision_code text,
    cde_state text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: bcf_viewpoints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bcf_viewpoints (
    guid text NOT NULL,
    topic_guid text NOT NULL,
    viewpoint_index integer DEFAULT 0 NOT NULL,
    perspective_camera jsonb,
    orthogonal_camera jsonb,
    lines jsonb DEFAULT '[]'::jsonb NOT NULL,
    clipping_planes jsonb DEFAULT '[]'::jsonb NOT NULL,
    components jsonb DEFAULT '{}'::jsonb NOT NULL,
    snapshot_base64 text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: chat_conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_conversations (
    id text DEFAULT (gen_random_uuid())::text NOT NULL,
    project_id bigint NOT NULL,
    user_id uuid,
    title text DEFAULT 'New Conversation'::text NOT NULL,
    scope text DEFAULT 'hybrid'::text NOT NULL,
    document_id bigint,
    element_class text,
    is_pinned boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: chat_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_messages (
    id text NOT NULL,
    conversation_id text NOT NULL,
    role text NOT NULL,
    content text DEFAULT ''::text NOT NULL,
    citations jsonb DEFAULT '[]'::jsonb NOT NULL,
    reasoning_steps jsonb DEFAULT '[]'::jsonb NOT NULL,
    tool_calls jsonb DEFAULT '[]'::jsonb NOT NULL,
    cypher_queries jsonb DEFAULT '[]'::jsonb NOT NULL,
    "timestamp" text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chat_messages_role_check CHECK ((role = ANY (ARRAY['user'::text, 'assistant'::text, 'system'::text])))
);


--
-- Name: client_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.client_documents (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    filename text NOT NULL,
    file_path text NOT NULL,
    file_type text,
    category text NOT NULL,
    description text,
    tags text,
    upload_date timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT client_documents_category_check CHECK ((category = ANY (ARRAY['Specification'::text, 'Code'::text, 'Manual'::text, 'Standard'::text, 'Drawing'::text, 'Schedule'::text, 'O&M Manual'::text, 'Warranty'::text, 'Assessment'::text, 'Report'::text, 'RFI Log'::text, 'Other'::text])))
);


--
-- Name: TABLE client_documents; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.client_documents IS 'Client-uploaded project documents (specs, schedules, O&M, assessments) used as analysis evidence';


--
-- Name: COLUMN client_documents.project_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.client_documents.project_id IS 'Foreign key to public.projects.id (BIGINT)';


--
-- Name: COLUMN client_documents.filename; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.client_documents.filename IS 'Original filename of uploaded document';


--
-- Name: COLUMN client_documents.file_path; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.client_documents.file_path IS 'Object key in Supabase Storage';


--
-- Name: COLUMN client_documents.file_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.client_documents.file_type IS 'File MIME type or extension';


--
-- Name: COLUMN client_documents.category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.client_documents.category IS 'Specification, Schedule, Drawing, O&M Manual, Warranty, Assessment, RFI Log, or Other';


--
-- Name: COLUMN client_documents.description; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.client_documents.description IS 'User-provided description';


--
-- Name: COLUMN client_documents.tags; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.client_documents.tags IS 'Comma-separated searchable tags';


--
-- Name: client_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.client_documents ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.client_documents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: document_nodes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_nodes (
    id bigint NOT NULL,
    document_id bigint NOT NULL,
    node_id text NOT NULL,
    text text NOT NULL,
    clause_id text,
    page_number integer,
    parent_section text,
    section_path jsonb DEFAULT '[]'::jsonb NOT NULL,
    node_type text DEFAULT 'paragraph'::text NOT NULL,
    deontic_statements jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    bbox jsonb,
    CONSTRAINT document_nodes_node_type_check CHECK ((node_type = ANY (ARRAY['paragraph'::text, 'table'::text, 'list'::text, 'heading'::text])))
);


--
-- Name: TABLE document_nodes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.document_nodes IS 'LlamaIndex-ingested, clause-annotated document nodes carrying provenance for BCF/rule traceability';


--
-- Name: COLUMN document_nodes.document_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.document_nodes.document_id IS 'Foreign key to public.documents.id';


--
-- Name: COLUMN document_nodes.node_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.document_nodes.node_id IS 'LlamaIndexIngestor-assigned node identifier (UUID)';


--
-- Name: COLUMN document_nodes.clause_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.document_nodes.clause_id IS 'Clause/article reference, e.g. 9.8.2.1.(1)';


--
-- Name: COLUMN document_nodes.page_number; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.document_nodes.page_number IS '1-based source page number, when known';


--
-- Name: COLUMN document_nodes.parent_section; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.document_nodes.parent_section IS 'Nearest enclosing section heading';


--
-- Name: COLUMN document_nodes.section_path; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.document_nodes.section_path IS 'JSON array breadcrumb of headings, e.g. ["5", "5.3", "5.3.2"]';


--
-- Name: COLUMN document_nodes.deontic_statements; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.document_nodes.deontic_statements IS 'JSON array of DeonticStatement objects extracted from this node';


--
-- Name: COLUMN document_nodes.bbox; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.document_nodes.bbox IS 'Bounding box coordinates on the source page: {l, t, r, b, coord_origin}';


--
-- Name: document_nodes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.document_nodes ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.document_nodes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: document_pages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_pages (
    id bigint NOT NULL,
    document_id bigint NOT NULL,
    page_number integer NOT NULL,
    text text DEFAULT ''::text NOT NULL,
    char_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE document_pages; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.document_pages IS 'Page-tagged raw text per document, captured at extraction time for document-viewer page navigation and rule-to-source annotation';


--
-- Name: COLUMN document_pages.document_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.document_pages.document_id IS 'Foreign key to public.documents.id';


--
-- Name: COLUMN document_pages.page_number; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.document_pages.page_number IS '1-based source page number';


--
-- Name: COLUMN document_pages.text; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.document_pages.text IS 'Raw extracted text for this page';


--
-- Name: document_pages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.document_pages ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.document_pages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id bigint NOT NULL,
    md5_hash text DEFAULT ''::text NOT NULL,
    filename text DEFAULT ''::text NOT NULL,
    file_path text DEFAULT ''::text NOT NULL,
    upload_date text DEFAULT ''::text NOT NULL,
    doc_type text DEFAULT 'Specification'::text NOT NULL,
    project_code text DEFAULT ''::text NOT NULL,
    originator text DEFAULT ''::text NOT NULL,
    volume_system text DEFAULT ''::text NOT NULL,
    level text DEFAULT ''::text NOT NULL,
    type text DEFAULT ''::text NOT NULL,
    role text DEFAULT ''::text NOT NULL,
    number text DEFAULT ''::text NOT NULL,
    suitability_code text DEFAULT 'S0'::text NOT NULL,
    revision_code text DEFAULT 'P01.01'::text NOT NULL,
    cde_state text DEFAULT 'WIP'::text NOT NULL,
    doclang_storage_path text,
    doclang_xml text DEFAULT ''::text NOT NULL,
    doclang_archive_path text,
    char_count integer DEFAULT 0 NOT NULL,
    text_preview text DEFAULT ''::text NOT NULL,
    element_bboxes jsonb DEFAULT '[]'::jsonb NOT NULL,
    toc_tree jsonb,
    CONSTRAINT documents_cde_state_check CHECK ((cde_state = ANY (ARRAY['WIP'::text, 'SHARED'::text, 'PUBLISHED'::text, 'ARCHIVED'::text]))),
    CONSTRAINT documents_doc_type_check CHECK ((doc_type = ANY (ARRAY['Specification'::text, 'Code'::text, 'Manual'::text, 'Standard'::text, 'Drawing'::text, 'Schedule'::text, 'O&M Manual'::text, 'Warranty'::text, 'Assessment'::text, 'Report'::text, 'RFI Log'::text, 'Other'::text]))),
    CONSTRAINT documents_revision_code_check CHECK ((revision_code ~* '^(P[0-9]{2}(\.[0-9]{2})?|C[0-9]{2}|D[0-9]{2})$'::text)),
    CONSTRAINT documents_suitability_code_check CHECK ((suitability_code = ANY (ARRAY['S0'::text, 'S1'::text, 'S2'::text, 'S3'::text, 'S4'::text, 'S5'::text, 'S6'::text, 'S7'::text, 'A1'::text, 'A2'::text, 'A3'::text, 'A4'::text, 'B1'::text, 'B2'::text, 'B3'::text, 'B4'::text, 'CR'::text])))
);


--
-- Name: COLUMN documents.doc_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.doc_type IS 'Document classification type: Code, Specification, Manual, Standard, Drawing, Schedule, Assessment, Report, Other';


--
-- Name: COLUMN documents.project_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.project_code IS 'ISO 19650 Project Code string';


--
-- Name: COLUMN documents.originator; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.originator IS 'ISO 19650 Originator / Authoring organization code';


--
-- Name: COLUMN documents.suitability_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.suitability_code IS 'ISO 19650 Suitability Code (S0-S4, A1-A4, B1-B4)';


--
-- Name: COLUMN documents.revision_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.revision_code IS 'ISO 19650 Revision Code (e.g. P01.01, C01)';


--
-- Name: COLUMN documents.cde_state; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.cde_state IS 'CDE Workflow State: WIP, SHARED, PUBLISHED, ARCHIVED';


--
-- Name: COLUMN documents.doclang_storage_path; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.doclang_storage_path IS 'Storage URI (sb://bucket/doclang/...) for offloaded DocLang XML or .dclx archives';


--
-- Name: COLUMN documents.doclang_xml; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.doclang_xml IS 'Canonical DocLang XML export (including OTSL table definitions) produced by Docling extraction';


--
-- Name: COLUMN documents.doclang_archive_path; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.doclang_archive_path IS 'Storage URI (sb://bucket/doclang/...) for pre-generated DocLang .dclx zip archives';


--
-- Name: COLUMN documents.element_bboxes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.element_bboxes IS 'Per-element bbox records aligned to <custom><bg_element_id value="..."/></custom> ids injected into doclang_xml at extraction time: [{element_id, kind, page_number, bbox, order}, ...]. Empty for documents whose DocLang XML predates this feature or came from a raw .dclg/.dclx import.';


--
-- Name: COLUMN documents.toc_tree; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.toc_tree IS 'Cached Smart Table of Contents (TOC) tree and metadata';


--
-- Name: documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.documents ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.documents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: evaluation_findings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evaluation_findings (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    ifc_file_id bigint,
    rule_id bigint,
    rule_snapshot jsonb NOT NULL,
    element_global_id text NOT NULL,
    element_name text,
    storey text,
    space text,
    bimguard_verdict text NOT NULL,
    bimguard_reason text,
    captured_by_email text,
    captured_at timestamp with time zone DEFAULT now() NOT NULL,
    human_verdict text,
    reviewer_email text,
    reviewed_at timestamp with time zone,
    review_notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT evaluation_findings_bimguard_verdict_check CHECK ((bimguard_verdict = ANY (ARRAY['PASS'::text, 'FAIL'::text, 'MISSING'::text, 'WAIVED'::text, 'NOT_APPLICABLE'::text]))),
    CONSTRAINT evaluation_findings_human_verdict_check CHECK ((human_verdict = ANY (ARRAY['PASS'::text, 'FAIL'::text, 'NOT_APPLICABLE'::text, 'INDETERMINATE'::text])))
);


--
-- Name: TABLE evaluation_findings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.evaluation_findings IS 'Human-validated ground truth for BIM-Guard PASS/FAIL verdicts, scored externally by bim-guard-evaluation';


--
-- Name: COLUMN evaluation_findings.rule_snapshot; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.evaluation_findings.rule_snapshot IS 'Frozen copy of the rule fields graded at capture time (reference, operator, check_value/value_min/value_max, property_set/property_name, target_ifc_class, severity, unit, mechanism); public.rules has no version history';


--
-- Name: COLUMN evaluation_findings.bimguard_verdict; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.evaluation_findings.bimguard_verdict IS 'BIM-Guard''s own verdict at capture time, same vocabulary as ComplianceComparator._entry() status values';


--
-- Name: COLUMN evaluation_findings.human_verdict; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.evaluation_findings.human_verdict IS 'Reviewer-confirmed correct verdict; NULL until reviewed. INDETERMINATE means the IFC lacked enough information to judge';


--
-- Name: evaluation_findings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.evaluation_findings ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.evaluation_findings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: github_repositories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.github_repositories (
    id bigint NOT NULL,
    name text NOT NULL,
    owner text NOT NULL,
    url text NOT NULL,
    branch text DEFAULT 'main'::text NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    organization_id bigint NOT NULL
);


--
-- Name: github_repositories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.github_repositories ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.github_repositories_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: group_project_grants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_project_grants (
    id bigint NOT NULL,
    group_id bigint NOT NULL,
    project_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: group_project_grants_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.group_project_grants ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.group_project_grants_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.groups (
    id bigint NOT NULL,
    organization_id bigint NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.groups ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: issue_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.issue_history (
    global_id text NOT NULL,
    payload_json text DEFAULT '{}'::text NOT NULL,
    updated_at text DEFAULT ''::text NOT NULL
);


--
-- Name: keep_alive; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.keep_alive (
    id bigint NOT NULL,
    pinged_at timestamp with time zone DEFAULT now()
);


--
-- Name: keep_alive_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.keep_alive ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.keep_alive_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: llm_calls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_calls (
    id bigint NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    organization_id bigint,
    project_id bigint,
    run_key text,
    context text NOT NULL,
    provider text,
    model text NOT NULL,
    input jsonb DEFAULT '[]'::jsonb NOT NULL,
    output text,
    status text DEFAULT 'success'::text NOT NULL,
    error text,
    input_tokens integer,
    output_tokens integer,
    total_tokens integer,
    cost numeric,
    latency_ms integer,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: llm_calls_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.llm_calls ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.llm_calls_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: llm_provider_instances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_provider_instances (
    id bigint NOT NULL,
    organization_id bigint NOT NULL,
    name text NOT NULL,
    kind text NOT NULL,
    api_key text DEFAULT ''::text NOT NULL,
    api_base text DEFAULT ''::text NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    notes text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: llm_provider_instances_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.llm_provider_instances ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.llm_provider_instances_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: llm_task_model_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_task_model_assignments (
    id bigint NOT NULL,
    organization_id bigint NOT NULL,
    task_key text NOT NULL,
    provider_instance_id bigint NOT NULL,
    model_id text NOT NULL,
    model_name text NOT NULL,
    context_length integer,
    input_price_per_million numeric,
    output_price_per_million numeric,
    is_default boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: llm_task_model_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.llm_task_model_assignments ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.llm_task_model_assignments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: memberships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.memberships (
    id bigint NOT NULL,
    organization_id bigint NOT NULL,
    user_id uuid NOT NULL,
    role text DEFAULT 'member'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    group_id bigint,
    CONSTRAINT memberships_role_check CHECK ((role = ANY (ARRAY['owner'::text, 'admin'::text, 'member'::text])))
);


--
-- Name: memberships_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.memberships ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.memberships_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: model_enhancement_lineage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_enhancement_lineage (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    source_reference text NOT NULL,
    output_reference text NOT NULL,
    version bigint NOT NULL,
    summary jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    source_version bigint DEFAULT 0 NOT NULL,
    source_sha256 text,
    ifc_file_id bigint,
    CONSTRAINT model_enhancement_lineage_distinct_artifacts_check CHECK ((source_reference <> output_reference)),
    CONSTRAINT model_enhancement_lineage_source_sha256_format_check CHECK (((source_sha256 IS NULL) OR (source_sha256 ~ '^[0-9a-f]{64}$'::text))),
    CONSTRAINT model_enhancement_lineage_source_version_check CHECK ((source_version >= 0)),
    CONSTRAINT model_enhancement_lineage_version_check CHECK ((version > 0))
);


--
-- Name: model_enhancement_lineage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.model_enhancement_lineage ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.model_enhancement_lineage_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: model_enhancement_version_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_enhancement_version_counters (
    project_id bigint NOT NULL,
    next_version bigint NOT NULL,
    CONSTRAINT model_enhancement_version_counters_next_version_check CHECK ((next_version > 0))
);


--
-- Name: organization_document_grants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization_document_grants (
    id bigint NOT NULL,
    organization_id bigint NOT NULL,
    document_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: organization_document_grants_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.organization_document_grants ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.organization_document_grants_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: organization_invites; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization_invites (
    id bigint NOT NULL,
    organization_id bigint NOT NULL,
    email text NOT NULL,
    role text DEFAULT 'member'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    accepted_at timestamp with time zone,
    CONSTRAINT organization_invites_role_check CHECK ((role = ANY (ARRAY['owner'::text, 'admin'::text, 'member'::text])))
);


--
-- Name: organization_invites_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.organization_invites ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.organization_invites_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: organization_project_grants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization_project_grants (
    id bigint NOT NULL,
    organization_id bigint NOT NULL,
    project_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: organization_project_grants_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.organization_project_grants ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.organization_project_grants_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: organization_ruleset_grants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization_ruleset_grants (
    id bigint NOT NULL,
    organization_id bigint NOT NULL,
    ruleset_id text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: organization_ruleset_grants_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.organization_ruleset_grants ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.organization_ruleset_grants_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: organizations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organizations (
    id bigint NOT NULL,
    name text NOT NULL,
    slug text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    org_code character varying(6) DEFAULT ''::character varying NOT NULL
);


--
-- Name: organizations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.organizations ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.organizations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: parsing_engine_instances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parsing_engine_instances (
    id bigint NOT NULL,
    name text NOT NULL,
    kind text NOT NULL,
    api_url text NOT NULL,
    api_key text DEFAULT ''::text NOT NULL,
    strategy text DEFAULT 'auto'::text NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    notes text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    organization_id bigint
);


--
-- Name: profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profiles (
    id uuid NOT NULL,
    full_name text DEFAULT ''::text NOT NULL,
    avatar_url text DEFAULT ''::text NOT NULL,
    title text DEFAULT ''::text NOT NULL,
    default_organization_id bigint,
    preferences jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_superadmin boolean DEFAULT false NOT NULL,
    email text
);


--
-- Name: project_document_bindings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_document_bindings (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    document_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: project_document_bindings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.project_document_bindings ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.project_document_bindings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: project_ifc_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_ifc_files (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    file_path text NOT NULL,
    file_name text DEFAULT ''::text NOT NULL,
    is_primary boolean DEFAULT false NOT NULL,
    role text DEFAULT 'context'::text NOT NULL,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    project_code text DEFAULT ''::text NOT NULL,
    originator text DEFAULT ''::text NOT NULL,
    volume_system text DEFAULT ''::text NOT NULL,
    level text DEFAULT ''::text NOT NULL,
    type text DEFAULT ''::text NOT NULL,
    number text DEFAULT ''::text NOT NULL,
    suitability_code text DEFAULT 'S0'::text NOT NULL,
    revision_code text DEFAULT 'P01.01'::text NOT NULL,
    cde_state text DEFAULT 'WIP'::text NOT NULL,
    cde_approved_by text DEFAULT ''::text NOT NULL,
    cde_approved_at timestamp with time zone,
    ifc_schema text DEFAULT ''::text NOT NULL,
    authoring_application text DEFAULT ''::text NOT NULL,
    storey_count integer,
    element_count integer,
    discipline_summary jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT project_ifc_files_cde_state_check CHECK ((cde_state = ANY (ARRAY['WIP'::text, 'SHARED'::text, 'PUBLISHED'::text, 'ARCHIVED'::text]))),
    CONSTRAINT project_ifc_files_revision_code_check CHECK ((revision_code ~* '^(P[0-9]{2}(\.[0-9]{2})?|C[0-9]{2}|D[0-9]{2})$'::text)),
    CONSTRAINT project_ifc_files_suitability_code_check CHECK ((suitability_code = ANY (ARRAY['S0'::text, 'S1'::text, 'S2'::text, 'S3'::text, 'S4'::text, 'S5'::text, 'S6'::text, 'S7'::text, 'A1'::text, 'A2'::text, 'A3'::text, 'A4'::text, 'B1'::text, 'B2'::text, 'B3'::text, 'B4'::text, 'CR'::text])))
);


--
-- Name: TABLE project_ifc_files; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.project_ifc_files IS 'IFC models attached to a project; one row per file, at most one primary';


--
-- Name: COLUMN project_ifc_files.project_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_ifc_files.project_id IS 'Foreign key to public.projects.id (BIGINT); rows die with the project';


--
-- Name: COLUMN project_ifc_files.file_path; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_ifc_files.file_path IS 'ObjectStorage reference, e.g. sb://bucket/uploads/ifc/<uuid>_model.ifc';


--
-- Name: COLUMN project_ifc_files.file_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_ifc_files.file_name IS 'Basename of the stored reference, for display';


--
-- Name: COLUMN project_ifc_files.is_primary; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_ifc_files.is_primary IS 'The model an analysis run starts from; at most one per project';


--
-- Name: COLUMN project_ifc_files.role; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_ifc_files.role IS 'Discipline this model carries: primary, structural, architectural, context, ...';


--
-- Name: COLUMN project_ifc_files.ifc_schema; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_ifc_files.ifc_schema IS 'IFC schema version read from the model header, e.g. IFC4, IFC2X3; blank if extraction failed';


--
-- Name: COLUMN project_ifc_files.authoring_application; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_ifc_files.authoring_application IS 'IfcApplication.ApplicationFullName + Version from the model that produced this file; blank if absent or unreadable';


--
-- Name: COLUMN project_ifc_files.storey_count; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_ifc_files.storey_count IS 'Count of IfcBuildingStorey entities; NULL if extraction failed rather than the model genuinely having none';


--
-- Name: COLUMN project_ifc_files.element_count; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_ifc_files.element_count IS 'Count of IfcElement occurrences; NULL if extraction failed rather than the model genuinely having none';


--
-- Name: COLUMN project_ifc_files.discipline_summary; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_ifc_files.discipline_summary IS 'Heuristic element-count breakdown by discipline (architectural/structural/mep/other), keyed by category name';


--
-- Name: project_ifc_files_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.project_ifc_files ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.project_ifc_files_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: project_naming_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_naming_config (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    project_code text DEFAULT ''::text NOT NULL,
    originator_code text DEFAULT ''::text NOT NULL,
    type_code text DEFAULT 'CO'::text NOT NULL,
    suitability text DEFAULT 'S1'::text NOT NULL,
    revision text DEFAULT '01'::text NOT NULL,
    separator text DEFAULT '_'::text NOT NULL,
    date_format text DEFAULT 'YYMMDD'::text NOT NULL,
    class_a text DEFAULT ''::text NOT NULL,
    class_b text DEFAULT ''::text NOT NULL,
    active_convention text DEFAULT 'iso19650_date'::text NOT NULL,
    level_codes jsonb DEFAULT '[]'::jsonb NOT NULL,
    type_codes jsonb DEFAULT '[]'::jsonb NOT NULL,
    discipline_codes jsonb DEFAULT '[]'::jsonb NOT NULL,
    volume_codes jsonb DEFAULT '[]'::jsonb NOT NULL,
    custom_conventions jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE project_naming_config; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.project_naming_config IS 'ISO 19650 information-container naming setup; exactly one row per project';


--
-- Name: COLUMN project_naming_config.project_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.project_id IS 'Foreign key to public.projects.id (BIGINT); the row dies with the project';


--
-- Name: COLUMN project_naming_config.project_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.project_code IS 'Unique project identifier, e.g. A1234 (ISO 19650-1 Annex A)';


--
-- Name: COLUMN project_naming_config.originator_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.originator_code IS 'Author / issuing organisation, e.g. BIM01';


--
-- Name: COLUMN project_naming_config.type_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.type_code IS 'Information type: CO correspondence, RP report, MO model';


--
-- Name: COLUMN project_naming_config.suitability; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.suitability IS 'CDE status (ISO 19650-2 Table 1): S0, S1, S2, S3 or A';


--
-- Name: COLUMN project_naming_config.revision; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.revision IS 'Revision, e.g. 01; P01 preliminary, C01 contract';


--
-- Name: COLUMN project_naming_config.separator; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.separator IS 'Field separator used when rendering a name: _, - or .';


--
-- Name: COLUMN project_naming_config.date_format; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.date_format IS 'YYMMDD, DDMMYY, YYYYMMDD, DD-MM-YY or ISO';


--
-- Name: COLUMN project_naming_config.class_a; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.class_a IS 'Uniclass 2015 primary classification token, used by the uniclass convention';


--
-- Name: COLUMN project_naming_config.class_b; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.class_b IS 'Uniclass 2015 secondary classification token';


--
-- Name: COLUMN project_naming_config.active_convention; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.active_convention IS 'id of the convention names are rendered by; a preset or a custom_conventions entry';


--
-- Name: COLUMN project_naming_config.level_codes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.level_codes IS 'JSON array of {code,label} this project narrows the level library to; [] means all';


--
-- Name: COLUMN project_naming_config.custom_conventions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_naming_config.custom_conventions IS 'JSON array of {id,name,separator,format,description} defined by this project';


--
-- Name: project_naming_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.project_naming_config ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.project_naming_config_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: project_ruleset_bindings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_ruleset_bindings (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    ruleset_id text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: project_ruleset_bindings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.project_ruleset_bindings ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.project_ruleset_bindings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: projects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.projects (
    id bigint NOT NULL,
    name text DEFAULT ''::text NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    status text DEFAULT 'Draft'::text NOT NULL,
    ifc_file_path text DEFAULT ''::text NOT NULL,
    ifc_md5_hash text DEFAULT ''::text NOT NULL,
    created_at text DEFAULT ''::text NOT NULL,
    updated_at text DEFAULT ''::text NOT NULL,
    country text DEFAULT 'UK'::text NOT NULL,
    analysis_types text[] DEFAULT ARRAY['piping'::text] NOT NULL,
    analysis_type text DEFAULT 'Arch'::text NOT NULL,
    project_type text,
    project_size_sqm numeric,
    buildings_count integer,
    floors_count integer,
    building_code text,
    project_code character varying(6) DEFAULT ''::text NOT NULL,
    originator text DEFAULT ''::text NOT NULL,
    volume_system text DEFAULT ''::text NOT NULL,
    level text DEFAULT ''::text NOT NULL,
    type text DEFAULT ''::text NOT NULL,
    role text DEFAULT ''::text NOT NULL,
    number text DEFAULT ''::text NOT NULL,
    suitability_code text DEFAULT 'S0'::text NOT NULL,
    revision_code text DEFAULT 'P01.01'::text NOT NULL,
    cde_state text DEFAULT 'WIP'::text NOT NULL,
    cde_approved_by text DEFAULT ''::text NOT NULL,
    cde_approved_at timestamp with time zone,
    classification_standard text,
    organization_id bigint DEFAULT public.default_organization_id() NOT NULL,
    short_name character varying(24) DEFAULT ''::character varying NOT NULL,
    client_name text DEFAULT ''::text NOT NULL,
    CONSTRAINT projects_cde_state_check CHECK ((cde_state = ANY (ARRAY['WIP'::text, 'SHARED'::text, 'PUBLISHED'::text, 'ARCHIVED'::text]))),
    CONSTRAINT projects_revision_code_check CHECK ((revision_code ~* '^(P[0-9]{2}(\.[0-9]{2})?|C[0-9]{2}|D[0-9]{2})$'::text)),
    CONSTRAINT projects_suitability_code_check CHECK ((suitability_code = ANY (ARRAY['S0'::text, 'S1'::text, 'S2'::text, 'S3'::text, 'S4'::text, 'S5'::text, 'S6'::text, 'S7'::text, 'A1'::text, 'A2'::text, 'A3'::text, 'A4'::text, 'B1'::text, 'B2'::text, 'B3'::text, 'B4'::text, 'CR'::text]))),
    CONSTRAINT projects_wizard_counts_non_negative CHECK ((((project_size_sqm IS NULL) OR (project_size_sqm >= (0)::numeric)) AND ((buildings_count IS NULL) OR (buildings_count >= 0)) AND ((floors_count IS NULL) OR (floors_count >= 0)))),
    CONSTRAINT valid_analysis_type CHECK ((analysis_type = ANY (ARRAY['Arch'::text, 'Architectural'::text, 'Architecture'::text, 'arch'::text])))
);


--
-- Name: COLUMN projects.country; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.country IS 'Country/jurisdiction for project (affects applicable standards and building codes)';


--
-- Name: COLUMN projects.analysis_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.analysis_type IS 'Analysis type: Piping (Corrosive) [GC-001+CC-001], Halo [Blue Halo], or Architecture [future]';


--
-- Name: COLUMN projects.project_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.project_type IS 'Building type chosen in wizard step 1; one of app.constants.PROJECT_TYPES';


--
-- Name: COLUMN projects.project_size_sqm; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.project_size_sqm IS 'Gross floor area in square metres, as entered in wizard step 1';


--
-- Name: COLUMN projects.buildings_count; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.buildings_count IS 'Number of buildings in the project';


--
-- Name: COLUMN projects.floors_count; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.floors_count IS 'Number of floors in the project';


--
-- Name: COLUMN projects.building_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.building_code IS 'Building code chosen in wizard step 3; an id from app.constants.BUILDING_CODES, or NULL where the analysis domain does not need one (e.g. Piping corrosion)';


--
-- Name: COLUMN projects.project_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.project_code IS 'ISO 19650 Project Code string';


--
-- Name: COLUMN projects.originator; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.originator IS 'ISO 19650 Originator / Authoring organization code';


--
-- Name: COLUMN projects.volume_system; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.volume_system IS 'ISO 19650 Volume / Spatial system identifier';


--
-- Name: COLUMN projects.level; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.level IS 'ISO 19650 Level / Location breakdown';


--
-- Name: COLUMN projects.type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.type IS 'ISO 19650 Type designation (e.g. M3, DR, RP)';


--
-- Name: COLUMN projects.role; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.role IS 'ISO 19650 Discipline role code (e.g. A, S, M)';


--
-- Name: COLUMN projects.number; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.number IS 'ISO 19650 Sequential document number';


--
-- Name: COLUMN projects.suitability_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.suitability_code IS 'ISO 19650 Suitability Code (S0-S4, A1-A4, B1-B4)';


--
-- Name: COLUMN projects.revision_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.revision_code IS 'ISO 19650 Revision Code (e.g. P01.01, C01)';


--
-- Name: COLUMN projects.cde_state; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.cde_state IS 'CDE Workflow State: WIP, SHARED, PUBLISHED, ARCHIVED';


--
-- Name: COLUMN projects.classification_standard; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.projects.classification_standard IS 'bSDD dictionary code (e.g. uniclass_2015, omniclass_2020, ifc_4.3) this project is classified against; NULL when no standard has been chosen yet';


--
-- Name: projects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.projects ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.projects_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: report_artifacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_artifacts (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    artifact_type text NOT NULL,
    filename text NOT NULL,
    storage_ref text NOT NULL,
    content_type text DEFAULT 'application/octet-stream'::text NOT NULL,
    byte_size bigint NOT NULL,
    sha256 text NOT NULL,
    issue_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    ifc_file_id bigint,
    rule_folder text,
    ruleset_name text,
    created_by uuid,
    created_by_email text,
    CONSTRAINT report_artifacts_byte_size_check CHECK ((byte_size >= 0)),
    CONSTRAINT report_artifacts_issue_count_check CHECK ((issue_count >= 0)),
    CONSTRAINT report_artifacts_sha256_check CHECK ((length(sha256) = 64))
);


--
-- Name: report_artifacts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.report_artifacts ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.report_artifacts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.role_permissions (
    id bigint NOT NULL,
    organization_id bigint,
    action text NOT NULL,
    min_role text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT role_permissions_min_role_check CHECK ((min_role = ANY (ARRAY['owner'::text, 'admin'::text, 'member'::text])))
);


--
-- Name: role_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.role_permissions ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.role_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rule_check_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rule_check_categories (
    id bigint NOT NULL,
    name text NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    target_ifc_classes text[] DEFAULT '{}'::text[] NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE rule_check_categories; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.rule_check_categories IS 'Ordered check categories, per element type, used to group rule results in the analysis view.';


--
-- Name: rule_check_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.rule_check_categories ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.rule_check_categories_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rule_check_category_properties; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rule_check_category_properties (
    id bigint NOT NULL,
    target_ifc_class text NOT NULL,
    property_name text NOT NULL,
    check_category_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: rule_check_category_properties_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.rule_check_category_properties ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.rule_check_category_properties_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rule_extraction_drafts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rule_extraction_drafts (
    id bigint NOT NULL,
    source_document_id bigint NOT NULL,
    source_node_id text,
    clause jsonb,
    proposed_rule jsonb NOT NULL,
    confidence double precision DEFAULT 0.8 NOT NULL,
    extraction_method text DEFAULT 'litellm_legacy'::text NOT NULL,
    status text DEFAULT 'pending_review'::text NOT NULL,
    reviewer_email text,
    reviewed_at timestamp with time zone,
    review_notes text,
    promoted_rule_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    source_snippet text,
    original_proposed_rule jsonb,
    bbox jsonb,
    source_element_id text,
    original_source_element_id text,
    CONSTRAINT rule_extraction_drafts_confidence_check CHECK (((confidence >= (0)::double precision) AND (confidence <= (1)::double precision))),
    CONSTRAINT rule_extraction_drafts_extraction_method_check CHECK ((extraction_method = ANY (ARRAY['llamaindex_pydantic'::text, 'litellm_legacy'::text]))),
    CONSTRAINT rule_extraction_drafts_status_check CHECK ((status = ANY (ARRAY['pending_review'::text, 'accepted'::text, 'rejected'::text, 'edited'::text])))
);


--
-- Name: TABLE rule_extraction_drafts; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.rule_extraction_drafts IS 'LLM-extracted rule candidates awaiting review/promotion into public.rules; fixes the prior lack of a persisted extraction-draft state';


--
-- Name: COLUMN rule_extraction_drafts.source_document_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_extraction_drafts.source_document_id IS 'Foreign key to public.documents.id';


--
-- Name: COLUMN rule_extraction_drafts.source_node_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_extraction_drafts.source_node_id IS 'Links back to a DocumentNodeContract.node_id, when ingested via LlamaIndexIngestor';


--
-- Name: COLUMN rule_extraction_drafts.clause; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_extraction_drafts.clause IS 'JSON ClauseMetadata for the source clause, when known';


--
-- Name: COLUMN rule_extraction_drafts.proposed_rule; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_extraction_drafts.proposed_rule IS 'JSON RuleCreateRequest payload proposed by the extractor';


--
-- Name: COLUMN rule_extraction_drafts.promoted_rule_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_extraction_drafts.promoted_rule_id IS 'Set once the draft has been promoted into public.rules';


--
-- Name: COLUMN rule_extraction_drafts.source_snippet; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_extraction_drafts.source_snippet IS 'The originating DocumentNodeContract.text, carried forward so promote_draft() can populate rules.source_text';


--
-- Name: COLUMN rule_extraction_drafts.original_proposed_rule; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_extraction_drafts.original_proposed_rule IS 'The LLM-proposed rule as first extracted, captured only when a reviewer edits proposed_rule (status=edited). Null for drafts never edited.';


--
-- Name: COLUMN rule_extraction_drafts.bbox; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_extraction_drafts.bbox IS 'Source clause bounding box coordinates on the page for visual highlighting in PDF viewer: {l, t, r, b, coord_origin}';


--
-- Name: rule_extraction_drafts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.rule_extraction_drafts ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.rule_extraction_drafts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rule_folders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rule_folders (
    id bigint NOT NULL,
    ruleset_id text DEFAULT ''::text NOT NULL,
    display_name text DEFAULT ''::text NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    mechanism_scope text DEFAULT ''::text NOT NULL,
    created_at text DEFAULT ''::text NOT NULL,
    updated_at text DEFAULT ''::text NOT NULL,
    category text DEFAULT 'Arch'::text NOT NULL,
    CONSTRAINT valid_rule_folder_category CHECK ((category = 'Arch'::text))
);


--
-- Name: COLUMN rule_folders.category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_folders.category IS 'Ruleset category: Arch (architectural building code), Piping (MEP corrosion), or seismic (Blue Halo)';


--
-- Name: rule_folders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.rule_folders ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.rule_folders_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rule_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rule_snapshots (
    id bigint NOT NULL,
    name text NOT NULL,
    source_ruleset_id text DEFAULT ''::text NOT NULL,
    source_mode text DEFAULT 'manual'::text NOT NULL,
    category text DEFAULT 'Arch'::text NOT NULL,
    rules_json jsonb DEFAULT '[]'::jsonb NOT NULL,
    rule_count integer DEFAULT 0 NOT NULL,
    notes text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text DEFAULT ''::text NOT NULL,
    CONSTRAINT rule_snapshots_category_check CHECK ((category = ANY (ARRAY['Arch'::text, 'Piping'::text, 'seismic'::text]))),
    CONSTRAINT rule_snapshots_source_mode_check CHECK ((source_mode = ANY (ARRAY['pdf'::text, 'ids'::text, 'manual'::text, 'mixed'::text])))
);


--
-- Name: TABLE rule_snapshots; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.rule_snapshots IS 'Named, timestamped, frozen copies of a rule folder''s rules at save time — independent of subsequent edits to public.rules, and the source for the "configuration only" PDF export.';


--
-- Name: COLUMN rule_snapshots.source_ruleset_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_snapshots.source_ruleset_id IS 'ruleset_id the snapshot was taken from (informational; the live folder may since have changed or been deleted)';


--
-- Name: COLUMN rule_snapshots.source_mode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_snapshots.source_mode IS 'How the snapshotted rules originated: pdf (LLM/regex extraction), ids (IDS import), manual, or mixed';


--
-- Name: COLUMN rule_snapshots.rules_json; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_snapshots.rules_json IS 'Frozen JSON array of rule rows (same shape as list_by_ruleset()) captured at snapshot time';


--
-- Name: COLUMN rule_snapshots.rule_count; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rule_snapshots.rule_count IS 'Denormalized count of rules_json entries, for fast list rendering without parsing JSONB';


--
-- Name: rule_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.rule_snapshots ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.rule_snapshots_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rules (
    id bigint NOT NULL,
    reference text DEFAULT ''::text NOT NULL,
    rule_type text DEFAULT ''::text NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    target_ifc_class text DEFAULT ''::text NOT NULL,
    parameters text DEFAULT '{}'::text NOT NULL,
    created_at text DEFAULT ''::text NOT NULL,
    updated_at text DEFAULT ''::text NOT NULL,
    source_text text DEFAULT ''::text NOT NULL,
    property_set text DEFAULT ''::text NOT NULL,
    property_name text DEFAULT ''::text NOT NULL,
    fallback_property text DEFAULT ''::text NOT NULL,
    operator text DEFAULT ''::text NOT NULL,
    check_value text DEFAULT 'null'::text NOT NULL,
    value_min text DEFAULT 'null'::text NOT NULL,
    value_max text DEFAULT 'null'::text NOT NULL,
    unit text DEFAULT ''::text NOT NULL,
    applies_when text DEFAULT '{}'::text NOT NULL,
    severity text DEFAULT 'mandatory'::text NOT NULL,
    keyword text DEFAULT ''::text NOT NULL,
    compliance_type text DEFAULT ''::text NOT NULL,
    exceptions text DEFAULT '[]'::text NOT NULL,
    related_refs text DEFAULT '[]'::text NOT NULL,
    overridden_by text DEFAULT ''::text NOT NULL,
    confidence text DEFAULT ''::text NOT NULL,
    extraction_method text DEFAULT 'manual'::text NOT NULL,
    needs_review integer DEFAULT 0 NOT NULL,
    mechanism text DEFAULT ''::text NOT NULL,
    ruleset_id text DEFAULT ''::text NOT NULL,
    rule_category text DEFAULT 'property_check'::text NOT NULL,
    value_min_property text DEFAULT ''::text NOT NULL,
    value_max_property text DEFAULT ''::text NOT NULL,
    value_min_offset text DEFAULT '0'::text NOT NULL,
    value_max_offset text DEFAULT '0'::text NOT NULL,
    compare_property text DEFAULT ''::text NOT NULL,
    name_pattern text DEFAULT ''::text NOT NULL,
    uniqueness_scope text DEFAULT ''::text NOT NULL,
    category text DEFAULT 'Arch'::text NOT NULL,
    source_document_id bigint,
    rase_requirement text,
    rase_applicability jsonb,
    rase_selection jsonb,
    rase_exception jsonb,
    source_node_id text,
    source_page_number integer,
    source_bbox jsonb,
    source_element_id text,
    value_min_scale text DEFAULT '1'::text NOT NULL,
    value_max_scale text DEFAULT '1'::text NOT NULL,
    check_category_id bigint,
    CONSTRAINT valid_rule_category_domain CHECK (((category IS NULL) OR (category = 'Arch'::text)))
);


--
-- Name: COLUMN rules.category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rules.category IS 'Domain category: Arch (architectural building code), Piping (MEP corrosion), or seismic (Blue Halo)';


--
-- Name: COLUMN rules.source_document_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rules.source_document_id IS 'FK to public.documents.id — the document this rule was extracted from, when known (NULL for manually-authored rules)';


--
-- Name: COLUMN rules.value_min_scale; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rules.value_min_scale IS 'Multiplier applied to value_min_property before value_min_offset is added: resolved_value_min = (property x scale) + offset. Default 1 (no-op).';


--
-- Name: COLUMN rules.value_max_scale; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rules.value_max_scale IS 'Multiplier applied to value_max_property before value_max_offset is added: resolved_value_max = (property x scale) + offset. Default 1 (no-op).';


--
-- Name: COLUMN rules.check_category_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rules.check_category_id IS 'rule_check_categories entry this rule is grouped under in analysis results; NULL = uncategorized.';


--
-- Name: rules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.rules ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.rules_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: scim_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scim_tokens (
    id bigint NOT NULL,
    organization_id bigint NOT NULL,
    token_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone,
    revoked_at timestamp with time zone
);


--
-- Name: scim_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.scim_tokens ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.scim_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: standards_by_project; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.standards_by_project (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    standard_id text NOT NULL,
    source text NOT NULL,
    file_path text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT standards_by_project_source_check CHECK ((source = ANY (ARRAY['notebook'::text, 'uploaded'::text])))
);


--
-- Name: TABLE standards_by_project; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.standards_by_project IS 'Junction table linking projects to selected standards (normative references)';


--
-- Name: COLUMN standards_by_project.project_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.standards_by_project.project_id IS 'Foreign key to public.projects.id (BIGINT)';


--
-- Name: COLUMN standards_by_project.standard_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.standards_by_project.standard_id IS 'Standard identifier: a NOTEBOOK_STANDARDS id (e.g. nasa-12, en-15329) or a generated id for an upload';


--
-- Name: COLUMN standards_by_project.source; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.standards_by_project.source IS 'Source of standard: notebook (predefined) or uploaded (custom file)';


--
-- Name: COLUMN standards_by_project.file_path; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.standards_by_project.file_path IS 'For uploaded standards, the object key in Supabase Storage';


--
-- Name: standards_by_project_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.standards_by_project ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.standards_by_project_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: static_data_assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.static_data_assets (
    id bigint NOT NULL,
    asset_key text NOT NULL,
    source_path text DEFAULT ''::text NOT NULL,
    format text DEFAULT 'json'::text NOT NULL,
    content_json text DEFAULT '{}'::text NOT NULL,
    content_text text DEFAULT ''::text NOT NULL,
    content_sha256 text DEFAULT ''::text NOT NULL,
    migrated_at text DEFAULT ''::text NOT NULL,
    active integer DEFAULT 1 NOT NULL
);


--
-- Name: static_data_assets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.static_data_assets ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.static_data_assets_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: unstructured_instances_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.parsing_engine_instances ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.unstructured_instances_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: uploaded_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.uploaded_files (
    id bigint NOT NULL,
    project_id bigint,
    kind text DEFAULT 'ifc'::text NOT NULL,
    filename text NOT NULL,
    storage_ref text NOT NULL,
    file_hash_sha256 text NOT NULL,
    size_bytes bigint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT uploaded_files_kind_check CHECK ((kind = ANY (ARRAY['ifc'::text, 'document'::text, 'standard'::text])))
);


--
-- Name: TABLE uploaded_files; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.uploaded_files IS 'Storage references and SHA-256 digests for uploaded IFC models, documents and standards';


--
-- Name: COLUMN uploaded_files.project_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.uploaded_files.project_id IS 'Foreign key to public.projects.id (BIGINT); NULL until the project is created';


--
-- Name: COLUMN uploaded_files.storage_ref; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.uploaded_files.storage_ref IS 'ObjectStorage reference, e.g. sb://bucket/uploads/ifc/<uuid>_model.ifc';


--
-- Name: COLUMN uploaded_files.file_hash_sha256; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.uploaded_files.file_hash_sha256 IS 'Hex SHA-256 of the stored bytes; the cache key shared with the Phase 6B parser';


--
-- Name: uploaded_files_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.uploaded_files ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.uploaded_files_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: app_settings app_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (key);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: bcf_comments bcf_comments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bcf_comments
    ADD CONSTRAINT bcf_comments_pkey PRIMARY KEY (guid);


--
-- Name: bcf_topics bcf_topics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bcf_topics
    ADD CONSTRAINT bcf_topics_pkey PRIMARY KEY (guid);


--
-- Name: bcf_viewpoints bcf_viewpoints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bcf_viewpoints
    ADD CONSTRAINT bcf_viewpoints_pkey PRIMARY KEY (guid);


--
-- Name: chat_conversations chat_conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_conversations
    ADD CONSTRAINT chat_conversations_pkey PRIMARY KEY (id);


--
-- Name: chat_messages chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_pkey PRIMARY KEY (id);


--
-- Name: client_documents client_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.client_documents
    ADD CONSTRAINT client_documents_pkey PRIMARY KEY (id);


--
-- Name: document_nodes document_nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_nodes
    ADD CONSTRAINT document_nodes_pkey PRIMARY KEY (id);


--
-- Name: document_pages document_pages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_pages
    ADD CONSTRAINT document_pages_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: evaluation_findings evaluation_findings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_findings
    ADD CONSTRAINT evaluation_findings_pkey PRIMARY KEY (id);


--
-- Name: github_repositories github_repositories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.github_repositories
    ADD CONSTRAINT github_repositories_pkey PRIMARY KEY (id);


--
-- Name: github_repositories github_repositories_url_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.github_repositories
    ADD CONSTRAINT github_repositories_url_key UNIQUE (url);


--
-- Name: group_project_grants group_project_grants_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_project_grants
    ADD CONSTRAINT group_project_grants_key UNIQUE (group_id, project_id);


--
-- Name: group_project_grants group_project_grants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_project_grants
    ADD CONSTRAINT group_project_grants_pkey PRIMARY KEY (id);


--
-- Name: groups groups_org_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_org_name_key UNIQUE (organization_id, name);


--
-- Name: groups groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_pkey PRIMARY KEY (id);


--
-- Name: issue_history issue_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_history
    ADD CONSTRAINT issue_history_pkey PRIMARY KEY (global_id);


--
-- Name: keep_alive keep_alive_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.keep_alive
    ADD CONSTRAINT keep_alive_pkey PRIMARY KEY (id);


--
-- Name: llm_calls llm_calls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_calls
    ADD CONSTRAINT llm_calls_pkey PRIMARY KEY (id);


--
-- Name: llm_provider_instances llm_provider_instances_org_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_provider_instances
    ADD CONSTRAINT llm_provider_instances_org_name_key UNIQUE (organization_id, name);


--
-- Name: llm_provider_instances llm_provider_instances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_provider_instances
    ADD CONSTRAINT llm_provider_instances_pkey PRIMARY KEY (id);


--
-- Name: llm_task_model_assignments llm_task_model_assignments_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_task_model_assignments
    ADD CONSTRAINT llm_task_model_assignments_key UNIQUE (organization_id, task_key, provider_instance_id, model_id);


--
-- Name: llm_task_model_assignments llm_task_model_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_task_model_assignments
    ADD CONSTRAINT llm_task_model_assignments_pkey PRIMARY KEY (id);


--
-- Name: memberships memberships_org_user_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT memberships_org_user_key UNIQUE (organization_id, user_id);


--
-- Name: memberships memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT memberships_pkey PRIMARY KEY (id);


--
-- Name: model_enhancement_lineage model_enhancement_lineage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_enhancement_lineage
    ADD CONSTRAINT model_enhancement_lineage_pkey PRIMARY KEY (id);


--
-- Name: model_enhancement_lineage model_enhancement_lineage_project_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_enhancement_lineage
    ADD CONSTRAINT model_enhancement_lineage_project_version_key UNIQUE (project_id, version);


--
-- Name: model_enhancement_version_counters model_enhancement_version_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_enhancement_version_counters
    ADD CONSTRAINT model_enhancement_version_counters_pkey PRIMARY KEY (project_id);


--
-- Name: organization_document_grants organization_document_grants_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_document_grants
    ADD CONSTRAINT organization_document_grants_key UNIQUE (organization_id, document_id);


--
-- Name: organization_document_grants organization_document_grants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_document_grants
    ADD CONSTRAINT organization_document_grants_pkey PRIMARY KEY (id);


--
-- Name: organization_invites organization_invites_org_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_invites
    ADD CONSTRAINT organization_invites_org_email_key UNIQUE (organization_id, email);


--
-- Name: organization_invites organization_invites_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_invites
    ADD CONSTRAINT organization_invites_pkey PRIMARY KEY (id);


--
-- Name: organization_project_grants organization_project_grants_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_project_grants
    ADD CONSTRAINT organization_project_grants_key UNIQUE (organization_id, project_id);


--
-- Name: organization_project_grants organization_project_grants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_project_grants
    ADD CONSTRAINT organization_project_grants_pkey PRIMARY KEY (id);


--
-- Name: organization_ruleset_grants organization_ruleset_grants_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_ruleset_grants
    ADD CONSTRAINT organization_ruleset_grants_key UNIQUE (organization_id, ruleset_id);


--
-- Name: organization_ruleset_grants organization_ruleset_grants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_ruleset_grants
    ADD CONSTRAINT organization_ruleset_grants_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_slug_key UNIQUE (slug);


--
-- Name: parsing_engine_instances parsing_engine_instances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parsing_engine_instances
    ADD CONSTRAINT parsing_engine_instances_pkey PRIMARY KEY (id);


--
-- Name: profiles profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_pkey PRIMARY KEY (id);


--
-- Name: project_document_bindings project_document_bindings_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_document_bindings
    ADD CONSTRAINT project_document_bindings_key UNIQUE (project_id, document_id);


--
-- Name: project_document_bindings project_document_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_document_bindings
    ADD CONSTRAINT project_document_bindings_pkey PRIMARY KEY (id);


--
-- Name: project_ifc_files project_ifc_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_ifc_files
    ADD CONSTRAINT project_ifc_files_pkey PRIMARY KEY (id);


--
-- Name: project_naming_config project_naming_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_naming_config
    ADD CONSTRAINT project_naming_config_pkey PRIMARY KEY (id);


--
-- Name: project_ruleset_bindings project_ruleset_bindings_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_ruleset_bindings
    ADD CONSTRAINT project_ruleset_bindings_key UNIQUE (project_id, ruleset_id);


--
-- Name: project_ruleset_bindings project_ruleset_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_ruleset_bindings
    ADD CONSTRAINT project_ruleset_bindings_pkey PRIMARY KEY (id);


--
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- Name: report_artifacts report_artifacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_artifacts
    ADD CONSTRAINT report_artifacts_pkey PRIMARY KEY (id);


--
-- Name: report_artifacts report_artifacts_storage_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_artifacts
    ADD CONSTRAINT report_artifacts_storage_ref_key UNIQUE (storage_ref);


--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_scope_action_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_scope_action_key UNIQUE NULLS NOT DISTINCT (organization_id, action);


--
-- Name: rule_check_categories rule_check_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_check_categories
    ADD CONSTRAINT rule_check_categories_pkey PRIMARY KEY (id);


--
-- Name: rule_check_category_properties rule_check_category_properties_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_check_category_properties
    ADD CONSTRAINT rule_check_category_properties_pkey PRIMARY KEY (id);


--
-- Name: rule_extraction_drafts rule_extraction_drafts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_extraction_drafts
    ADD CONSTRAINT rule_extraction_drafts_pkey PRIMARY KEY (id);


--
-- Name: rule_folders rule_folders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_folders
    ADD CONSTRAINT rule_folders_pkey PRIMARY KEY (id);


--
-- Name: rule_snapshots rule_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_snapshots
    ADD CONSTRAINT rule_snapshots_pkey PRIMARY KEY (id);


--
-- Name: rules rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rules
    ADD CONSTRAINT rules_pkey PRIMARY KEY (id);


--
-- Name: scim_tokens scim_tokens_org_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scim_tokens
    ADD CONSTRAINT scim_tokens_org_key UNIQUE (organization_id);


--
-- Name: scim_tokens scim_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scim_tokens
    ADD CONSTRAINT scim_tokens_pkey PRIMARY KEY (id);


--
-- Name: standards_by_project standards_by_project_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.standards_by_project
    ADD CONSTRAINT standards_by_project_pkey PRIMARY KEY (id);


--
-- Name: static_data_assets static_data_assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.static_data_assets
    ADD CONSTRAINT static_data_assets_pkey PRIMARY KEY (id);


--
-- Name: uploaded_files uploaded_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.uploaded_files
    ADD CONSTRAINT uploaded_files_pkey PRIMARY KEY (id);


--
-- Name: github_repositories_organization_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX github_repositories_organization_id_idx ON public.github_repositories USING btree (organization_id);


--
-- Name: group_project_grants_project_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX group_project_grants_project_id_idx ON public.group_project_grants USING btree (project_id);


--
-- Name: groups_organization_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX groups_organization_id_idx ON public.groups USING btree (organization_id);


--
-- Name: idx_audit_log_actor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_log_actor ON public.audit_log USING btree (actor_id);


--
-- Name: idx_audit_log_occurred_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_log_occurred_at ON public.audit_log USING btree (occurred_at DESC);


--
-- Name: idx_audit_log_organization; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_log_organization ON public.audit_log USING btree (organization_id);


--
-- Name: idx_bcf_comments_topic; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bcf_comments_topic ON public.bcf_comments USING btree (topic_guid);


--
-- Name: idx_bcf_topics_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bcf_topics_project ON public.bcf_topics USING btree (project_id);


--
-- Name: idx_bcf_viewpoints_topic; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bcf_viewpoints_topic ON public.bcf_viewpoints USING btree (topic_guid);


--
-- Name: idx_chat_conversations_pinned; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_conversations_pinned ON public.chat_conversations USING btree (project_id, is_pinned);


--
-- Name: idx_chat_conversations_project_updated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_conversations_project_updated ON public.chat_conversations USING btree (project_id, updated_at DESC);


--
-- Name: idx_chat_conversations_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_conversations_user ON public.chat_conversations USING btree (user_id);


--
-- Name: idx_chat_messages_conversation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_messages_conversation ON public.chat_messages USING btree (conversation_id, created_at);


--
-- Name: idx_client_documents_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_client_documents_category ON public.client_documents USING btree (category);


--
-- Name: idx_client_documents_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_client_documents_project_id ON public.client_documents USING btree (project_id);


--
-- Name: idx_client_documents_tags; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_client_documents_tags ON public.client_documents USING gin (to_tsvector('english'::regconfig, COALESCE(tags, ''::text)));


--
-- Name: idx_client_documents_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_client_documents_unique ON public.client_documents USING btree (project_id, filename);


--
-- Name: idx_client_documents_upload_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_client_documents_upload_date ON public.client_documents USING btree (upload_date);


--
-- Name: idx_document_nodes_doc_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_nodes_doc_type ON public.document_nodes USING btree (document_id, node_type);


--
-- Name: idx_document_nodes_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_nodes_document_id ON public.document_nodes USING btree (document_id);


--
-- Name: idx_document_nodes_section_path; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_nodes_section_path ON public.document_nodes USING gin (section_path jsonb_path_ops);


--
-- Name: idx_document_nodes_unique_node_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_document_nodes_unique_node_id ON public.document_nodes USING btree (document_id, node_id);


--
-- Name: idx_document_pages_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_pages_document_id ON public.document_pages USING btree (document_id);


--
-- Name: idx_document_pages_unique_page; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_document_pages_unique_page ON public.document_pages USING btree (document_id, page_number);


--
-- Name: idx_documents_cde_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_cde_state ON public.documents USING btree (cde_state);


--
-- Name: idx_documents_doc_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_doc_type ON public.documents USING btree (doc_type);


--
-- Name: idx_documents_md5_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_md5_hash ON public.documents USING btree (md5_hash);


--
-- Name: idx_documents_suitability; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_suitability ON public.documents USING btree (suitability_code);


--
-- Name: idx_evaluation_findings_human_verdict; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_evaluation_findings_human_verdict ON public.evaluation_findings USING btree (human_verdict);


--
-- Name: idx_evaluation_findings_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_evaluation_findings_project_id ON public.evaluation_findings USING btree (project_id);


--
-- Name: idx_evaluation_findings_rule_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_evaluation_findings_rule_id ON public.evaluation_findings USING btree (rule_id);


--
-- Name: idx_github_repositories_owner_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_github_repositories_owner_name ON public.github_repositories USING btree (owner, name);


--
-- Name: idx_github_repositories_url; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_github_repositories_url ON public.github_repositories USING btree (url);


--
-- Name: idx_llm_calls_context; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_calls_context ON public.llm_calls USING btree (context);


--
-- Name: idx_llm_calls_occurred_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_calls_occurred_at ON public.llm_calls USING btree (occurred_at DESC);


--
-- Name: idx_llm_calls_organization; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_calls_organization ON public.llm_calls USING btree (organization_id);


--
-- Name: idx_llm_calls_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_calls_project ON public.llm_calls USING btree (project_id);


--
-- Name: idx_llm_provider_instances_org; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_provider_instances_org ON public.llm_provider_instances USING btree (organization_id);


--
-- Name: idx_llm_task_model_assignments_org_task; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_task_model_assignments_org_task ON public.llm_task_model_assignments USING btree (organization_id, task_key);


--
-- Name: idx_model_enhancement_lineage_ifc_file_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_enhancement_lineage_ifc_file_id ON public.model_enhancement_lineage USING btree (ifc_file_id);


--
-- Name: idx_parsing_engine_instances_enabled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_parsing_engine_instances_enabled ON public.parsing_engine_instances USING btree (is_enabled);


--
-- Name: idx_parsing_engine_instances_org; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_parsing_engine_instances_org ON public.parsing_engine_instances USING btree (organization_id);


--
-- Name: idx_project_ifc_files_cde_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_ifc_files_cde_state ON public.project_ifc_files USING btree (cde_state);


--
-- Name: idx_project_ifc_files_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_ifc_files_project_id ON public.project_ifc_files USING btree (project_id);


--
-- Name: idx_project_ifc_files_project_primary; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_ifc_files_project_primary ON public.project_ifc_files USING btree (project_id, is_primary);


--
-- Name: idx_projects_analysis_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_projects_analysis_type ON public.projects USING btree (analysis_type);


--
-- Name: idx_projects_analysis_types; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_projects_analysis_types ON public.projects USING gin (analysis_types);


--
-- Name: idx_projects_cde_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_projects_cde_state ON public.projects USING btree (cde_state);


--
-- Name: idx_projects_country; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_projects_country ON public.projects USING btree (country);


--
-- Name: idx_projects_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_projects_status ON public.projects USING btree (status);


--
-- Name: idx_projects_suitability_revision; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_projects_suitability_revision ON public.projects USING btree (suitability_code, revision_code);


--
-- Name: idx_report_artifacts_ifc_file_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_report_artifacts_ifc_file_id ON public.report_artifacts USING btree (ifc_file_id);


--
-- Name: idx_report_artifacts_rule_folder; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_report_artifacts_rule_folder ON public.report_artifacts USING btree (rule_folder);


--
-- Name: idx_role_permissions_org; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_role_permissions_org ON public.role_permissions USING btree (organization_id);


--
-- Name: idx_rule_extraction_drafts_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rule_extraction_drafts_document_id ON public.rule_extraction_drafts USING btree (source_document_id);


--
-- Name: idx_rule_extraction_drafts_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rule_extraction_drafts_status ON public.rule_extraction_drafts USING btree (status);


--
-- Name: idx_rule_folders_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rule_folders_category ON public.rule_folders USING btree (category);


--
-- Name: idx_rule_snapshots_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rule_snapshots_created_at ON public.rule_snapshots USING btree (created_at DESC);


--
-- Name: idx_rule_snapshots_source_ruleset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rule_snapshots_source_ruleset_id ON public.rule_snapshots USING btree (source_ruleset_id);


--
-- Name: idx_rules_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rules_category ON public.rules USING btree (category);


--
-- Name: idx_rules_check_category_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rules_check_category_id ON public.rules USING btree (check_category_id);


--
-- Name: idx_rules_mechanism; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rules_mechanism ON public.rules USING btree (mechanism);


--
-- Name: idx_rules_needs_review; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rules_needs_review ON public.rules USING btree (needs_review);


--
-- Name: idx_rules_ruleset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rules_ruleset_id ON public.rules USING btree (ruleset_id);


--
-- Name: idx_rules_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rules_severity ON public.rules USING btree (severity);


--
-- Name: idx_rules_source_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rules_source_document_id ON public.rules USING btree (source_document_id);


--
-- Name: idx_rules_target_ifc_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rules_target_ifc_class ON public.rules USING btree (target_ifc_class);


--
-- Name: idx_scim_tokens_org; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scim_tokens_org ON public.scim_tokens USING btree (organization_id);


--
-- Name: idx_standards_by_project_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_standards_by_project_project_id ON public.standards_by_project USING btree (project_id);


--
-- Name: idx_standards_by_project_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_standards_by_project_source ON public.standards_by_project USING btree (source);


--
-- Name: idx_standards_by_project_standard_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_standards_by_project_standard_id ON public.standards_by_project USING btree (standard_id);


--
-- Name: idx_standards_by_project_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_standards_by_project_unique ON public.standards_by_project USING btree (project_id, standard_id, source);


--
-- Name: idx_uploaded_files_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_uploaded_files_hash ON public.uploaded_files USING btree (file_hash_sha256);


--
-- Name: idx_uploaded_files_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_uploaded_files_kind ON public.uploaded_files USING btree (kind);


--
-- Name: idx_uploaded_files_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_uploaded_files_project_id ON public.uploaded_files USING btree (project_id);


--
-- Name: llm_provider_instances_single_default_per_org; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX llm_provider_instances_single_default_per_org ON public.llm_provider_instances USING btree (organization_id) WHERE is_default;


--
-- Name: llm_task_model_assignments_single_default_per_task; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX llm_task_model_assignments_single_default_per_task ON public.llm_task_model_assignments USING btree (organization_id, task_key) WHERE is_default;


--
-- Name: memberships_group_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX memberships_group_id_idx ON public.memberships USING btree (group_id);


--
-- Name: memberships_organization_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX memberships_organization_id_idx ON public.memberships USING btree (organization_id);


--
-- Name: memberships_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX memberships_user_id_idx ON public.memberships USING btree (user_id);


--
-- Name: model_enhancement_lineage_project_source_sha256_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX model_enhancement_lineage_project_source_sha256_key ON public.model_enhancement_lineage USING btree (project_id, source_sha256) WHERE (source_sha256 IS NOT NULL);


--
-- Name: organization_document_grants_document_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX organization_document_grants_document_id_idx ON public.organization_document_grants USING btree (document_id);


--
-- Name: organization_invites_email_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX organization_invites_email_idx ON public.organization_invites USING btree (lower(email));


--
-- Name: organization_invites_organization_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX organization_invites_organization_id_idx ON public.organization_invites USING btree (organization_id);


--
-- Name: organization_project_grants_project_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX organization_project_grants_project_id_idx ON public.organization_project_grants USING btree (project_id);


--
-- Name: organization_ruleset_grants_ruleset_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX organization_ruleset_grants_ruleset_id_idx ON public.organization_ruleset_grants USING btree (ruleset_id);


--
-- Name: parsing_engine_instances_org_name_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX parsing_engine_instances_org_name_key ON public.parsing_engine_instances USING btree (organization_id, name) WHERE (organization_id IS NOT NULL);


--
-- Name: parsing_engine_instances_platform_name_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX parsing_engine_instances_platform_name_key ON public.parsing_engine_instances USING btree (name) WHERE (organization_id IS NULL);


--
-- Name: parsing_engine_instances_single_default_per_org; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX parsing_engine_instances_single_default_per_org ON public.parsing_engine_instances USING btree (organization_id) WHERE (is_default AND (organization_id IS NOT NULL));


--
-- Name: parsing_engine_instances_single_default_platform; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX parsing_engine_instances_single_default_platform ON public.parsing_engine_instances USING btree (is_default) WHERE (is_default AND (organization_id IS NULL));


--
-- Name: profiles_default_organization_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX profiles_default_organization_id_idx ON public.profiles USING btree (default_organization_id);


--
-- Name: profiles_email_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX profiles_email_idx ON public.profiles USING btree (lower(email));


--
-- Name: project_document_bindings_document_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX project_document_bindings_document_id_idx ON public.project_document_bindings USING btree (document_id);


--
-- Name: project_ruleset_bindings_ruleset_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX project_ruleset_bindings_ruleset_id_idx ON public.project_ruleset_bindings USING btree (ruleset_id);


--
-- Name: projects_organization_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX projects_organization_id_idx ON public.projects USING btree (organization_id);


--
-- Name: report_artifacts_project_type_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX report_artifacts_project_type_created_idx ON public.report_artifacts USING btree (project_id, artifact_type, created_at DESC);


--
-- Name: rule_folders_ruleset_id_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX rule_folders_ruleset_id_key ON public.rule_folders USING btree (lower(ruleset_id)) WHERE (ruleset_id <> ''::text);


--
-- Name: static_data_assets_asset_key_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX static_data_assets_asset_key_key ON public.static_data_assets USING btree (asset_key);


--
-- Name: uq_project_ifc_files_one_primary; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_project_ifc_files_one_primary ON public.project_ifc_files USING btree (project_id) WHERE is_primary;


--
-- Name: uq_project_naming_config_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_project_naming_config_project_id ON public.project_naming_config USING btree (project_id);


--
-- Name: uq_rule_check_categories_name_classes; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_rule_check_categories_name_classes ON public.rule_check_categories USING btree (name, target_ifc_classes);


--
-- Name: uq_rule_check_category_properties_class_prop; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_rule_check_category_properties_class_prop ON public.rule_check_category_properties USING btree (lower(target_ifc_class), lower(property_name));


--
-- Name: documents trg_documents_cde_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_documents_cde_guard BEFORE UPDATE ON public.documents FOR EACH ROW EXECUTE FUNCTION public.prevent_published_cde_mutation_generic();


--
-- Name: project_ifc_files trg_project_ifc_files_cde_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_project_ifc_files_cde_guard BEFORE UPDATE ON public.project_ifc_files FOR EACH ROW EXECUTE FUNCTION public.prevent_published_cde_mutation_generic();


--
-- Name: projects trg_projects_cde_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_projects_cde_guard BEFORE UPDATE ON public.projects FOR EACH ROW EXECUTE FUNCTION public.prevent_published_cde_mutation();


--
-- Name: audit_log audit_log_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- Name: bcf_comments bcf_comments_topic_guid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bcf_comments
    ADD CONSTRAINT bcf_comments_topic_guid_fkey FOREIGN KEY (topic_guid) REFERENCES public.bcf_topics(guid) ON DELETE CASCADE;


--
-- Name: bcf_viewpoints bcf_viewpoints_topic_guid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bcf_viewpoints
    ADD CONSTRAINT bcf_viewpoints_topic_guid_fkey FOREIGN KEY (topic_guid) REFERENCES public.bcf_topics(guid) ON DELETE CASCADE;


--
-- Name: chat_conversations chat_conversations_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_conversations
    ADD CONSTRAINT chat_conversations_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: chat_conversations chat_conversations_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_conversations
    ADD CONSTRAINT chat_conversations_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: chat_conversations chat_conversations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_conversations
    ADD CONSTRAINT chat_conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE SET NULL;


--
-- Name: chat_messages chat_messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.chat_conversations(id) ON DELETE CASCADE;


--
-- Name: client_documents client_documents_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.client_documents
    ADD CONSTRAINT client_documents_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: document_nodes document_nodes_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_nodes
    ADD CONSTRAINT document_nodes_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: document_pages document_pages_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_pages
    ADD CONSTRAINT document_pages_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: evaluation_findings evaluation_findings_ifc_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_findings
    ADD CONSTRAINT evaluation_findings_ifc_file_id_fkey FOREIGN KEY (ifc_file_id) REFERENCES public.project_ifc_files(id) ON DELETE SET NULL;


--
-- Name: evaluation_findings evaluation_findings_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_findings
    ADD CONSTRAINT evaluation_findings_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: evaluation_findings evaluation_findings_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_findings
    ADD CONSTRAINT evaluation_findings_rule_id_fkey FOREIGN KEY (rule_id) REFERENCES public.rules(id) ON DELETE SET NULL;


--
-- Name: github_repositories github_repositories_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.github_repositories
    ADD CONSTRAINT github_repositories_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: group_project_grants group_project_grants_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_project_grants
    ADD CONSTRAINT group_project_grants_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: group_project_grants group_project_grants_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_project_grants
    ADD CONSTRAINT group_project_grants_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: groups groups_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: llm_calls llm_calls_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_calls
    ADD CONSTRAINT llm_calls_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- Name: llm_calls llm_calls_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_calls
    ADD CONSTRAINT llm_calls_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE SET NULL;


--
-- Name: llm_provider_instances llm_provider_instances_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_provider_instances
    ADD CONSTRAINT llm_provider_instances_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: llm_task_model_assignments llm_task_model_assignments_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_task_model_assignments
    ADD CONSTRAINT llm_task_model_assignments_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: llm_task_model_assignments llm_task_model_assignments_provider_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_task_model_assignments
    ADD CONSTRAINT llm_task_model_assignments_provider_instance_id_fkey FOREIGN KEY (provider_instance_id) REFERENCES public.llm_provider_instances(id) ON DELETE CASCADE;


--
-- Name: memberships memberships_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT memberships_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE SET NULL;


--
-- Name: memberships memberships_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT memberships_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: memberships memberships_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT memberships_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: model_enhancement_lineage model_enhancement_lineage_ifc_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_enhancement_lineage
    ADD CONSTRAINT model_enhancement_lineage_ifc_file_id_fkey FOREIGN KEY (ifc_file_id) REFERENCES public.project_ifc_files(id) ON DELETE SET NULL;


--
-- Name: model_enhancement_lineage model_enhancement_lineage_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_enhancement_lineage
    ADD CONSTRAINT model_enhancement_lineage_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: model_enhancement_version_counters model_enhancement_version_counters_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_enhancement_version_counters
    ADD CONSTRAINT model_enhancement_version_counters_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: organization_document_grants organization_document_grants_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_document_grants
    ADD CONSTRAINT organization_document_grants_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: organization_document_grants organization_document_grants_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_document_grants
    ADD CONSTRAINT organization_document_grants_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: organization_invites organization_invites_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_invites
    ADD CONSTRAINT organization_invites_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: organization_project_grants organization_project_grants_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_project_grants
    ADD CONSTRAINT organization_project_grants_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: organization_project_grants organization_project_grants_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_project_grants
    ADD CONSTRAINT organization_project_grants_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: organization_ruleset_grants organization_ruleset_grants_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_ruleset_grants
    ADD CONSTRAINT organization_ruleset_grants_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: parsing_engine_instances parsing_engine_instances_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parsing_engine_instances
    ADD CONSTRAINT parsing_engine_instances_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: profiles profiles_default_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_default_organization_id_fkey FOREIGN KEY (default_organization_id) REFERENCES public.organizations(id);


--
-- Name: profiles profiles_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: project_document_bindings project_document_bindings_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_document_bindings
    ADD CONSTRAINT project_document_bindings_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: project_document_bindings project_document_bindings_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_document_bindings
    ADD CONSTRAINT project_document_bindings_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_ifc_files project_ifc_files_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_ifc_files
    ADD CONSTRAINT project_ifc_files_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_naming_config project_naming_config_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_naming_config
    ADD CONSTRAINT project_naming_config_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_ruleset_bindings project_ruleset_bindings_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_ruleset_bindings
    ADD CONSTRAINT project_ruleset_bindings_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: projects projects_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: report_artifacts report_artifacts_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_artifacts
    ADD CONSTRAINT report_artifacts_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE SET NULL;


--
-- Name: report_artifacts report_artifacts_ifc_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_artifacts
    ADD CONSTRAINT report_artifacts_ifc_file_id_fkey FOREIGN KEY (ifc_file_id) REFERENCES public.project_ifc_files(id) ON DELETE SET NULL;


--
-- Name: report_artifacts report_artifacts_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_artifacts
    ADD CONSTRAINT report_artifacts_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: rule_check_category_properties rule_check_category_properties_check_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_check_category_properties
    ADD CONSTRAINT rule_check_category_properties_check_category_id_fkey FOREIGN KEY (check_category_id) REFERENCES public.rule_check_categories(id) ON DELETE CASCADE;


--
-- Name: rule_extraction_drafts rule_extraction_drafts_promoted_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_extraction_drafts
    ADD CONSTRAINT rule_extraction_drafts_promoted_rule_id_fkey FOREIGN KEY (promoted_rule_id) REFERENCES public.rules(id) ON DELETE SET NULL;


--
-- Name: rule_extraction_drafts rule_extraction_drafts_source_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_extraction_drafts
    ADD CONSTRAINT rule_extraction_drafts_source_document_id_fkey FOREIGN KEY (source_document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: rules rules_check_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rules
    ADD CONSTRAINT rules_check_category_id_fkey FOREIGN KEY (check_category_id) REFERENCES public.rule_check_categories(id) ON DELETE SET NULL;


--
-- Name: rules rules_source_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rules
    ADD CONSTRAINT rules_source_document_id_fkey FOREIGN KEY (source_document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: scim_tokens scim_tokens_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scim_tokens
    ADD CONSTRAINT scim_tokens_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: standards_by_project standards_by_project_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.standards_by_project
    ADD CONSTRAINT standards_by_project_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: uploaded_files uploaded_files_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.uploaded_files
    ADD CONSTRAINT uploaded_files_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: keep_alive Allow anon insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Allow anon insert" ON public.keep_alive FOR INSERT TO anon WITH CHECK (true);


--
-- Name: app_settings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.app_settings ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

--
-- Name: bcf_comments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bcf_comments ENABLE ROW LEVEL SECURITY;

--
-- Name: bcf_topics; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bcf_topics ENABLE ROW LEVEL SECURITY;

--
-- Name: bcf_viewpoints; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bcf_viewpoints ENABLE ROW LEVEL SECURITY;

--
-- Name: chat_conversations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.chat_conversations ENABLE ROW LEVEL SECURITY;

--
-- Name: chat_messages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

--
-- Name: client_documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.client_documents ENABLE ROW LEVEL SECURITY;

--
-- Name: document_nodes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.document_nodes ENABLE ROW LEVEL SECURITY;

--
-- Name: document_pages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.document_pages ENABLE ROW LEVEL SECURITY;

--
-- Name: documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

--
-- Name: evaluation_findings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.evaluation_findings ENABLE ROW LEVEL SECURITY;

--
-- Name: github_repositories; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.github_repositories ENABLE ROW LEVEL SECURITY;

--
-- Name: group_project_grants; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_project_grants ENABLE ROW LEVEL SECURITY;

--
-- Name: groups; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.groups ENABLE ROW LEVEL SECURITY;

--
-- Name: issue_history; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.issue_history ENABLE ROW LEVEL SECURITY;

--
-- Name: keep_alive; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.keep_alive ENABLE ROW LEVEL SECURITY;

--
-- Name: llm_calls; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.llm_calls ENABLE ROW LEVEL SECURITY;

--
-- Name: llm_provider_instances; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.llm_provider_instances ENABLE ROW LEVEL SECURITY;

--
-- Name: llm_task_model_assignments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.llm_task_model_assignments ENABLE ROW LEVEL SECURITY;

--
-- Name: memberships; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;

--
-- Name: model_enhancement_lineage; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.model_enhancement_lineage ENABLE ROW LEVEL SECURITY;

--
-- Name: model_enhancement_version_counters; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.model_enhancement_version_counters ENABLE ROW LEVEL SECURITY;

--
-- Name: organization_document_grants; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organization_document_grants ENABLE ROW LEVEL SECURITY;

--
-- Name: organization_invites; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organization_invites ENABLE ROW LEVEL SECURITY;

--
-- Name: organization_project_grants; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organization_project_grants ENABLE ROW LEVEL SECURITY;

--
-- Name: organization_ruleset_grants; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organization_ruleset_grants ENABLE ROW LEVEL SECURITY;

--
-- Name: organizations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;

--
-- Name: parsing_engine_instances; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.parsing_engine_instances ENABLE ROW LEVEL SECURITY;

--
-- Name: profiles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

--
-- Name: project_document_bindings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.project_document_bindings ENABLE ROW LEVEL SECURITY;

--
-- Name: project_ifc_files; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.project_ifc_files ENABLE ROW LEVEL SECURITY;

--
-- Name: project_naming_config; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.project_naming_config ENABLE ROW LEVEL SECURITY;

--
-- Name: project_ruleset_bindings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.project_ruleset_bindings ENABLE ROW LEVEL SECURITY;

--
-- Name: projects; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;

--
-- Name: report_artifacts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.report_artifacts ENABLE ROW LEVEL SECURITY;

--
-- Name: role_permissions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.role_permissions ENABLE ROW LEVEL SECURITY;

--
-- Name: rule_check_categories; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rule_check_categories ENABLE ROW LEVEL SECURITY;

--
-- Name: rule_check_category_properties; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rule_check_category_properties ENABLE ROW LEVEL SECURITY;

--
-- Name: rule_extraction_drafts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rule_extraction_drafts ENABLE ROW LEVEL SECURITY;

--
-- Name: rule_folders; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rule_folders ENABLE ROW LEVEL SECURITY;

--
-- Name: rule_snapshots; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rule_snapshots ENABLE ROW LEVEL SECURITY;

--
-- Name: rules; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rules ENABLE ROW LEVEL SECURITY;

--
-- Name: scim_tokens; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.scim_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: standards_by_project; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.standards_by_project ENABLE ROW LEVEL SECURITY;

--
-- Name: static_data_assets; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.static_data_assets ENABLE ROW LEVEL SECURITY;

--
-- Name: uploaded_files; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.uploaded_files ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--


