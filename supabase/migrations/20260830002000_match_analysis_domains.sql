-- Migration: Update project analysis domains to Arch, Piping, seismic
-- Unifies project analysis domains with rules categories: 'Arch', 'Piping', 'seismic'.

-- 1. Drop existing constraint first
ALTER TABLE public.projects DROP CONSTRAINT IF EXISTS valid_analysis_type;

-- 2. Migrate existing project rows to exact rules categories
UPDATE public.projects
SET analysis_type = CASE
    WHEN analysis_type IN ('Architectural', 'Architecture', 'arch', 'Arch') THEN 'Arch'
    WHEN analysis_type IN ('Piping (Corrosive)', 'piping', 'corrosion', 'Piping') THEN 'Piping'
    WHEN analysis_type IN ('Seismic', 'Halo', 'seismic', 'Piping (Seismic)') THEN 'seismic'
    ELSE analysis_type
END;

-- 3. Update default to 'Arch'
ALTER TABLE public.projects ALTER COLUMN analysis_type SET DEFAULT 'Arch';

-- 4. Re-add constraint with canonical names (plus legacy aliases for backwards compatibility)
ALTER TABLE public.projects
    ADD CONSTRAINT valid_analysis_type
    CHECK (analysis_type IN ('Arch', 'Piping', 'seismic', 'Architectural', 'Seismic', 'Architecture', 'Piping (Corrosive)', 'Halo'));

COMMENT ON COLUMN public.projects.analysis_type IS
    'Target analysis domain matching rules categories: Arch, Piping, or seismic.';
