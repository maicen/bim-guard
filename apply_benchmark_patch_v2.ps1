# ============================================================
# BIMGUARD - Fix patch application (v2)
# 1. Commits Session 1 work-in-progress first (protects it)
# 2. Clears stale git am state
# 3. Moves colliding loose files to backup
# 4. Applies patch EXCLUDING uv.lock + pyproject.toml (conflict)
# 5. Regenerates lock with uv afterwards
# ============================================================

$repo   = "D:\Zigurat Masters\bim-guard"
$backup = "D:\Zigurat Masters\_backups\session2-benchmarking"

Set-Location $repo
New-Item -ItemType Directory -Path $backup -Force | Out-Null

# --- 0. Clear stale rebase/am state -------------------------
Write-Host "=== 0. Clearing stale git am/rebase state ===" -ForegroundColor Cyan
git am --abort 2>$null
if (Test-Path ".git\rebase-apply") {
    Remove-Item ".git\rebase-apply" -Recurse -Force
    Write-Host "Removed stale .git\rebase-apply"
}

# --- 1. COMMIT Session 1 work-in-progress FIRST -------------
Write-Host "`n=== 1. Committing Session 1 work (protecting it) ===" -ForegroundColor Cyan
git add app/ tests/ data/rulesets/ .python-version pyproject.toml uv.lock
git commit -m "Session 1 WIP: Issue #17 LLM standardization, piping producer + fixtures, comparator tests, MM-001 matrix draft"
git log -1 --oneline

# --- 2. Move colliding loose files to backup ----------------
Write-Host "`n=== 2. Moving loose duplicate files out of the way ===" -ForegroundColor Cyan
$looseFiles = @(
    "performance_benchmark.py",
    "ss316_feedback_loop_case_study.md",
    "expert_review_process.md",
    "halo_performance_analysis.md"
)
foreach ($f in $looseFiles) {
    if (Test-Path (Join-Path $repo $f)) {
        Copy-Item (Join-Path $repo $f) $backup -Force
        Remove-Item (Join-Path $repo $f) -Force
        Write-Host "  backed up + removed from root: $f"
    }
}

# --- 3. Apply patch, excluding the conflicting lock files ---
Write-Host "`n=== 3. Applying patch (excluding uv.lock, pyproject.toml) ===" -ForegroundColor Cyan
$patch = Get-ChildItem -Path $repo -Filter "*benchmark*work*.patch" | Select-Object -First 1
if (-not $patch) { Write-Host "Patch not found!" -ForegroundColor Red; exit 1 }

git apply --exclude=uv.lock --exclude=pyproject.toml --whitespace=nowarn $patch.FullName
if ($LASTEXITCODE -ne 0) {
    Write-Host "git apply still failed. Trying 3-way merge..." -ForegroundColor Yellow
    git apply --3way --exclude=uv.lock --exclude=pyproject.toml --whitespace=nowarn $patch.FullName
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED - show this output to Claude." -ForegroundColor Red
        exit 1
    }
}
Write-Host "Patch content applied." -ForegroundColor Green

# --- 4. Add benchmark dependencies that the excluded pyproject diff carried
Write-Host "`n=== 4. Adding benchmark dependencies via uv (psutil, matplotlib) ===" -ForegroundColor Cyan
uv add psutil matplotlib
# (If the patch needed other deps, performance_benchmark.py will say so when run.)

# --- 5. Commit the Session 2 work ---------------------------
Write-Host "`n=== 5. Committing Session 2 benchmarking work ===" -ForegroundColor Cyan
git add -A
git commit -m "Session 2: Halo performance benchmark harness + results, Expert Review process, SS316 LLM feedback case study, thesis revisions"

# --- 6. Verify ----------------------------------------------
Write-Host "`n=== 6. Final verification ===" -ForegroundColor Cyan
git log -3 --oneline
Write-Host ""
Get-ChildItem "docs\benchmarks" -ErrorAction SilentlyContinue | Select-Object Name

# --- 7. Tidy remaining loose files --------------------------
Write-Host "`n=== 7. Backing up patch file ===" -ForegroundColor Cyan
Copy-Item $patch.FullName $backup -Force
Remove-Item $patch.FullName -Force
Write-Host "Patch archived to $backup"

Write-Host "`n=== 8. Final status ===" -ForegroundColor Cyan
git status --short --branch

Write-Host "`n=== DONE ===" -ForegroundColor Green
Write-Host "Both sessions' work is now committed locally on this branch."
Write-Host "Push when GitHub access is restored:"
Write-Host "  git push -u origin claude/thesis-performance-benchmarking" -ForegroundColor Yellow
