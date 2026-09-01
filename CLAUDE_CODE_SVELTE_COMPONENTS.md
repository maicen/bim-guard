# Claude Code Session: ISO 19650 Naming Config — Svelte Components

**Task:** Create 5 Svelte components for the naming configuration UI.

**Destination:** All files in `frontend/src/routes/components/naming-config/`

**Context:** These are child sections of NamingConfigStep.svelte (already created). Each manages one aspect of the naming convention configuration.

---

## Component 1: ProjectMetadataSection.svelte

Create file: `frontend/src/routes/components/naming-config/ProjectMetadataSection.svelte`

```svelte
<!-- 
  ProjectMetadataSection.svelte
  Section 1: Project Metadata (PROJ-ORG-PH)
  Manages: Project Code, Originator Code, Phase Code
-->

<script>
  import { createEventDispatcher } from 'svelte';

  export let data = {
    project_code: '',
    originator_code: '',
    phase_code: 'SD'
  };

  const dispatch = createEventDispatcher();

  const phaseOptions = [
    { value: 'PV', label: 'PV — Preliminary/Provisional' },
    { value: 'SD', label: 'SD — Scheme Design' },
    { value: 'DD', label: 'DD — Design Development' },
    { value: 'CD', label: 'CD — Contract Documents' },
    { value: 'AS', label: 'AS — As-Built / As-Constructed' },
    { value: 'WIP', label: 'WIP — Work in Progress' }
  ];

  function handleChange(field, value) {
    dispatch('update', {
      [field]: value
    });
  }
</script>

<div class="metadata-section">
  <div class="info-box">
    <p>
      Define project-level identifiers used in all filenames.
      These fields are mandatory and must be agreed upon in the BIM Execution Plan (BEP).
    </p>
  </div>

  <form class="form-grid">
    <!-- Project Code -->
    <div class="form-group">
      <label for="project-code">
        PROJECT CODE <span class="required">*</span>
      </label>
      <input
        id="project-code"
        type="text"
        placeholder="e.g., A7000"
        value={data.project_code}
        on:change={(e) => handleChange('project_code', e.target.value)}
        maxlength="8"
        required
      />
      <small>Unique identifier (2–8 characters). Example: A7000 for Motorway Project A7</small>
    </div>

    <!-- Originator Code -->
    <div class="form-group">
      <label for="originator-code">
        ORIGINATOR CODE <span class="required">*</span>
      </label>
      <input
        id="originator-code"
        type="text"
        placeholder="e.g., BIM"
        value={data.originator_code}
        on:change={(e) => handleChange('originator_code', e.target.value)}
        maxlength="8"
        required
      />
      <small>Firm initials or organization code (2–8 characters). Example: BIM for BIMicon</small>
    </div>

    <!-- Phase Code -->
    <div class="form-group">
      <label for="phase-code">
        PHASE CODE
      </label>
      <select
        id="phase-code"
        value={data.phase_code}
        on:change={(e) => handleChange('phase_code', e.target.value)}
      >
        {#each phaseOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
      <small>Project phase (SD = Scheme Design is most common)</small>
    </div>
  </form>

  <div class="status-bar">
    <div class="status-item">
      <strong>Status:</strong>
      {#if data.project_code && data.originator_code}
        ✓ Metadata complete
      {:else}
        ⚠ Fill in both Project and Originator codes
      {/if}
    </div>
  </div>

  <div class="example-box">
    <strong>Example naming output:</strong>
    <code>
      {data.project_code || 'A7000'}-{data.originator_code || 'BIM'}-{data.phase_code}-01-DR-A-A01-0001-S1-Rev01
    </code>
  </div>
</div>

<style>
  .metadata-section {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .info-box {
    background-color: #eff6ff;
    border-left: 4px solid #2563eb;
    padding: 1rem;
    border-radius: 4px;
    font-size: 0.875rem;
    color: #1e40af;
    line-height: 1.6;
  }

  .info-box p {
    margin: 0;
  }

  .form-grid {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  label {
    font-size: 0.875rem;
    font-weight: 600;
    color: #1f2937;
  }

  .required {
    color: #dc2626;
  }

  input,
  select {
    padding: 0.75rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.875rem;
    font-family: inherit;
    transition: border-color 0.2s ease;
  }

  input:focus,
  select:focus {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  }

  small {
    font-size: 0.75rem;
    color: #6b7280;
  }

  .status-bar {
    background-color: #f3f4f6;
    padding: 0.75rem 1rem;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .status-item {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .example-box {
    background-color: #1f2937;
    color: #10b981;
    padding: 1rem;
    border-radius: 4px;
    font-size: 0.8rem;
    line-height: 1.6;
  }

  .example-box strong {
    color: #60a5fa;
    display: block;
    margin-bottom: 0.5rem;
  }

  code {
    font-family: 'Courier New', monospace;
    word-break: break-all;
  }
</style>
```

---

## Component 2: LevelLocationCodesSection.svelte

Create file: `frontend/src/routes/components/naming-config/LevelLocationCodesSection.svelte`

```svelte
<!-- 
  LevelLocationCodesSection.svelte
  Section 2: Level/Location Codes (LV)
  Manages library of level codes (GF, 01, 02, RF, etc.)
-->

<script>
  import { createEventDispatcher } from 'svelte';

  export let codes = [];
  const dispatch = createEventDispatcher();

  const masterLibrary = [
    { code: 'ZZ', label: 'All levels', removable: false },
    { code: 'B02', label: 'Basement 2', removable: true },
    { code: 'B01', label: 'Basement 1', removable: true },
    { code: 'GF', label: 'Ground Floor', removable: false },
    { code: '01', label: 'Level 01', removable: false },
    { code: '02', label: 'Level 02', removable: true },
    { code: '03', label: 'Level 03', removable: true },
    { code: '04', label: 'Level 04', removable: true },
    { code: '05', label: 'Level 05', removable: true },
    { code: 'RF', label: 'Roof', removable: false },
    { code: 'ME', label: 'Mezzanine', removable: true }
  ];

  let newCode = '';
  let newLabel = '';

  function removeCode(index) {
    const updated = codes.filter((_, i) => i !== index);
    dispatch('update', updated);
  }

  function addCustomCode() {
    if (!newCode || !newLabel) return;
    if (codes.some(c => c.code === newCode)) {
      alert('Code already exists');
      return;
    }
    const updated = [...codes, { code: newCode.toUpperCase(), label: newLabel, removable: true }];
    dispatch('update', updated);
    newCode = '';
    newLabel = '';
  }

  function addCodeFromLibrary(libCode) {
    if (codes.some(c => c.code === libCode)) {
      alert('Code already added');
      return;
    }
    const libItem = masterLibrary.find(item => item.code === libCode);
    const updated = [...codes, libItem];
    dispatch('update', updated);
  }

  $: availableLibraryCodes = masterLibrary.filter(
    item => !codes.some(c => c.code === item.code)
  );
</script>

<div class="level-section">
  <div class="info-box">
    <p>
      Define level/location codes for your building (floors, zones, areas).
      Select from the library or add custom codes. ZZ means "all levels".
    </p>
  </div>

  <!-- Active Codes -->
  <div class="section">
    <h3>Active Level Codes</h3>
    {#if codes.length === 0}
      <p class="empty-state">No level codes selected. Add from library below.</p>
    {:else}
      <div class="codes-grid">
        {#each codes as code, idx}
          <div class="code-tag">
            <span class="code-badge">{code.code}</span>
            <span class="code-label">{code.label}</span>
            {#if code.removable}
              <button class="remove-btn" on:click={() => removeCode(idx)}>✕</button>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Library -->
  <div class="section">
    <h3>Add from Master Library</h3>
    {#if availableLibraryCodes.length === 0}
      <p class="empty-state">All library codes are already added.</p>
    {:else}
      <div class="library-grid">
        {#each availableLibraryCodes as item}
          <button class="library-btn" on:click={() => addCodeFromLibrary(item.code)}>
            <strong>{item.code}</strong>
            <span>{item.label}</span>
          </button>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Custom Code -->
  <div class="section">
    <h3>Add Custom Code</h3>
    <div class="custom-form">
      <div class="form-group">
        <label for="new-code">Code</label>
        <input
          id="new-code"
          type="text"
          placeholder="e.g., M1"
          bind:value={newCode}
          maxlength="3"
          on:keydown={(e) => e.key === 'Enter' && addCustomCode()}
        />
      </div>
      <div class="form-group">
        <label for="new-label">Description</label>
        <input
          id="new-label"
          type="text"
          placeholder="e.g., Mezzanine 1"
          bind:value={newLabel}
          on:keydown={(e) => e.key === 'Enter' && addCustomCode()}
        />
      </div>
      <button
        class="btn btn-add"
        on:click={addCustomCode}
        disabled={!newCode || !newLabel}
      >
        + Add
      </button>
    </div>
  </div>
</div>

<style>
  .level-section {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .info-box {
    background-color: #eff6ff;
    border-left: 4px solid #2563eb;
    padding: 1rem;
    border-radius: 4px;
    font-size: 0.875rem;
    color: #1e40af;
  }

  .info-box p {
    margin: 0;
  }

  .section {
    padding: 1rem;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    background: #f9fafb;
  }

  .section h3 {
    margin: 0 0 1rem 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: #1f2937;
  }

  .empty-state {
    font-size: 0.875rem;
    color: #6b7280;
    margin: 0;
    font-style: italic;
  }

  .codes-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .code-tag {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: white;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .code-badge {
    background: #7c3aed;
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    font-weight: 600;
    font-size: 0.75rem;
    min-width: 40px;
    text-align: center;
  }

  .code-label {
    color: #374151;
  }

  .remove-btn {
    background: none;
    border: none;
    color: #dc2626;
    cursor: pointer;
    font-size: 1rem;
    padding: 0;
    line-height: 1;
    transition: color 0.2s ease;
  }

  .remove-btn:hover {
    color: #991b1b;
  }

  .library-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 0.75rem;
  }

  .library-btn {
    padding: 0.75rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    background: white;
    cursor: pointer;
    font-size: 0.875rem;
    text-align: left;
    transition: all 0.2s ease;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .library-btn:hover {
    border-color: #7c3aed;
    box-shadow: 0 2px 4px rgba(124, 58, 237, 0.1);
  }

  .library-btn strong {
    color: #7c3aed;
    font-size: 0.95rem;
  }

  .library-btn span {
    color: #6b7280;
    font-size: 0.8rem;
  }

  .custom-form {
    display: grid;
    grid-template-columns: auto auto 1fr;
    gap: 0.75rem;
    align-items: flex-end;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  label {
    font-size: 0.8rem;
    font-weight: 600;
    color: #374151;
  }

  input {
    padding: 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  input:focus {
    outline: none;
    border-color: #7c3aed;
  }

  .btn {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
    transition: all 0.2s ease;
  }

  .btn-add {
    background: #7c3aed;
    color: white;
  }

  .btn-add:hover:not(:disabled) {
    background: #6d28d9;
  }

  .btn-add:disabled {
    background: #d1d5db;
    cursor: not-allowed;
  }
</style>
```

---

## Component 3: TypeCodesSection.svelte

Create file: `frontend/src/routes/components/naming-config/TypeCodesSection.svelte`

```svelte
<!-- 
  TypeCodesSection.svelte
  Section 3: Type Codes (TYP)
  Manages: DR, M3, RI, CM, etc.
-->

<script>
  import { createEventDispatcher } from 'svelte';

  export let codes = [];
  const dispatch = createEventDispatcher();

  const masterLibrary = [
    { code: 'DR', label: '2D Drawing', removable: false },
    { code: 'M3', label: '3D Model', removable: false },
    { code: 'M2', label: '2D Model', removable: true },
    { code: 'RI', label: 'Request for Information', removable: true },
    { code: 'RP', label: 'Report', removable: true },
    { code: 'CM', label: 'Combined Model', removable: true },
    { code: 'SH', label: 'Schedule', removable: true },
    { code: 'SP', label: 'Specification', removable: true },
    { code: 'AF', label: 'Animation File', removable: true },
    { code: 'CR', label: 'Clash Report', removable: true }
  ];

  let newCode = '';
  let newLabel = '';

  function removeCode(index) {
    const updated = codes.filter((_, i) => i !== index);
    dispatch('update', updated);
  }

  function addCustomCode() {
    if (!newCode || !newLabel) return;
    if (codes.some(c => c.code === newCode)) {
      alert('Code already exists');
      return;
    }
    const updated = [...codes, { code: newCode.toUpperCase(), label: newLabel, removable: true }];
    dispatch('update', updated);
    newCode = '';
    newLabel = '';
  }

  function addCodeFromLibrary(libCode) {
    if (codes.some(c => c.code === libCode)) {
      alert('Code already added');
      return;
    }
    const libItem = masterLibrary.find(item => item.code === libCode);
    const updated = [...codes, libItem];
    dispatch('update', updated);
  }

  $: availableLibraryCodes = masterLibrary.filter(
    item => !codes.some(c => c.code === item.code)
  );
</script>

<div class="type-section">
  <div class="info-box">
    <p>
      Type codes describe the kind of information in the file (drawing, model, report, etc.).
      DR (Drawing) and M3 (3D Model) are mandatory for most projects.
    </p>
  </div>

  <!-- Active Codes -->
  <div class="section">
    <h3>Active Type Codes</h3>
    {#if codes.length === 0}
      <p class="empty-state">No type codes selected.</p>
    {:else}
      <div class="codes-grid">
        {#each codes as code, idx}
          <div class="code-tag">
            <span class="code-badge">{code.code}</span>
            <span class="code-label">{code.label}</span>
            {#if code.removable}
              <button class="remove-btn" on:click={() => removeCode(idx)}>✕</button>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Library -->
  <div class="section">
    <h3>Add from Master Library</h3>
    {#if availableLibraryCodes.length === 0}
      <p class="empty-state">All library codes are already added.</p>
    {:else}
      <div class="library-grid">
        {#each availableLibraryCodes as item}
          <button class="library-btn" on:click={() => addCodeFromLibrary(item.code)}>
            <strong>{item.code}</strong>
            <span>{item.label}</span>
          </button>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Custom Code -->
  <div class="section">
    <h3>Add Custom Code</h3>
    <div class="custom-form">
      <div class="form-group">
        <label for="new-code">Code (2–3 chars)</label>
        <input
          id="new-code"
          type="text"
          placeholder="e.g., MD"
          bind:value={newCode}
          maxlength="3"
          on:keydown={(e) => e.key === 'Enter' && addCustomCode()}
        />
      </div>
      <div class="form-group">
        <label for="new-label">Description</label>
        <input
          id="new-label"
          type="text"
          placeholder="e.g., Mechanical Design"
          bind:value={newLabel}
          on:keydown={(e) => e.key === 'Enter' && addCustomCode()}
        />
      </div>
      <button
        class="btn btn-add"
        on:click={addCustomCode}
        disabled={!newCode || !newLabel}
      >
        + Add
      </button>
    </div>
  </div>
</div>

<style>
  .type-section {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .info-box {
    background-color: #eff6ff;
    border-left: 4px solid #2563eb;
    padding: 1rem;
    border-radius: 4px;
    font-size: 0.875rem;
    color: #1e40af;
  }

  .info-box p {
    margin: 0;
  }

  .section {
    padding: 1rem;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    background: #f9fafb;
  }

  .section h3 {
    margin: 0 0 1rem 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: #1f2937;
  }

  .empty-state {
    font-size: 0.875rem;
    color: #6b7280;
    margin: 0;
    font-style: italic;
  }

  .codes-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .code-tag {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: white;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .code-badge {
    background: #059669;
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    font-weight: 600;
    font-size: 0.75rem;
    min-width: 35px;
    text-align: center;
  }

  .code-label {
    color: #374151;
  }

  .remove-btn {
    background: none;
    border: none;
    color: #dc2626;
    cursor: pointer;
    font-size: 1rem;
    padding: 0;
    line-height: 1;
  }

  .remove-btn:hover {
    color: #991b1b;
  }

  .library-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 0.75rem;
  }

  .library-btn {
    padding: 0.75rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    background: white;
    cursor: pointer;
    font-size: 0.875rem;
    text-align: left;
    transition: all 0.2s ease;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .library-btn:hover {
    border-color: #059669;
    box-shadow: 0 2px 4px rgba(5, 150, 105, 0.1);
  }

  .library-btn strong {
    color: #059669;
    font-size: 0.95rem;
  }

  .library-btn span {
    color: #6b7280;
    font-size: 0.8rem;
  }

  .custom-form {
    display: grid;
    grid-template-columns: auto auto 1fr;
    gap: 0.75rem;
    align-items: flex-end;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  label {
    font-size: 0.8rem;
    font-weight: 600;
    color: #374151;
  }

  input {
    padding: 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  input:focus {
    outline: none;
    border-color: #059669;
  }

  .btn {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
  }

  .btn-add {
    background: #059669;
    color: white;
  }

  .btn-add:hover:not(:disabled) {
    background: #047857;
  }

  .btn-add:disabled {
    background: #d1d5db;
  }
</style>
```

---

## Component 4: RoleDisciplineCodesSection.svelte

Create file: `frontend/src/routes/components/naming-config/RoleDisciplineCodesSection.svelte`

```svelte
<!-- 
  RoleDisciplineCodesSection.svelte
  Section 4: Role/Discipline Codes (RL)
  Manages: A (Architect), E (Electrical), H (HVAC), S (Structural), etc.
-->

<script>
  import { createEventDispatcher } from 'svelte';

  export let codes = [];
  const dispatch = createEventDispatcher();

  const masterLibrary = [
    { code: 'A', label: 'Architect', removable: false },
    { code: 'E', label: 'Electrical Engineer', removable: false },
    { code: 'H', label: 'HVAC / Mechanical', removable: false },
    { code: 'S', label: 'Structural Engineer', removable: false },
    { code: 'C', label: 'Civil Engineer', removable: true },
    { code: 'L', label: 'Landscape Architect', removable: true },
    { code: 'B', label: 'Building Surveyor', removable: true },
    { code: 'D', label: 'Drainage Engineer', removable: true },
    { code: 'F', label: 'Facilities Manager', removable: true },
    { code: 'G', label: 'Geotechnical Engineer', removable: true },
    { code: 'I', label: 'Interior Designer', removable: true },
    { code: 'K', label: 'Kitchen Equipment Specialist', removable: true }
  ];

  let newCode = '';
  let newLabel = '';

  function removeCode(index) {
    const updated = codes.filter((_, i) => i !== index);
    dispatch('update', updated);
  }

  function addCustomCode() {
    if (!newCode || !newLabel) return;
    if (codes.some(c => c.code === newCode)) {
      alert('Code already exists');
      return;
    }
    const updated = [...codes, { code: newCode.toUpperCase(), label: newLabel, removable: true }];
    dispatch('update', updated);
    newCode = '';
    newLabel = '';
  }

  function addCodeFromLibrary(libCode) {
    if (codes.some(c => c.code === libCode)) {
      alert('Code already added');
      return;
    }
    const libItem = masterLibrary.find(item => item.code === libCode);
    const updated = [...codes, libItem];
    dispatch('update', updated);
  }

  $: availableLibraryCodes = masterLibrary.filter(
    item => !codes.some(c => c.code === item.code)
  );
</script>

<div class="discipline-section">
  <div class="info-box">
    <p>
      Role/Discipline codes identify the professional discipline (Architect, Electrical, etc.).
      Single characters are standard (A, E, H, S). Add custom codes for specialized disciplines.
    </p>
  </div>

  <!-- Active Codes -->
  <div class="section">
    <h3>Active Discipline Codes</h3>
    {#if codes.length === 0}
      <p class="empty-state">No discipline codes selected.</p>
    {:else}
      <div class="codes-grid">
        {#each codes as code, idx}
          <div class="code-tag">
            <span class="code-badge">{code.code}</span>
            <span class="code-label">{code.label}</span>
            {#if code.removable}
              <button class="remove-btn" on:click={() => removeCode(idx)}>✕</button>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Library -->
  <div class="section">
    <h3>Add from Master Library</h3>
    {#if availableLibraryCodes.length === 0}
      <p class="empty-state">All library codes are already added.</p>
    {:else}
      <div class="library-grid">
        {#each availableLibraryCodes as item}
          <button class="library-btn" on:click={() => addCodeFromLibrary(item.code)}>
            <strong>{item.code}</strong>
            <span>{item.label}</span>
          </button>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Custom Code -->
  <div class="section">
    <h3>Add Custom Code</h3>
    <div class="custom-form">
      <div class="form-group">
        <label for="new-code">Code (1–2 chars)</label>
        <input
          id="new-code"
          type="text"
          placeholder="e.g., X"
          bind:value={newCode}
          maxlength="2"
          on:keydown={(e) => e.key === 'Enter' && addCustomCode()}
        />
      </div>
      <div class="form-group">
        <label for="new-label">Description</label>
        <input
          id="new-label"
          type="text"
          placeholder="e.g., Specialist"
          bind:value={newLabel}
          on:keydown={(e) => e.key === 'Enter' && addCustomCode()}
        />
      </div>
      <button
        class="btn btn-add"
        on:click={addCustomCode}
        disabled={!newCode || !newLabel}
      >
        + Add
      </button>
    </div>
  </div>
</div>

<style>
  .discipline-section {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .info-box {
    background-color: #eff6ff;
    border-left: 4px solid #2563eb;
    padding: 1rem;
    border-radius: 4px;
    font-size: 0.875rem;
    color: #1e40af;
  }

  .info-box p {
    margin: 0;
  }

  .section {
    padding: 1rem;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    background: #f9fafb;
  }

  .section h3 {
    margin: 0 0 1rem 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: #1f2937;
  }

  .empty-state {
    font-size: 0.875rem;
    color: #6b7280;
    margin: 0;
    font-style: italic;
  }

  .codes-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .code-tag {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: white;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .code-badge {
    background: #2563eb;
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    font-weight: 600;
    font-size: 0.75rem;
    min-width: 28px;
    text-align: center;
  }

  .code-label {
    color: #374151;
  }

  .remove-btn {
    background: none;
    border: none;
    color: #dc2626;
    cursor: pointer;
    font-size: 1rem;
    padding: 0;
    line-height: 1;
  }

  .remove-btn:hover {
    color: #991b1b;
  }

  .library-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 0.75rem;
  }

  .library-btn {
    padding: 0.75rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    background: white;
    cursor: pointer;
    font-size: 0.875rem;
    text-align: left;
    transition: all 0.2s ease;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .library-btn:hover {
    border-color: #2563eb;
    box-shadow: 0 2px 4px rgba(37, 99, 235, 0.1);
  }

  .library-btn strong {
    color: #2563eb;
    font-size: 0.95rem;
  }

  .library-btn span {
    color: #6b7280;
    font-size: 0.8rem;
  }

  .custom-form {
    display: grid;
    grid-template-columns: auto auto 1fr;
    gap: 0.75rem;
    align-items: flex-end;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  label {
    font-size: 0.8rem;
    font-weight: 600;
    color: #374151;
  }

  input {
    padding: 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  input:focus {
    outline: none;
    border-color: #2563eb;
  }

  .btn {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
  }

  .btn-add {
    background: #2563eb;
    color: white;
  }

  .btn-add:hover:not(:disabled) {
    background: #1d4ed8;
  }

  .btn-add:disabled {
    background: #d1d5db;
  }
</style>
```

---

## Component 5: CDEStatusMappingSection.svelte

Create file: `frontend/src/routes/components/naming-config/CDEStatusMappingSection.svelte`

```svelte
<!-- 
  CDEStatusMappingSection.svelte
  Section 5: CDE Status Codes (SUIT) — Read-Only Reference
  ISO 19650-2, TABLE 1
-->

<script>
  export let cdeMapping = {
    S0: 'Work in progress',
    S1: 'Suitable for coordination',
    S2: 'Suitable for information',
    S3: 'Suitable for review',
    A: 'Approved/Accepted',
    B: 'Partial sign off',
    S7: 'Archived / superseded'
  };

  const statusOrder = ['S0', 'S1', 'S2', 'S3', 'A', 'B', 'S7'];

  function getStatusColor(code) {
    const colors = {
      S0: '#f97316',
      S1: '#3b82f6',
      S2: '#10b981',
      S3: '#f59e0b',
      A: '#059669',
      B: '#ec4899',
      S7: '#6b7280'
    };
    return colors[code] || '#6b7280';
  }
</script>

<div class="cde-status-section">
  <div class="info-box">
    <p>
      CDE (Common Data Environment) status codes are defined in ISO 19650-2, TABLE 1.
      These are standardized, read-only reference values. Select the appropriate status code for file release.
    </p>
  </div>

  <div class="status-grid">
    {#each statusOrder as code}
      <div class="status-card" style="--status-color: {getStatusColor(code)}">
        <div class="status-badge">{code}</div>
        <div class="status-label">{cdeMapping[code]}</div>
      </div>
    {/each}
  </div>

  <div class="guidance">
    <h4>When to Use</h4>
    <ul>
      <li><strong>S0</strong> — File in active development; not for circulation</li>
      <li><strong>S1</strong> — Ready for other disciplines to review and build upon</li>
      <li><strong>S2</strong> — Released for reference only; not subject to change</li>
      <li><strong>S3</strong> — Released for formal comment and review</li>
      <li><strong>A</strong> — Formally approved and signed off; basis for construction</li>
      <li><strong>B</strong> — Partially approved (some sections only)</li>
      <li><strong>S7</strong> — Superseded; keep for historical reference only</li>
    </ul>
  </div>
</div>

<style>
  .cde-status-section {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .info-box {
    background-color: #eff6ff;
    border-left: 4px solid #2563eb;
    padding: 1rem;
    border-radius: 4px;
    font-size: 0.875rem;
    color: #1e40af;
    line-height: 1.6;
  }

  .info-box p {
    margin: 0;
  }

  .status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 1rem;
  }

  .status-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
    padding: 1.5rem 1rem;
    background: white;
    border: 2px solid var(--status-color);
    border-radius: 8px;
    text-align: center;
  }

  .status-badge {
    font-size: 1.5rem;
    font-weight: 700;
    color: white;
    background: var(--status-color);
    padding: 0.5rem 0.75rem;
    border-radius: 4px;
    min-width: 45px;
  }

  .status-label {
    font-size: 0.8rem;
    font-weight: 600;
    color: #1f2937;
    line-height: 1.3;
  }

  .guidance {
    background: #f3f4f6;
    padding: 1.5rem;
    border-radius: 6px;
    border-left: 4px solid #6b7280;
  }

  .guidance h4 {
    margin: 0 0 1rem 0;
    font-size: 0.95rem;
    color: #1f2937;
  }

  .guidance ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .guidance li {
    font-size: 0.8rem;
    color: #374151;
    line-height: 1.5;
  }

  .guidance strong {
    color: #1f2937;
  }
</style>
```

---

## Component 6: NamingConventionSection.svelte

Create file: `frontend/src/routes/components/naming-config/NamingConventionSection.svelte`

```svelte
<!-- 
  NamingConventionSection.svelte
  Section 6: Naming Convention Presets + Live Preview
  Shows 5 presets + live example output
-->

<script>
  import { createEventDispatcher, onMount } from 'svelte';

  export let activeConvention = 'iso19650-1';
  export let projectCode = '';
  export let originatorCode = '';
  export let revisionFormat = 'Rev##';

  const dispatch = createEventDispatcher();

  let presets = {};
  let loading = true;
  let preview = '';

  onMount(async () => {
    try {
      const response = await fetch('/api/naming-config/presets');
      presets = await response.json();
      updatePreview();
    } catch (err) {
      console.error('Failed to load presets:', err);
    } finally {
      loading = false;
    }
  });

  function updateConvention(convention) {
    dispatch('update', { active_convention: convention });
    activeConvention = convention;
    updatePreview();
  }

  function updatePreview() {
    // Generate simple preview
    const date = new Date().toISOString().slice(0, 8).replace(/-/g, '');
    
    if (activeConvention === 'iso19650-1') {
      preview = `${projectCode || 'PROJ'}-${originatorCode || 'ORG'}-SD-01-DR-A-A01-0001-S1-${revisionFormat.replace('##', '01')}`;
    } else if (activeConvention === 'iso19650-2') {
      preview = `${projectCode || 'PROJ'}-${originatorCode || 'ORG'}-SD-01-DR-A-A01-0001-S1-${revisionFormat.replace('##', '01')}-${date}`;
    } else if (activeConvention === 'simple') {
      preview = `DR-${originatorCode || 'ORG'}-01-A-0001`;
    } else if (activeConvention === 'descriptive') {
      preview = `${originatorCode || 'ORG'} 2D Drawing Ground Floor Architecture 0001`;
    } else if (activeConvention === 'uniclass') {
      preview = `${projectCode || 'PROJ'}_Pr_70_01_0001_${revisionFormat.replace('##', '01')}`;
    }
  }

  $: if (projectCode || originatorCode || revisionFormat) updatePreview();
</script>

<div class="naming-convention-section">
  <div class="info-box">
    <p>
      Select a naming convention preset. The preview below shows how your filenames will appear.
      ISO 19650-1:2018 is the industry standard. Choose the convention your project requires.
    </p>
  </div>

  {#if loading}
    <p style="text-align: center; color: #6b7280;">Loading presets...</p>
  {:else}
    <!-- Preset Selector -->
    <div class="section">
      <h3>Naming Convention Presets</h3>
      <div class="preset-selector">
        {#each Object.entries(presets) as [key, data]}
          <div class="preset-option">
            <input
              type="radio"
              id="preset-{key}"
              name="naming-convention"
              value={key}
              checked={activeConvention === key}
              on:change={() => updateConvention(key)}
            />
            <label for="preset-{key}">
              <strong>{data.name}</strong>
              <span class="description">{data.description}</span>
            </label>
          </div>
        {/each}
      </div>
    </div>

    <!-- Template & Preview -->
    <div class="section">
      <h3>Format Template & Example</h3>
      {#if presets[activeConvention]}
        <div class="format-info">
          <div class="format-row">
            <label>Template:</label>
            <code class="format-string">{presets[activeConvention].template}</code>
          </div>
          <div class="format-row">
            <label>Your Preview:</label>
            <code class="example">{preview}</code>
          </div>
        </div>
      {/if}
    </div>

    <!-- Token Legend -->
    <div class="section">
      <h3>Available Tokens</h3>
      {#if presets[activeConvention]?.tokens}
        <div class="token-grid">
          {#each Object.entries(presets[activeConvention].tokens) as [key, value]}
            <div class="token-item">
              <code>{{{key}}}</code>
              <span>{value}</span>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .naming-convention-section {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .info-box {
    background-color: #eff6ff;
    border-left: 4px solid #2563eb;
    padding: 1rem;
    border-radius: 4px;
    font-size: 0.875rem;
    color: #1e40af;
    line-height: 1.6;
  }

  .info-box p {
    margin: 0;
  }

  .section {
    padding: 1rem;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    background: #f9fafb;
  }

  .section h3 {
    margin: 0 0 1rem 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: #1f2937;
  }

  .preset-selector {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .preset-option {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.75rem;
    background: white;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    transition: all 0.2s ease;
    cursor: pointer;
  }

  .preset-option:hover {
    border-color: #2563eb;
    background: #f0f9ff;
  }

  .preset-option input[type='radio'] {
    margin-top: 0.25rem;
    cursor: pointer;
  }

  .preset-option label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    cursor: pointer;
    flex: 1;
    margin: 0;
  }

  .preset-option label strong {
    color: #1f2937;
    font-size: 0.875rem;
  }

  .description {
    font-size: 0.8rem;
    color: #6b7280;
    font-weight: normal;
  }

  .format-info {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .format-row {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .format-row label {
    font-size: 0.8rem;
    font-weight: 600;
    color: #374151;
    margin: 0;
  }

  code {
    background: #1f2937;
    color: #10b981;
    padding: 0.75rem;
    border-radius: 4px;
    font-family: 'Courier New', monospace;
    font-size: 0.85rem;
    overflow-x: auto;
    display: block;
    word-break: break-all;
  }

  .format-string {
    color: #60a5fa;
  }

  .example {
    color: #fbbf24;
    font-weight: 600;
  }

  .token-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 0.75rem;
  }

  .token-item {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    padding: 0.75rem;
    background: white;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.8rem;
  }

  .token-item code {
    background: #eff6ff;
    color: #1e40af;
    padding: 0.375rem;
    display: inline-block;
    overflow: visible;
  }

  .token-item span {
    color: #6b7280;
  }
</style>
```

---

## Summary

You now have 6 complete Svelte components. Copy each one into the correct file path as listed above. Then run:

```powershell
cd frontend
npm run build
```

All components will integrate into the NamingConfigStep.svelte parent.
