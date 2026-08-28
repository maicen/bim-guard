<script lang="ts">
  import { onMount } from 'svelte';
  import {
    ListChecks,
    Search,
    Plus,
    Trash2,
    Database,
    Download,
    Folder,
    FolderOpen,
    CheckCircle2,
    AlertCircle,
    SlidersHorizontal,
    Edit3,
    X,
  } from 'lucide-svelte';
  import { rulesApi, ruleExtractionApi } from '../lib/api';
  import type { Rule, RuleFolder } from '../lib/types';

  let rules: Rule[] = [];
  let folders: RuleFolder[] = [];
  let isLoading = true;
  let error = '';
  let successMessage = '';

  // Filter state
  let searchQuery = '';
  let selectedFolderId: string | null = null;
  let selectedMechanism: string = 'all';
  let filterNeedsReview: boolean = false;

  // Rule edit/create modal state
  let isModalOpen = false;
  let isEditing = false;
  let editRuleId: number | null = null;

  // Form fields
  let formRuleId = '';
  let formDescription = '';
  let formMechanism = 'CODE';
  let formRulesetId = 'BUILDING-CODE-PART9';
  let formCategory = 'property_check';
  let formPropertySet = 'Pset_Compliance';
  let formPropertyName = '';
  let formOperator = '==';
  let formCheckValue = '';
  let formValueMin = '';
  let formValueMax = '';
  let formValueMinProperty = '';
  let formValueMaxProperty = '';
  let formValueMinOffset = '';
  let formValueMaxOffset = '';
  let formCompareProperty = '';
  let formNamePattern = '';
  let formUniquenessScope = 'building';
  let formUnit = '';
  let formSeverity = 'Medium';
  let formNeedsReview = 0;

  async function loadData() {
    isLoading = true;
    error = '';
    try {
      const [rulesData, foldersData] = await Promise.all([
        rulesApi.list(),
        rulesApi.folders(),
      ]);
      rules = rulesData;
      folders = foldersData;
    } catch (err: any) {
      error = err.message || 'Failed to load compliance rules';
    } finally {
      isLoading = false;
    }
  }

  onMount(() => {
    loadData();
  });

  $: filteredRules = rules.filter((r) => {
    const matchesSearch =
      searchQuery === '' ||
      (r.rule_id || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.description || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.property_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.compare_property || '').toLowerCase().includes(searchQuery.toLowerCase());

    const matchesFolder =
      !selectedFolderId || r.ruleset_id === selectedFolderId;

    const matchesMechanism =
      selectedMechanism === 'all' || r.mechanism === selectedMechanism;

    const matchesReview =
      !filterNeedsReview || r.needs_review === 1;

    return matchesSearch && matchesFolder && matchesMechanism && matchesReview;
  });

  async function handleSeedRules() {
    try {
      const res = await ruleExtractionApi.seed();
      successMessage = `Rule library seeded successfully (${res.total_rules} rules active).`;
      await loadData();
    } catch (err: any) {
      error = `Seeding failed: ${err.message}`;
    }
  }

  function openCreateModal() {
    isEditing = false;
    editRuleId = null;
    formRuleId = '';
    formDescription = '';
    formMechanism = 'CODE';
    formRulesetId = selectedFolderId || 'BUILDING-CODE-PART9';
    formCategory = 'property_check';
    formPropertySet = 'Pset_Compliance';
    formPropertyName = '';
    formOperator = '==';
    formCheckValue = '';
    formValueMin = '';
    formValueMax = '';
    formValueMinProperty = '';
    formValueMaxProperty = '';
    formValueMinOffset = '';
    formValueMaxOffset = '';
    formCompareProperty = '';
    formNamePattern = '';
    formUniquenessScope = 'building';
    formUnit = '';
    formSeverity = 'Medium';
    formNeedsReview = 0;
    isModalOpen = true;
  }

  function openEditModal(rule: Rule) {
    isEditing = true;
    editRuleId = rule.id;
    formRuleId = rule.rule_id || '';
    formDescription = rule.description || '';
    formMechanism = rule.mechanism || 'CODE';
    formRulesetId = rule.ruleset_id || 'BUILDING-CODE-PART9';
    formCategory = rule.rule_category || 'property_check';
    formPropertySet = rule.property_set || 'Pset_Compliance';
    formPropertyName = rule.property_name || '';
    formOperator = rule.operator || '==';
    formCheckValue = rule.check_value || '';
    formValueMin = rule.value_min || '';
    formValueMax = rule.value_max || '';
    formValueMinProperty = rule.value_min_property || '';
    formValueMaxProperty = rule.value_max_property || '';
    formValueMinOffset = rule.value_min_offset !== undefined && rule.value_min_offset !== null ? String(rule.value_min_offset) : '';
    formValueMaxOffset = rule.value_max_offset !== undefined && rule.value_max_offset !== null ? String(rule.value_max_offset) : '';
    formCompareProperty = rule.compare_property || '';
    formNamePattern = rule.name_pattern || '';
    formUniquenessScope = rule.uniqueness_scope || 'building';
    formUnit = rule.unit || '';
    formSeverity = rule.severity || 'Medium';
    formNeedsReview = rule.needs_review || 0;
    isModalOpen = true;
  }

  async function handleSaveRule() {
    if (!formRuleId.trim() || !formPropertyName.trim()) {
      alert('Rule ID and Property Name are required.');
      return;
    }

    try {
      const payload: Partial<Rule> = {
        rule_id: formRuleId,
        description: formDescription,
        mechanism: formMechanism,
        ruleset_id: formRulesetId,
        rule_category: formCategory,
        property_set: formPropertySet,
        property_name: formPropertyName,
        operator: formOperator,
        check_value: formCheckValue,
        value_min: formValueMin || null,
        value_max: formValueMax || null,
        value_min_property: formValueMinProperty || '',
        value_max_property: formValueMaxProperty || '',
        value_min_offset: formValueMinOffset || 0,
        value_max_offset: formValueMaxOffset || 0,
        compare_property: formCompareProperty || '',
        name_pattern: formNamePattern || '',
        uniqueness_scope: formUniquenessScope || 'building',
        unit: formUnit || '',
        severity: formSeverity,
        needs_review: formNeedsReview,
      };

      if (isEditing && editRuleId) {
        await rulesApi.update(editRuleId, payload);
      } else {
        await rulesApi.create(payload);
      }

      isModalOpen = false;
      await loadData();
    } catch (err: any) {
      alert(`Save failed: ${err.message}`);
    }
  }

  async function handleDelete(id: number, ruleId: string) {
    if (!confirm(`Delete rule "${ruleId}"?`)) return;
    try {
      await rulesApi.delete(id);
      rules = rules.filter((r) => r.id !== id);
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  }
</script>

<div class="space-y-6 max-w-6xl mx-auto">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Library</div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">Rules Catalog</h1>
      <p class="text-xs sm:text-sm text-slate-400">Engineering criteria for corrosion, seismic clearance, and architectural building codes.</p>
    </div>

    <div class="flex items-center gap-2">
      <button
        type="button"
        on:click={handleSeedRules}
        class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 transition-colors"
        title="Seed engine rulesets: GC-001, CC-001, MC-001"
      >
        <Database class="w-3.5 h-3.5 text-emerald-400" />
        <span>Seed Engines</span>
      </button>

      {#if selectedFolderId}
        <a
          href={ruleExtractionApi.getIdsExportUrl(selectedFolderId)}
          class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 transition-colors"
          title="Export current ruleset into buildingSMART IDS XML"
        >
          <Download class="w-3.5 h-3.5 text-blue-400" />
          <span>Export IDS</span>
        </a>
      {/if}

      <button
        type="button"
        on:click={openCreateModal}
        class="inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02]"
      >
        <Plus class="w-3.5 h-3.5" />
        <span>New Rule</span>
      </button>
    </div>
  </div>

  {#if error}
    <div class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
      {error}
    </div>
  {/if}

  {#if successMessage}
    <div class="p-4 rounded-xl bg-emerald-950/50 border border-emerald-800 text-emerald-300 text-xs flex items-center gap-2">
      <CheckCircle2 class="w-4 h-4 text-emerald-400 shrink-0" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- Main Grid: Folders Sidebar + Rules Table -->
  <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
    <!-- Folder tree sidebar -->
    <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
      <div class="text-xs font-bold uppercase tracking-wider text-slate-400 px-1">
        Ruleset Folders
      </div>
      <div class="space-y-1">
        <button
          type="button"
          on:click={() => (selectedFolderId = null)}
          class="w-full flex items-center justify-between px-2.5 py-2 rounded-xl text-xs font-medium transition-colors {!selectedFolderId ? 'bg-[#0071e3] text-white' : 'text-slate-400 hover:text-white hover:bg-slate-800/60'}"
        >
          <div class="flex items-center gap-2">
            <FolderOpen class="w-3.5 h-3.5" />
            <span>All Rules</span>
          </div>
          <span class="text-[10px] opacity-75">{rules.length}</span>
        </button>

        {#each folders as folder}
          <button
            type="button"
            on:click={() => (selectedFolderId = folder.ruleset_id)}
            class="w-full flex items-center justify-between px-2.5 py-2 rounded-xl text-xs font-medium transition-colors {selectedFolderId === folder.ruleset_id ? 'bg-[#0071e3] text-white' : 'text-slate-400 hover:text-white hover:bg-slate-800/60'}"
          >
            <div class="flex items-center gap-2 truncate">
              <Folder class="w-3.5 h-3.5 shrink-0" />
              <span class="truncate">{folder.display_name}</span>
            </div>
            <span class="text-[10px] opacity-75 ml-2 shrink-0">{folder.rules.length}</span>
          </button>
        {/each}
      </div>
    </div>

    <!-- Rules Table Area -->
    <div class="md:col-span-3 space-y-4">
      <!-- Search & Filters -->
      <div class="p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col sm:flex-row items-center gap-3">
        <div class="relative flex-1 w-full">
          <Search class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            bind:value={searchQuery}
            placeholder="Search rules by ID, description, property..."
            class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
          />
        </div>

        <select
          bind:value={selectedMechanism}
          class="bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        >
          <option value="all">All Mechanisms</option>
          <option value="CODE">Building Code</option>
          <option value="GC-001">Galvanic (GC-001)</option>
          <option value="CC-001">Crevice (CC-001)</option>
          <option value="MC-001">Microbiological (MC-001)</option>
          <option value="SEISMIC">Seismic Clearance</option>
        </select>

        <label class="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer whitespace-nowrap">
          <input
            type="checkbox"
            bind:checked={filterNeedsReview}
            class="rounded border-slate-700 bg-slate-950 text-[#0071e3]"
          />
          <span>Needs Review</span>
        </label>
      </div>

      <!-- Table -->
      <div class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-900/40">
        {#if isLoading}
          <div class="p-12 text-center text-xs text-slate-400">Loading compliance rules...</div>
        {:else if filteredRules.length === 0}
          <div class="p-12 text-center text-xs text-slate-500 space-y-2">
            <p>No rules found for this folder or filter criteria.</p>
          </div>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-300">
              <thead class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                <tr>
                  <th class="py-3 px-4">Rule Ref</th>
                  <th class="py-3 px-4">Mechanism</th>
                  <th class="py-3 px-4">Target Property</th>
                  <th class="py-3 px-4">Condition</th>
                  <th class="py-3 px-4">Severity</th>
                  <th class="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                {#each filteredRules as rule}
                  <tr class="hover:bg-slate-900/60 transition-colors">
                    <td class="py-3 px-4">
                      <div class="font-mono font-bold text-white">{rule.rule_id || `Rule #${rule.id}`}</div>
                      <div class="text-[11px] text-slate-400 truncate max-w-xs">{rule.description || 'No description'}</div>
                    </td>
                    <td class="py-3 px-4">
                      <span class="inline-block px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-300 font-mono">
                        {rule.mechanism || 'CODE'}
                      </span>
                    </td>
                    <td class="py-3 px-4 text-slate-300 font-mono text-[11px]">
                      <div>{rule.property_name || '-'}</div>
                      <div class="text-[10px] text-slate-500">{rule.property_set || 'Pset_Compliance'}</div>
                    </td>
                    <td class="py-3 px-4 font-mono text-cyan-300">
                      {#if rule.operator === 'field_consistency'}
                        <div class="flex flex-col gap-0.5">
                          <span class="text-[11px] text-amber-300">≡ {rule.compare_property || 'same element'}</span>
                          {#if rule.name_pattern}
                            <span class="text-[10px] text-slate-500 font-sans">pattern: {rule.name_pattern}</span>
                          {/if}
                        </div>
                      {:else if rule.operator === 'unique_within_scope'}
                        <div class="text-[11px] text-purple-300">
                          <span>unique ({rule.uniqueness_scope || 'building'})</span>
                        </div>
                      {:else if rule.value_min_property || rule.value_max_property}
                        <div class="text-[11px] text-emerald-300">
                          <span>relative [{rule.value_min_property || '0'}..{rule.value_max_property || '∞'}]</span>
                        </div>
                      {:else}
                        <span>{rule.operator || '=='} {rule.check_value || '-'} {rule.unit || ''}</span>
                      {/if}
                      {#if rule.needs_review}
                        <span class="inline-block mt-1 px-1.5 py-0.2 rounded text-[9px] font-sans font-medium bg-amber-950/70 border border-amber-800 text-amber-400">
                          Needs Review
                        </span>
                      {/if}
                    </td>
                    <td class="py-3 px-4">
                      <span class="inline-block px-2 py-0.5 rounded text-[10px] font-semibold {rule.severity === 'Critical' || rule.severity === 'mandatory' ? 'bg-red-950/60 text-red-400 border border-red-800/60' : rule.severity === 'High' ? 'bg-orange-950/60 text-orange-400 border border-orange-800/60' : 'bg-yellow-950/60 text-yellow-400 border border-yellow-800/60'}">
                        {rule.severity}
                      </span>
                    </td>
                    <td class="py-3 px-4 text-right whitespace-nowrap">
                      <div class="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          on:click={() => openEditModal(rule)}
                          class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                          title="Edit rule"
                        >
                          <Edit3 class="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          on:click={() => handleDelete(rule.id, rule.rule_id || '')}
                          class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                          title="Delete rule"
                        >
                          <Trash2 class="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>

<!-- Rule Edit/Create Modal -->
{#if isModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-2xl rounded-2xl shadow-2xl p-6 space-y-4 max-h-[90vh] flex flex-col">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <h2 class="text-base font-bold text-white">{isEditing ? 'Edit Rule' : 'Create New Rule'}</h2>
        <button
          type="button"
          on:click={() => (isModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="space-y-4 overflow-y-auto pr-1 flex-1">
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label for="rule-id" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Rule ID *</label>
            <input
              id="rule-id"
              type="text"
              bind:value={formRuleId}
              placeholder="e.g. OBC-9.9.4.2"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            />
          </div>
          <div>
            <label for="rule-mechanism" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Mechanism</label>
            <select
              id="rule-mechanism"
              bind:value={formMechanism}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            >
              <option value="CODE">CODE</option>
              <option value="GC-001">GC-001</option>
              <option value="CC-001">CC-001</option>
              <option value="MC-001">MC-001</option>
              <option value="SEISMIC">SEISMIC</option>
            </select>
          </div>
        </div>

        <div>
          <label for="rule-desc" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Description</label>
          <textarea
            id="rule-desc"
            bind:value={formDescription}
            rows="2"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
          ></textarea>
        </div>

        <div class="grid grid-cols-3 gap-3">
          <div>
            <label for="rule-pset" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Property Set</label>
            <input
              id="rule-pset"
              type="text"
              bind:value={formPropertySet}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            />
          </div>
          <div>
            <label for="rule-pname" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Property Name *</label>
            <input
              id="rule-pname"
              type="text"
              bind:value={formPropertyName}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            />
          </div>
          <div>
            <label for="rule-unit" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Unit</label>
            <input
              id="rule-unit"
              type="text"
              bind:value={formUnit}
              placeholder="e.g. mm, min, m²"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label for="rule-op" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Operator</label>
            <select
              id="rule-op"
              bind:value={formOperator}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            >
              <option value="==">== (Exact match)</option>
              <option value="!=">!= (Not equal)</option>
              <option value=">">&gt; (Greater than)</option>
              <option value=">=">&gt;= (Greater than or equal)</option>
              <option value="<">&lt; (Less than)</option>
              <option value="<=">&lt;= (Less than or equal)</option>
              <option value="exists">exists</option>
              <option value="not_exists">not_exists</option>
              <option value="matches">matches (Regex)</option>
              <option value="field_consistency">field_consistency (Element match)</option>
              <option value="unique_within_scope">unique_within_scope (Uniqueness)</option>
            </select>
          </div>
          <div>
            <label for="rule-val" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Expected / Target Value</label>
            <input
              id="rule-val"
              type="text"
              bind:value={formCheckValue}
              placeholder="Literal value or threshold"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            />
          </div>
        </div>

        <!-- Field Consistency section -->
        {#if formOperator === 'field_consistency'}
          <div class="p-3 rounded-xl bg-slate-950 border border-amber-900/40 space-y-2.5">
            <div class="text-[11px] font-bold text-amber-400 uppercase tracking-wider">
              Field Consistency (Element-to-Element Property Match)
            </div>
            <p class="text-[11px] text-slate-400">
              Validates that Property Name's value matches another property on the SAME element (e.g. wall Name matches Cod_Object).
            </p>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label for="rule-compare-prop" class="block text-[11px] font-semibold text-slate-300 mb-1">Compare Property</label>
                <input
                  id="rule-compare-prop"
                  type="text"
                  bind:value={formCompareProperty}
                  placeholder="e.g. Cod_Object"
                  class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
                />
              </div>
              <div>
                <label for="rule-name-pattern" class="block text-[11px] font-semibold text-slate-300 mb-1">Name Pattern (Regex extraction)</label>
                <input
                  id="rule-name-pattern"
                  type="text"
                  bind:value={formNamePattern}
                  placeholder="e.g. ([A-Z]+)_.*_(\\d+)$"
                  class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
                />
              </div>
            </div>
          </div>
        {/if}

        <!-- Uniqueness Scope section -->
        {#if formOperator === 'unique_within_scope'}
          <div class="p-3 rounded-xl bg-slate-950 border border-purple-900/40 space-y-2.5">
            <div class="text-[11px] font-bold text-purple-400 uppercase tracking-wider">
              Scope Uniqueness Verification
            </div>
            <p class="text-[11px] text-slate-400">
              Ensures Property Name's value is unique across elements within the selected building hierarchy scope.
            </p>
            <div>
              <label for="rule-unique-scope" class="block text-[11px] font-semibold text-slate-300 mb-1">Uniqueness Scope</label>
              <select
                id="rule-unique-scope"
                bind:value={formUniquenessScope}
                class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
              >
                <option value="building">building (entire model)</option>
                <option value="storey">storey (same floor)</option>
                <option value="space">storey + space (same room)</option>
              </select>
            </div>
          </div>
        {/if}

        <!-- Relative Bounds Section -->
        <div class="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2.5">
          <div class="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
            Relative Dynamic Bounds & Offsets (Optional)
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="rule-min-prop" class="block text-[11px] font-semibold text-slate-400 mb-1">Min Dynamic Property / Offset</label>
              <div class="grid grid-cols-2 gap-2">
                <input
                  id="rule-min-prop"
                  type="text"
                  bind:value={formValueMinProperty}
                  placeholder="e.g. Run"
                  class="bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
                />
                <input
                  type="number"
                  bind:value={formValueMinOffset}
                  placeholder="Offset (0)"
                  class="bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
                />
              </div>
            </div>
            <div>
              <label for="rule-max-prop" class="block text-[11px] font-semibold text-slate-400 mb-1">Max Dynamic Property / Offset</label>
              <div class="grid grid-cols-2 gap-2">
                <input
                  id="rule-max-prop"
                  type="text"
                  bind:value={formValueMaxProperty}
                  placeholder="e.g. Run"
                  class="bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
                />
                <input
                  type="number"
                  bind:value={formValueMaxOffset}
                  placeholder="Offset (+25)"
                  class="bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
                />
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label for="rule-sev" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Severity</label>
            <select
              id="rule-sev"
              bind:value={formSeverity}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            >
              <option value="mandatory">Mandatory</option>
              <option value="recommended">Recommended</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>
          <div>
            <label for="rule-ruleset" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Ruleset ID</label>
            <input
              id="rule-ruleset"
              type="text"
              bind:value={formRulesetId}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            />
          </div>
        </div>

        <div>
          <label class="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={formNeedsReview === 1}
              on:change={(e) => (formNeedsReview = e.currentTarget.checked ? 1 : 0)}
              class="rounded border-slate-700 bg-slate-950 text-[#0071e3]"
            />
            <span>Flag for engineering review (Needs Review)</span>
          </label>
        </div>
      </div>

      <div class="flex justify-end gap-2 pt-3 border-t border-slate-800">
        <button
          type="button"
          on:click={() => (isModalOpen = false)}
          class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white"
        >
          Cancel
        </button>
        <button
          type="button"
          on:click={handleSaveRule}
          class="px-5 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white"
        >
          Save Rule
        </button>
      </div>
    </div>
  </div>
{/if}
