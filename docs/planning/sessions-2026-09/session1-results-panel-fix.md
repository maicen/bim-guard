# TASK: Fix Results Panel Rendering (Pre-existing Blocker)

## Context
Analysis runs successfully (backend returns 200 in ~4ms, cache works, data is correct). But the results panel never renders — no table, no stat cards, DOM unchanged. This blocks user visibility even though the underlying data pipeline is correct.

**Architecture:** Svelte 5 frontend calls `/api/analyze/upload` → receives results JSON → should render `ResultsPanel.svelte`. Currently: network succeeds, component doesn't appear.

**Known leads (unverified):**
- `ScanEye` used in `IssueTable.svelte:297` but never imported
- 51 svelte-check errors across 14 files (structural Svelte issues)

---

## STEP 1: Establish Baseline — Confirm Issue in Browser

```bash
cd D:\Zigurat Masters\bim-guard
python main.py
# Browser: http://localhost:5173
# Upload a test IFC → click Analyze
# Open DevTools (F12)
```

**Observe:**
- Network tab: POST /api/analyze/upload returns 200, response body shows full results JSON
- Console tab: Any errors? (Should be empty or only warnings)
- DOM: `<div id="app">` exists but no `ResultsPanel` component renders
- Measure: `document.body.innerText.length` before and after analyze (should change)

**Report:** Screenshot of Network tab (200 response) + Console (errors if any) + DOM state

---

## STEP 2: Inspect Component Lifecycle

**File:** `frontend/src/lib/components/ResultsPanel.svelte`

Find the `<script>` block:

```bash
grep -n "export let\|onMount\|$:" frontend/src/lib/components/ResultsPanel.svelte | head -20
```

You should see:
```
export let results
onMount
$: if (results)
```

**Check:** Does the component receive `results` prop as reactive data? Or does it fetch its own?

---

## STEP 3: Trace Prop Flow — Where Does ResultsPanel Get Results?

**File:** `frontend/src/routes/AnalyzeView.svelte`

Find where ResultsPanel is used:

```bash
grep -n "ResultsPanel\|import.*ResultsPanel" frontend/src/routes/AnalyzeView.svelte
```

You should see:
```
<ResultsPanel results={analysisResults} />
```

**Check:** Is `analysisResults` being set after the API call returns?

Find the analyze handler:

```bash
grep -B5 -A15 "onAnalyze\|POST.*analyze" frontend/src/routes/AnalyzeView.svelte | head -40
```

**Verify:**
```javascript
const response = await fetch('/api/analyze/upload', { ... });
const data = await response.json();
analysisResults = data;  // ← This line must exist and fire
```

If `analysisResults` is never assigned after the fetch, the component has no data to render.

---

## STEP 4: Check Svelte Reactivity

If `analysisResults` is being assigned, check that the component actually *reacts* to it.

**Pattern (correct):**
```javascript
let analysisResults = null;

async function handleAnalyze() {
  const response = await fetch('/api/analyze/upload', { ... });
  const data = await response.json();
  analysisResults = data;  // Svelte re-runs subscribed components
}
```

**Anti-pattern (silent no-op):**
```javascript
let analysisResults = null;

async function handleAnalyze() {
  const response = await fetch('/api/analyze/upload', { ... });
  const data = await response.json();
  // analysisResults = data;  // ← Oops, forgot to assign
}
```

**Check:** Grep for the assignment:

```bash
grep -n "analysisResults.*=" frontend/src/routes/AnalyzeView.svelte
```

Should see multiple lines (init + post-fetch assignment).

---

## STEP 5: Fix Known Import Issue

**File:** `frontend/src/lib/components/IssueTable.svelte`

Check if `ScanEye` is used but not imported:

```bash
grep -n "ScanEye\|import.*ScanEye" frontend/src/lib/components/IssueTable.svelte
```

If you see `ScanEye` used (e.g., in a function call or template) but no import, add:

```javascript
import ScanEye from 'lucide-svelte/icons/scan-eye';
```

Add it to the other lucide imports at the top of the script block.

---

## STEP 6: Run Svelte Type Check

```bash
cd frontend
npx svelte-check --tsconfig ./tsconfig.json
```

This will list all 51 structural errors. Focus on errors in:
- `AnalyzeView.svelte`
- `ResultsPanel.svelte`
- `IssueTable.svelte`

**Common patterns to fix:**
- Missing imports (like ScanEye)
- Undefined variables in templates
- Type mismatches on reactive stores
- Missing event handlers

For each error, the output shows file, line, and suggestion. Fix the critical ones first (import errors, undefined vars).

---

## STEP 7: Manual Render Test

Add a temporary debug line to confirm the component is even being mounted:

**File:** `frontend/src/lib/components/ResultsPanel.svelte`

In the `<script>` block, after the imports:

```javascript
console.log('[ResultsPanel] Mounted with results:', results);
```

In the template, add a visible debug marker at the top:

```svelte
{#if results}
  <div style="color: red; font-weight: bold;">DEBUG: Results loaded ({results.issues.length} issues)</div>
{:else}
  <div style="color: orange; font-weight: bold;">DEBUG: No results yet</div>
{/if}
```

Reload the browser, run Analyze, and check the console + DOM. You should see the debug message confirming whether results are being received.

Once confirmed, remove the debug lines.

---

## STEP 8: Test with Cache Off (Isolate)

If results still don't render with cache on, test with cache disabled:

```bash
# In AnalyzeView.svelte, find the analyze handler
# Add this before the fetch:
const useCache = false;  // Temp disable
```

Re-run. If results render when cache is off, the issue is in the cache response handling.

---

## STEP 9: Systematic Fix Path

Based on findings from Steps 1-8:

**If issue is missing assignment:**
```javascript
async function handleAnalyze() {
  const response = await fetch('/api/analyze/upload', { ... });
  const data = await response.json();
  analysisResults = data;  // ← Add this
}
```

**If issue is missing import:**
```javascript
import ScanEye from 'lucide-svelte/icons/scan-eye';
```

**If issue is svelte-check errors blocking render:**
- Run `npx svelte-check` and fix errors one by one
- Prioritize: missing imports > undefined vars > type mismatches

**If issue is component mounting but not rendering:**
- Add `{#if results}` guard in template
- Ensure results object has expected shape (`.issues`, `.findings`, etc.)

---

## STEP 10: Run Full Test

```bash
cd frontend
npm run build
```

Build should complete without warnings. If it fails, svelte-check errors need fixing first.

Then test in browser again:

```bash
# Terminal 1: Backend
python main.py

# Terminal 2: Frontend (if separate)
cd frontend && npm run dev

# Browser: http://localhost:5173
# Upload → Analyze → results panel should render
```

---

## STEP 11: Regression Check

Run existing Svelte tests (if they exist):

```bash
cd frontend
npm test
```

Or if using Vitest/Playwright:

```bash
npm run test:unit
npm run test:e2e
```

Ensure no new failures introduced.

---

## STEP 12: Commit

```bash
git add frontend/src/

# If multiple fixes (ScanEye import + svelte-check fixes + assignment fix):
git commit -m "Fix: Results panel rendering blocked by missing props/imports/reactivity

- Add missing analysisResults assignment in analyze handler
- Import ScanEye in IssueTable.svelte
- Resolve X svelte-check errors (missing imports, undefined vars)
- Verify component mounts and renders on data arrival
- Regression tests pass"
```

---

## Verification Checklist

- [ ] Backend returns 200 with results JSON (Network tab confirms)
- [ ] analysisResults is assigned after fetch (code inspection)
- [ ] ScanEye and other missing imports added
- [ ] svelte-check passes (or errors reduced significantly)
- [ ] ResultsPanel renders with test data in browser
- [ ] Cache on/off both work
- [ ] Regression tests pass
- [ ] Build succeeds without warnings

---

## When Done

Report back with:
1. Screenshot of results panel rendering (table + stat cards visible)
2. svelte-check output (number of errors before/after)
3. Commit hash
4. Any blockers encountered during debugging

Then Session 2 moves to demo block generators.
