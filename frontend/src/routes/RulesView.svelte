<script lang="ts">
  import { onMount } from 'svelte';
  import { rulesApi } from '../lib/api';
  import type { Rule, RuleFolder } from '../lib/types';

  let rules: Rule[] = [];
  let folders: RuleFolder[] = [];
  let loading = true;
  let error = '';

  let selectedMechanism = 'all';
  let searchQuery = '';

  let showCreateModal = false;
  let newRuleId = '';
  let newDesc = '';
  let newMechanism = 'CODE';
  let newPropertySet = '';
  let newPropertyName = '';
  let newCheckValue = '';
  let newSeverity = 'recommended';
  let creating = false;

  async function loadRulesData() {
    loading = true;
    error = '';
    try {
      const [rulesData, foldersData] = await Promise.all([
        rulesApi.list(),
        rulesApi.folders(),
      ]);
      rules = rulesData;
      folders = foldersData;
    } catch (err: any) {
      error = err.message || 'Failed to load rules.';
    } finally {
      loading = false;
    }
  }

  $: filteredRules = rules.filter((r) => {
    const matchesMech = selectedMechanism === 'all' || r.mechanism === selectedMechanism;
    const matchesSearch =
      !searchQuery ||
      (r.rule_id || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.description || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.property_name || '').toLowerCase().includes(searchQuery.toLowerCase());
    return matchesMech && matchesSearch;
  });

  async function handleCreateRule() {
    if (!newRuleId.trim()) return;
    creating = true;
    try {
      await rulesApi.create({
        rule_id: newRuleId.trim(),
        description: newDesc.trim(),
        mechanism: newMechanism,
        property_set: newPropertySet.trim() || undefined,
        property_name: newPropertyName.trim() || undefined,
        check_value: newCheckValue.trim() || undefined,
        severity: newSeverity,
      });
      showCreateModal = false;
      newRuleId = '';
      newDesc = '';
      await loadRulesData();
    } catch (err: any) {
      alert(`Create rule failed: ${err.message}`);
    } finally {
      creating = false;
    }
  }

  async function handleDeleteRule(id: number) {
    if (!confirm('Are you sure you want to delete this rule?')) return;
    try {
      await rulesApi.delete(id);
      await loadRulesData();
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  }

  onMount(() => {
    loadRulesData();
  });
</script>

<div class="space-y-6">
  <!-- Header -->
  <div class="flex items-center justify-between flex-wrap gap-4">
    <div>
      <h1 class="text-2xl font-bold tracking-tight text-white">Rule Library</h1>
      <p class="text-sm text-slate-400 mt-1">Regulatory specifications, property checks, and physics thresholds</p>
    </div>
    <button
      on:click={() => (showCreateModal = true)}
      class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold shadow-lg shadow-emerald-600/20 transition-colors"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
      </svg>
      Add Rule
    </button>
  </div>

  {#if error}
    <div class="p-4 rounded-lg bg-rose-950/40 border border-rose-800 text-rose-300 text-sm">
      {error}
    </div>
  {/if}

  <!-- Filters Toolbar -->
  <div class="flex flex-col sm:flex-row gap-3 items-center justify-between">
    <div class="w-full sm:w-80">
      <input
        type="text"
        placeholder="Search rule ID, description, property..."
        bind:value={searchQuery}
        class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
      />
    </div>
    <div class="flex gap-2 w-full sm:w-auto">
      <select
        bind:value={selectedMechanism}
        class="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
      >
        <option value="all">All Mechanisms</option>
        <option value="GC-001">GC-001 (Galvanic)</option>
        <option value="CC-001">CC-001 (Crevice)</option>
        <option value="MC-001">MC-001 (MIC)</option>
        <option value="CODE">Building Code</option>
        <option value="IFC">IFC Standard</option>
      </select>
    </div>
  </div>

  <!-- Rules Table -->
  <div class="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-xl">
    <div class="overflow-x-auto">
      <table class="w-full text-left text-sm">
        <thead class="bg-slate-950/70 border-b border-slate-800 text-xs uppercase text-slate-400 font-semibold">
          <tr>
            <th class="py-3 px-4">Rule Ref</th>
            <th class="py-3 px-4">Mechanism</th>
            <th class="py-3 px-4">Category</th>
            <th class="py-3 px-4">Property Target</th>
            <th class="py-3 px-4">Description</th>
            <th class="py-3 px-4">Severity</th>
            <th class="py-3 px-4 text-right">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-800/60">
          {#if loading}
            <tr>
              <td colspan="7" class="py-8 text-center text-slate-400">Loading rules from API...</td>
            </tr>
          {:else if filteredRules.length === 0}
            <tr>
              <td colspan="7" class="py-8 text-center text-slate-400">No rules match your filters.</td>
            </tr>
          {:else}
            {#each filteredRules as rule}
              <tr class="hover:bg-slate-800/30 transition-colors">
                <td class="py-3 px-4 font-mono font-semibold text-emerald-400 whitespace-nowrap">
                  {rule.rule_id || `ID-${rule.id}`}
                </td>
                <td class="py-3 px-4 whitespace-nowrap">
                  <span class="px-2 py-0.5 rounded text-xs font-mono font-medium bg-slate-800 text-slate-300 border border-slate-700">
                    {rule.mechanism || 'CODE'}
                  </span>
                </td>
                <td class="py-3 px-4 text-xs text-slate-300 whitespace-nowrap">
                  {rule.rule_category || 'property_check'}
                </td>
                <td class="py-3 px-4 text-xs font-mono text-slate-300 whitespace-nowrap">
                  {rule.property_name ? `${rule.property_set || 'Pset'}.${rule.property_name}` : '—'}
                </td>
                <td class="py-3 px-4 text-slate-200 max-w-md">
                  <div class="line-clamp-2">{rule.description || 'No description provided.'}</div>
                </td>
                <td class="py-3 px-4 whitespace-nowrap">
                  <span class="px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wider border {rule.severity === 'mandatory' ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'}">
                    {rule.severity || 'recommended'}
                  </span>
                </td>
                <td class="py-3 px-4 text-right whitespace-nowrap">
                  <button
                    on:click={() => handleDeleteRule(rule.id)}
                    class="p-1 rounded text-slate-500 hover:text-rose-400 transition-colors"
                    title="Delete rule"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                  </button>
                </td>
              </tr>
            {/each}
          {/if}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Create Rule Modal -->
  {#if showCreateModal}
    <div class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div class="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl space-y-4">
        <h2 class="text-lg font-bold text-white">Create Compliance Rule</h2>
        <div class="space-y-3">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Rule Ref / Code *
              </label>
              <input
                type="text"
                bind:value={newRuleId}
                placeholder="e.g. GC-001.04"
                class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Mechanism
              </label>
              <select
                bind:value={newMechanism}
                class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
              >
                <option value="CODE">CODE (Building Code)</option>
                <option value="GC-001">GC-001 (Galvanic)</option>
                <option value="CC-001">CC-001 (Crevice)</option>
                <option value="MC-001">MC-001 (MIC)</option>
              </select>
            </div>
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Description
            </label>
            <textarea
              bind:value={newDesc}
              rows="2"
              placeholder="Human description of compliance requirement..."
              class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
            ></textarea>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Property Set
              </label>
              <input
                type="text"
                bind:value={newPropertySet}
                placeholder="e.g. Pset_PipeSegmentCommon"
                class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Property Name
              </label>
              <input
                type="text"
                bind:value={newPropertyName}
                placeholder="e.g. NominalDiameter"
                class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Expected Value
              </label>
              <input
                type="text"
                bind:value={newCheckValue}
                placeholder="e.g. >= 100"
                class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Severity
              </label>
              <select
                bind:value={newSeverity}
                class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
              >
                <option value="recommended">Recommended</option>
                <option value="mandatory">Mandatory</option>
              </select>
            </div>
          </div>
        </div>

        <div class="flex items-center justify-end gap-2 pt-4 border-t border-slate-800">
          <button
            on:click={() => (showCreateModal = false)}
            class="px-3.5 py-1.5 rounded-lg text-sm text-slate-400 hover:text-white"
          >
            Cancel
          </button>
          <button
            on:click={handleCreateRule}
            disabled={creating || !newRuleId.trim()}
            class="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold shadow"
          >
            {creating ? 'Saving...' : 'Save Rule'}
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

