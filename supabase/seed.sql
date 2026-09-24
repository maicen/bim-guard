-- Seed data applied by `supabase start` / `supabase db reset` to the local
-- development database only (never run against the hosted project).
--
-- The app uploads/downloads via a Supabase Storage bucket named by
-- SUPABASE_STORAGE_BUCKET (defaults to "bim-guard-artifacts" — see
-- app/services/object_storage.py), but bucket creation isn't part of any
-- migration since it's Storage config, not a schema change. The hosted
-- project already has this bucket created manually; a fresh local stack
-- needs it created here so uploads work out of the box.
insert into storage.buckets (id, name, public)
values ('bim-guard-artifacts', 'bim-guard-artifacts', false)
on conflict (id) do nothing;
