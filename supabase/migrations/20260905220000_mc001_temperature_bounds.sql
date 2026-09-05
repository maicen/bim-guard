-- MC-001 temperature classes: give them the numeric bounds they never had.
--
-- The six MC-001.TEMP.* rules state their band as a human range string
-- ("25-45°C") and nothing else. classify_temperature
-- (app/engines/bimguard_mic_engine.py) compares against t_min/t_max, and
-- corrosion_rule_catalog coerced the absent values to 0.0, so
-- "t_min <= t < t_max" was false for every real temperature and every element
-- fell through to the T4_SAFE_HOT fallback -- risk 0.05, the LOWEST of the
-- six. Water sitting at 35 °C in the middle of the Legionella danger zone
-- scored as safely hot.
--
-- The numbers below are transcriptions of each rule's own published range
-- string, not new thresholds. No risk value, weight or band boundary changes.
--
--   T0_COLD       "< 20°C"      -273.15 .. 20     open below -> absolute zero
--   T1_MARGINAL   "20-25°C"           20 .. 25
--   T2_DANGER     "25-45°C"           25 .. 45
--   T3_TOLERABLE  "45-55°C"           45 .. 55
--   T4_SAFE_HOT   "> 55°C"            55 .. 1000  open above -> beyond any
--                                                 building service temperature
--   T5_UNKNOWN    "Unknown"     deliberately untouched: it is the absence of a
--                               temperature, selected by name rather than by
--                               comparison, so bounds would be meaningless.
--
-- Intervals are half-open [t_min, t_max) as the engine evaluates them, so a
-- shared endpoint belongs to the warmer class and no temperature matches two
-- rows.
--
-- `parameters` is a text column holding JSON (see
-- supabase/migrations/20260721135500_init_core_public_tables.sql), hence the
-- ::jsonb round trip. The `||` merge adds the two keys and leaves every other
-- key -- including the "range" string -- in place.
--
-- Idempotent: re-running rewrites the same two keys to the same values. The
-- WHERE clause additionally skips rows already carrying both, so a second run
-- touches nothing and does not churn updated_at.

update public.rules AS r
   set parameters = (
           coalesce(nullif(r.parameters, ''), '{}')::jsonb
           || jsonb_build_object('t_min', b.t_min, 't_max', b.t_max)
       )::text,
       updated_at = to_char(now() at time zone 'utc',
                            'YYYY-MM-DD"T"HH24:MI:SS+00:00')
  from (values
            ('MC-001.TEMP.T0_COLD',      -273.15,   20.0),
            ('MC-001.TEMP.T1_MARGINAL',     20.0,   25.0),
            ('MC-001.TEMP.T2_DANGER',       25.0,   45.0),
            ('MC-001.TEMP.T3_TOLERABLE',    45.0,   55.0),
            ('MC-001.TEMP.T4_SAFE_HOT',     55.0, 1000.0)
       ) as b(reference, t_min, t_max)
 where r.reference = b.reference
   and r.rule_type = 'temperature_class'
   and (
           coalesce(nullif(r.parameters, ''), '{}')::jsonb -> 't_min'
             is distinct from to_jsonb(b.t_min)
        or coalesce(nullif(r.parameters, ''), '{}')::jsonb -> 't_max'
             is distinct from to_jsonb(b.t_max)
       );
