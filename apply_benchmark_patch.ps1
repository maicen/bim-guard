# ============================================================
# BIMGUARD - Apply Session 2 benchmarking patch + tidy up
# Run from anywhere: right-click > Run with PowerShell,
# or:  powershell -ExecutionPolicy Bypass -File apply_benchmark_patch.ps1
# ============================================================

$repo   = "D:\Zigurat Masters\bim-guard"
$backup = "D:\Zigurat Masters\_backups\session2-benchmarking"

Set-Location $repo
Write-Host "=== 1. Current location and branch ===" -ForegroundColor Cyan
git status --short --branch

# --- Ensure we are on the benchmarking branch ---------------
Write-Host "`n=== 2. Switching to claude/thesis-performance-benchmarking ===" -ForegroundColor Cyan
git checkout claude/thesis-performance-benchmarking
if ($LASTEXITCODE -ne 0) {
    Write-Host "Branch checkout FAILED - stopping." -ForegroundColor Red
    exit 1
}

# --- Find the patch file (handles both possible names) ------
Write-Host "`n=== 3. Locating patch file ===" -ForegroundColor Cyan
$patch = Get-ChildItem -Path $repo -Filter "*benchmark*work*.patch" | Select-Object -First 1
if (-not $patch) {
    Write-Host "No patch file found in $repo - download it from the Session 2 chat first." -ForegroundColor Red
    exit 1
}
Write-Host "Found: $($patch.Name)"

# --- Apply the patch ----------------------------------------
Write-Host "`n=== 4. Applying patch with git am ===" -ForegroundColor Cyan
git am $patch.FullName
if ($LASTEXITCODE -ne 0) {
    Write-Host "git am FAILED - trying fallback: git am --abort, then git apply" -ForegroundColor Yellow
    git am --abort 2>$null
    git apply --stat $patch.FullName
    git apply $patch.FullName
    if ($LASTEXITCODE -ne 0) {
        Write-Host "git apply also FAILED - stopping. Show this output to Claude." -ForegroundColor Red
        exit 1
    }
    git add -A
    git commit -m "Session 2: Halo benchmarking, Expert Review process, SS316 case study (applied via git apply)"
}

# --- Verify -------------------------------------------------
Write-Host "`n=== 5. Verifying commits ===" -ForegroundColor Cyan
git log -3 --oneline

Write-Host "`n=== 6. New files in docs/benchmarks (sample) ===" -ForegroundColor Cyan
Get-ChildItem -Path "docs\benchmarks" -ErrorAction SilentlyContinue | Select-Object -First 10 Name

# --- Move loose duplicates to backup ------------------------
Write-Host "`n=== 7. Moving loose duplicate files to backup ===" -ForegroundColor Cyan
New-Item -ItemType Directory -Path $backup -Force | Out-Null

$looseFiles = @(
    "performance_benchmark.py",
    "ss316_feedback_loop_case_study.md",
    "expert_review_process.md",
    "halo_performance_analysis.md",
    $patch.Name
)

foreach ($f in $looseFiles) {
    $src = Join-Path $repo $f
    if (Test-Path $src) {
        # Only move the root-level copy, never anything the patch placed in subfolders
        Move-Item -Path $src -Destination $backup -Force
        Write-Host "  moved: $f"
    } else {
        Write-Host "  not in root (ok): $f" -ForegroundColor DarkGray
    }
}

# --- Final state --------------------------------------------
Write-Host "`n=== 8. Final git status ===" -ForegroundColor Cyan
git status --short --branch

Write-Host "`n=== DONE ===" -ForegroundColor Green
Write-Host "If step 5 shows the two new commits (benchmark harness + examination gaps),"
Write-Host "the work is secured locally. Push to GitHub when access is restored with:"
Write-Host "  git push -u origin claude/thesis-performance-benchmarking" -ForegroundColor Yellow
