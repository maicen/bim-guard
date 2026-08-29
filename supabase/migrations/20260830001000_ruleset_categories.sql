-- Migration: Add category column to public.rule_folders and public.rules
-- Date: 2026-08-30
-- Purpose: Categorize all rulesets into Arch, Piping, or seismic
--
-- Idempotent: safe to re-run.

BEGIN;

-- 1. Add category column to rule_folders
ALTER TABLE public.rule_folders
    ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'Arch';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'valid_rule_folder_category'
          AND conrelid = 'public.rule_folders'::regclass
    ) THEN
        ALTER TABLE public.rule_folders
            ADD CONSTRAINT valid_rule_folder_category
            CHECK (category IN ('Arch', 'Piping', 'seismic'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_rule_folders_category ON public.rule_folders(category);

-- 2. Add category column to rules
ALTER TABLE public.rules
    ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'Arch';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'valid_rule_category_domain'
          AND conrelid = 'public.rules'::regclass
    ) THEN
        ALTER TABLE public.rules
            ADD CONSTRAINT valid_rule_category_domain
            CHECK (category IN ('Arch', 'Piping', 'seismic'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_rules_category ON public.rules(category);

-- 3. Update existing rule_folders with appropriate categories
UPDATE public.rule_folders
SET category = 'Piping'
WHERE ruleset_id IN ('BIMGUARD-GC-001', 'BIMGUARD-CC-001', 'BIMGUARD-MC-001')
   OR mechanism_scope IN ('GC-001', 'CC-001', 'MC-001');

UPDATE public.rule_folders
SET category = 'Arch'
WHERE ruleset_id IN ('BUILDING-CODE-PART9', 'BUILDING-CODE-PART9-EXT', 'OBC-PART9', 'OBC-PART9-EXT', 'door_mock', 'staits-rules-02', 'test_folder', 'test')
   OR mechanism_scope IN ('CODE', 'OBC', 'IFC', '');

-- 4. Ensure seismic ruleset folder exists
INSERT INTO public.rule_folders (
    ruleset_id,
    display_name,
    description,
    mechanism_scope,
    category,
    created_at,
    updated_at
)
VALUES (
    'BIMGUARD-SB-001',
    'BIMGUARD-SB-001 (Seismic Halo)',
    'Blue Halo seismic bracing clearance and buffer volume requirements per EN 1998-1 / DIN 4149',
    'SEISMIC',
    'seismic',
    NOW()::text,
    NOW()::text
)
ON CONFLICT ((lower(ruleset_id))) WHERE ruleset_id <> ''
DO UPDATE SET
    category = 'seismic',
    mechanism_scope = 'SEISMIC',
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description;

-- 5. Update existing rules to match their ruleset category
UPDATE public.rules
SET category = 'Piping'
WHERE ruleset_id IN ('BIMGUARD-GC-001', 'BIMGUARD-CC-001', 'BIMGUARD-MC-001')
   OR mechanism IN ('GC-001', 'CC-001', 'MC-001');

UPDATE public.rules
SET category = 'seismic'
WHERE ruleset_id IN ('BIMGUARD-SB-001', 'SB-001')
   OR mechanism IN ('SEISMIC', 'SB-001');

UPDATE public.rules
SET category = 'Arch'
WHERE ruleset_id IN ('BUILDING-CODE-PART9', 'BUILDING-CODE-PART9-EXT', 'OBC-PART9', 'OBC-PART9-EXT', 'door_mock', 'staits-rules-02', 'test_folder', 'test')
   OR mechanism IN ('CODE', 'OBC', 'IFC');

COMMENT ON COLUMN public.rule_folders.category IS
    'Ruleset category: Arch (architectural building code), Piping (MEP corrosion), or seismic (Blue Halo)';
COMMENT ON COLUMN public.rules.category IS
    'Domain category: Arch (architectural building code), Piping (MEP corrosion), or seismic (Blue Halo)';

COMMIT;
