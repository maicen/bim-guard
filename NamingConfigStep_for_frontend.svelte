<!-- 
  NamingConfigStep.svelte
  Step 3 of 5-step project wizard: ISO 19650 Naming Configuration
  
  Destination: frontend/src/routes/components/NamingConfigStep.svelte
  
  Manages 6 sections:
  1. Project Metadata (PROJ-ORG-PH)
  2. Phase Code (PH)
  3. Level/Location Codes (LV) — configurable library
  4. Type Codes (TYP) — configurable library
  5. Role/Discipline Codes (RL) — configurable library
  6. CDE Status Mapping (SUIT) — read-only reference + Naming Convention presets
-->

<script>
  import { onMount } from 'svelte';
  import ProjectMetadataSection from './naming-config/ProjectMetadataSection.svelte';
  import LevelLocationCodesSection from './naming-config/LevelLocationCodesSection.svelte';
  import TypeCodesSection from './naming-config/TypeCodesSection.svelte';
  import RoleDisciplineCodesSection from './naming-config/RoleDisciplineCodesSection.svelte';
  import CDEStatusMappingSection from './naming-config/CDEStatusMappingSection.svelte';
  import NamingConventionSection from './naming-config/NamingConventionSection.svelte';

  export let projectId = '';
  export let onSave = null;

  let configData = {
    project_code: '',
    originator_code: '',
    phase_code: 'SD',
    level_location_codes: [],
    type_codes: [],
    role_discipline_codes: [],
    classification_codes: {},
    active_convention: 'iso19650-1',
    revision_format: 'Rev##',
    custom_format_string: null
  };

  let loading = false;
  let saving = false;
  let error = '';
  let success = '';
  let activeTab = 'metadata';

  onMount(async () => {
    if (projectId) {
      await loadNamingConfig();
    }
  });

  async function loadNamingConfig() {
    loading = true;
    error = '';
    try {
      const response = await fetch(`/api/naming-config/projects/${projectId}`);
      if (response.ok) {
        configData = await response.json();
      } else if (response.status === 404) {
        // Config doesn't exist yet; use defaults
        console.log('No existing config, using defaults');
      } else {
        throw new Error('Failed to load naming config');
      }
    } catch (err) {
      console.error('Failed to load naming config:', err);
      error = `Error loading config: ${err.message}`;
    } finally {
      loading = false;
    }
  }

  async function saveNamingConfig() {
    saving = true;
    error = '';
    success = '';
    
    // Validate required fields
    if (!configData.project_code || !configData.originator_code) {
      error = 'Project Code and Originator Code are required';
      saving = false;
      return;
    }

    try {
      const response = await fetch(
        `/api/naming-config/projects/${projectId}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(configData)
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to save configuration');
      }

      configData = await response.json();
      success = 'Configuration saved successfully';
      
      // Call parent callback if provided
      if (onSave) {
        setTimeout(() => onSave(configData), 500);
      }
    } catch (err) {
      error = `Failed to save: ${err.message}`;
      console.error('Save error:', err);
    } finally {
      saving = false;
    }
  }

  // Update handlers for sections
  function updateMetadata(updates) {
    configData = { ...configData, ...updates };
  }

  function updateCodeArray(field, codes) {
    configData[field] = codes;
  }

  function updateClassification(codes) {
    configData.classification_codes = codes;
  }

  function updateConvention(updates) {
    configData = { ...configData, ...updates };
  }
</script>

<div class="naming-config-step">
  <div class="step-header">
    <h2>Step 3: ISO 19650 Naming Configuration</h2>
    <p class="step-description">
      Define project codes, naming codes, and naming convention for compliance with ISO 19650-1:2018.
      These settings ensure consistent file naming across your BIM project.
      Structure: <code>PROJ-ORG-PH-LV-TYP-RL-CL-NUM-SUIT-REV.ext</code>
    </p>
  </div>

  {#if error}
    <div class="alert alert-error">
      <span class="alert-icon">⚠</span> {error}
    </div>
  {/if}

  {#if success}
    <div class="alert alert-success">
      <span class="alert-icon">✓</span> {success}
    </div>
  {/if}

  {#if loading}
    <div class="alert alert-info">
      <span class="alert-icon">⏳</span> Loading configuration...
    </div>
  {:else}
    <!-- Tab Navigation -->
    <div class="tabs">
      {#each [
        { id: 'metadata', label: '📋 Metadata', icon: '📋' },
        { id: 'levels', label: '🏢 Levels', icon: '🏢' },
        { id: 'types', label: '📝 Types', icon: '📝' },
        { id: 'disciplines', label: '👥 Disciplines', icon: '👥' },
        { id: 'cde-status', label: '✓ CDE Status', icon: '✓' },
        { id: 'convention', label: '🏷️ Convention', icon: '🏷️' }
      ] as tab}
        <button
          class="tab-btn {activeTab === tab.id ? 'active' : ''}"
          on:click={() => (activeTab = tab.id)}
          disabled={saving}
          title={tab.label}
        >
          {tab.icon}
        </button>
      {/each}
    </div>

    <!-- Tab Content -->
    <div class="tabs-content">
      {#if activeTab === 'metadata'}
        <ProjectMetadataSection
          data={configData}
          on:update={(e) => updateMetadata(e.detail)}
        />
      {:else if activeTab === 'levels'}
        <LevelLocationCodesSection
          codes={configData.level_location_codes}
          on:update={(e) => updateCodeArray('level_location_codes', e.detail)}
        />
      {:else if activeTab === 'types'}
        <TypeCodesSection
          codes={configData.type_codes}
          on:update={(e) => updateCodeArray('type_codes', e.detail)}
        />
      {:else if activeTab === 'disciplines'}
        <RoleDisciplineCodesSection
          codes={configData.role_discipline_codes}
          on:update={(e) => updateCodeArray('role_discipline_codes', e.detail)}
        />
      {:else if activeTab === 'cde-status'}
        <CDEStatusMappingSection cdeMapping={configData.cde_status_mapping} />
      {:else if activeTab === 'convention'}
        <NamingConventionSection
          activeConvention={configData.active_convention}
          projectCode={configData.project_code}
          originatorCode={configData.originator_code}
          revisionFormat={configData.revision_format}
          on:update={(e) => updateConvention(e.detail)}
        />
      {/if}
    </div>

    <!-- Action Buttons -->
    <div class="form-actions">
      <button
        type="button"
        class="btn btn-primary"
        on:click={saveNamingConfig}
        disabled={saving || !configData.project_code || !configData.originator_code}
      >
        {saving ? 'Saving...' : 'Save Configuration'}
      </button>
      <button
        type="button"
        class="btn btn-secondary"
        on:click={() => loadNamingConfig()}
        disabled={saving}
      >
        Reset
      </button>
    </div>
  {/if}
</div>

<style>
  .naming-config-step {
    padding: 2rem;
    background: #f9fafb;
    border-radius: 8px;
  }

  .step-header {
    margin-bottom: 2rem;
  }

  .step-header h2 {
    font-size: 1.5rem;
    margin: 0 0 0.5rem 0;
    color: #1f2937;
  }

  .step-description {
    font-size: 0.875rem;
    color: #6b7280;
    margin: 0;
    line-height: 1.5;
  }

  .step-description code {
    background: #ffe5cc;
    padding: 0.2rem 0.4rem;
    border-radius: 3px;
    font-family: monospace;
    color: #92400e;
  }

  .alert {
    padding: 0.75rem 1rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
    font-size: 0.875rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .alert-error {
    background-color: #fee2e2;
    color: #991b1b;
    border: 1px solid #fecaca;
  }

  .alert-success {
    background-color: #dcfce7;
    color: #166534;
    border: 1px solid #bbf7d0;
  }

  .alert-info {
    background-color: #dbeafe;
    color: #1e40af;
    border: 1px solid #bfdbfe;
  }

  .alert-icon {
    font-size: 1rem;
    flex-shrink: 0;
  }

  .tabs {
    display: flex;
    gap: 0.25rem;
    background: white;
    padding: 0.5rem;
    border-radius: 6px;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
  }

  .tab-btn {
    padding: 0.625rem 0.75rem;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.2s ease;
    min-width: 45px;
    text-align: center;
  }

  .tab-btn:hover:not(:disabled) {
    background: #e5e7eb;
  }

  .tab-btn.active {
    background: #2563eb;
    color: white;
    border-color: #2563eb;
  }

  .tab-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .tabs-content {
    background: white;
    padding: 1.5rem;
    border-radius: 6px;
    margin-bottom: 1.5rem;
    min-height: 300px;
  }

  .form-actions {
    display: flex;
    gap: 1rem;
    justify-content: flex-end;
  }

  .btn {
    padding: 0.75rem 1.5rem;
    border-radius: 4px;
    border: none;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-primary {
    background-color: #2563eb;
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background-color: #1d4ed8;
  }

  .btn-secondary {
    background-color: #e5e7eb;
    color: #1f2937;
  }

  .btn-secondary:hover:not(:disabled) {
    background-color: #d1d5db;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
