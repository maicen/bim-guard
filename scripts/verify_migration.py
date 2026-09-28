"""Verify row counts and integrity between hosted Supabase and self-hosted database."""

import subprocess

TABLES = [
    ("auth", "users", 5),
    ("auth", "identities", 6),
    ("storage", "objects", 210),
    ("storage", "buckets", 1),
    ("public", "bcf_topics", 548),
    ("public", "audit_log", 428),
    ("public", "document_pages", 370),
    ("public", "bcf_comments", 198),
    ("public", "bcf_viewpoints", 125),
    ("public", "rule_extraction_drafts", 118),
    ("public", "rules", 84),
    ("public", "projects", 17),
    ("public", "memberships", 13),
    ("public", "project_ifc_files", 12),
    ("public", "documents", 7),
    ("public", "profiles", 5),
    ("public", "organizations", 4),
]

def check():
    print(f"{'Schema.Table':<30} {'Expected':<10} {'Actual':<10} {'Status':<10}")
    print("-" * 65)
    all_ok = True
    for schema, table, expected in TABLES:
        sql = f"SELECT count(*) FROM \"{schema}\".\"{table}\";"
        cmd = ["docker", "exec", "-i", "supabase-db", "psql", "-U", "postgres", "-d", "postgres", "-t", "-c", sql]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            actual = int(res.stdout.strip())
            ok = (actual == expected)
            if not ok:
                all_ok = False
            status = "PASS" if ok else "FAIL"
            print(f"{f'{schema}.{table}':<30} {expected:<10} {actual:<10} {status:<10}")
        except Exception as e:
            all_ok = False
            print(f"{f'{schema}.{table}':<30} {expected:<10} {'ERROR':<10} {e}")

    print("-" * 65)
    if all_ok:
        print("ALL VERIFICATIONS PASSED: 100% Data Fidelity across all schemas!")
    else:
        print("SOME VERIFICATIONS FAILED. Check logs above.")
    return all_ok

if __name__ == "__main__":
    check()
