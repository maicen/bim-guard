-- Supabase Migration: 20260831005000_add_iso19650_naming_config
-- Creates project_naming_config table for ISO 19650 naming convention management
-- Naming structure: PROJ-ORG-PH-LV-TYP-RL-CL-NUM-SUIT-REV.ext
-- References: BIMicon guidelines, ISO 19650-1:2018, ISO 19650-2:2018

CREATE TABLE IF NOT EXISTS public.project_naming_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  
  -- Section 1: Project Code & Originator (PROJ-ORG)
  project_code TEXT NOT NULL DEFAULT '',
  originator_code TEXT NOT NULL DEFAULT '',
  
  -- Section 2: Phase Code (PH) — Scheme Design, Design Development, etc.
  phase_code TEXT NOT NULL DEFAULT 'SD',
  
  -- Section 3: Level/Location Codes (LV) — configurable library
  -- JSON array: [{ "code": "ZZ", "label": "All levels", "removable": false }, ...]
  level_location_codes JSONB DEFAULT '[
    {"code": "ZZ", "label": "All levels", "removable": false},
    {"code": "B02", "label": "Basement 2", "removable": true},
    {"code": "B01", "label": "Basement 1", "removable": true},
    {"code": "GF", "label": "Ground Floor", "removable": false},
    {"code": "01", "label": "Level 01", "removable": false},
    {"code": "02", "label": "Level 02", "removable": true},
    {"code": "03", "label": "Level 03", "removable": true},
    {"code": "04", "label": "Level 04", "removable": true},
    {"code": "05", "label": "Level 05", "removable": true},
    {"code": "RF", "label": "Roof", "removable": false},
    {"code": "ME", "label": "Mezzanine", "removable": true}
  ]',
  
  -- Section 4: Type Codes (TYP) — DR, M3, RI, CM, etc.
  -- JSON array: [{ "code": "DR", "label": "2D Drawing", "removable": false }, ...]
  type_codes JSONB DEFAULT '[
    {"code": "DR", "label": "2D Drawing", "removable": false},
    {"code": "M3", "label": "3D Model", "removable": false},
    {"code": "M2", "label": "2D Model", "removable": true},
    {"code": "RI", "label": "Request for Information", "removable": true},
    {"code": "RP", "label": "Report", "removable": true},
    {"code": "CM", "label": "Combined Model", "removable": true},
    {"code": "SH", "label": "Schedule", "removable": true},
    {"code": "SP", "label": "Specification", "removable": true},
    {"code": "AF", "label": "Animation File", "removable": true}
  ]',
  
  -- Section 5: Role/Discipline Codes (RL) — A, E, H, S, C, etc.
  -- JSON array: [{ "code": "A", "label": "Architect", "removable": false }, ...]
  role_discipline_codes JSONB DEFAULT '[
    {"code": "A", "label": "Architect", "removable": false},
    {"code": "E", "label": "Electrical Engineer", "removable": false},
    {"code": "H", "label": "HVAC / Mechanical", "removable": false},
    {"code": "S", "label": "Structural Engineer", "removable": false},
    {"code": "C", "label": "Civil Engineer", "removable": true},
    {"code": "L", "label": "Landscape Architect", "removable": true},
    {"code": "B", "label": "Building Surveyor", "removable": true},
    {"code": "D", "label": "Drainage Engineer", "removable": true},
    {"code": "F", "label": "Facilities Manager", "removable": true},
    {"code": "G", "label": "Geotechnical Engineer", "removable": true},
    {"code": "I", "label": "Interior Designer", "removable": true},
    {"code": "K", "label": "Kitchen Equipment", "removable": true},
    {"code": "SH", "label": "Specialist MEP", "removable": true}
  ]',
  
  -- Section 6: Classification Codes (CL) — A01, B01, etc. (usually discipline-specific)
  -- JSON object: { "A": ["A01", "A02", ...], "E": ["E01", "E02", ...], ... }
  classification_codes JSONB DEFAULT '{
    "A": ["A01", "A02", "A03"],
    "E": ["E01", "E02", "E03"],
    "H": ["H01", "H02", "H03"],
    "S": ["S01", "S02", "S03"],
    "C": ["C01", "C02", "C03"],
    "default": ["001", "002", "003"]
  }',
  
  -- Section 7: Suitability / CDE Status Codes (SUIT)
  -- JSON object: { "S0": "Work in progress", "S1": "Suitable for coordination", ... }
  cde_status_mapping JSONB DEFAULT '{
    "S0": "Work in progress",
    "S1": "Suitable for coordination",
    "S2": "Suitable for information",
    "S3": "Suitable for review",
    "A": "Approved/Accepted",
    "B": "Partial sign off",
    "S7": "Archived / superseded"
  }',
  
  -- Section 8: Revision Format (REV)
  revision_format TEXT NOT NULL DEFAULT 'Rev##',
  
  -- Section 9: Active Naming Convention
  -- Enum: 'iso19650-1', 'iso19650-2', 'simple', 'descriptive', 'uniclass', 'custom'
  active_convention TEXT NOT NULL DEFAULT 'iso19650-1',
  
  -- Custom naming format string for advanced users
  -- E.g., "{project}_{originator}_{level}_{type}_{discipline}_{num}"
  custom_format_string TEXT,
  
  -- Metadata
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  
  UNIQUE(project_id)
);

-- Enable Row Level Security
ALTER TABLE public.project_naming_config ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can access naming config for their own projects
CREATE POLICY "Users can access naming config for their projects"
  ON public.project_naming_config
  FOR ALL
  USING (
    project_id IN (
      SELECT id FROM public.projects WHERE user_id = auth.uid()
    )
  );

-- Create index for fast lookups
CREATE INDEX idx_project_naming_config_project_id 
  ON public.project_naming_config(project_id);

-- Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_project_naming_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_project_naming_config_updated_at
  BEFORE UPDATE ON public.project_naming_config
  FOR EACH ROW
  EXECUTE FUNCTION update_project_naming_config_timestamp();

-- Comment for clarity
COMMENT ON TABLE public.project_naming_config IS 
'ISO 19650 naming convention configuration per project. 
Stores project metadata, code libraries, and naming convention preferences.
Structure: PROJ-ORG-PH-LV-TYP-RL-CL-NUM-SUIT-REV.ext';
