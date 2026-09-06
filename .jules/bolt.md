## 2026-09-06 - Python In-Memory Table Scans
**Learning:** Found a severe anti-pattern (`find_row_by_field`) being used to fetch records by hash. The utility fetched ALL rows from Supabase into local memory to perform Python-level O(N) filtering, rather than using DB-level filtering.
**Action:** Replace all such `table.rows` iterations with `table.rows_where` to push predicate evaluation down to the database and eliminate the memory bottleneck.
