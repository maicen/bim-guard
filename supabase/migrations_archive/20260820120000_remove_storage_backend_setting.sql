begin;

delete from public.app_settings
where key = 'BIM_GUARD_STORAGE_BACKEND';

commit;