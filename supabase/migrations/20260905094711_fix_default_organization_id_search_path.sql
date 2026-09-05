-- Pin search_path on default_organization_id() -- the advisor flags a
-- mutable search_path as a security lint (a caller-controlled search_path
-- could shadow "organizations" with another schema's table of that name).

alter function public.default_organization_id() set search_path = public;
