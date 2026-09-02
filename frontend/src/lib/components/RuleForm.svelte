<script lang="ts">
  import { SlidersHorizontal } from "lucide-svelte";
  import { rulesApi } from "../api";
  import type { Rule, RulesetCategory } from "../types";
  import type { IfcPropertySuggestion } from "../archDomains";

  export let editingRule: Rule | null = null;
  export let defaultRulesetId = "BUILDING-CODE-PART9";
  export let defaultCategory: RulesetCategory = "Arch";
  // When set, the rule's target IFC class is fixed (shown read-only) instead
  // of a free-text field — used when this form is opened from a specific
  // element-category page (e.g. Doors) so every rule created there is
  // correctly scoped without the user having to know the IFC class name.
  export let lockedTargetIfcClass: string | null = null;
  // Suggested property_name/property_set pairs for the locked target class,
  // offered as autocomplete — the field stays free text so any property can
  // still be typed.
  export let propertySuggestions: IfcPropertySuggestion[] = [];
  // Hides the advanced/rarely-needed fields (mechanism, ruleset override,
  // field-consistency, uniqueness scope, dynamic ranges, needs-review) for
  // contexts — like the Manual Rule Editor — that just want a quick
  // property check against a known element type.
  export let compact = false;
  export let onCancel: () => void;
  export let onSaved: (rule: Rule) => void;

  const isEditing = !!editingRule;
  const formInstanceId = Math.random().toString(36).slice(2, 8);

  let formRuleId = editingRule?.rule_id || "";
  let formDescription = editingRule?.description || "";
  let formMechanism = editingRule?.mechanism || "CODE";
  let formRulesetId = editingRule?.ruleset_id || defaultRulesetId;
  let formCategory = editingRule?.rule_category || "property_check";
  let formDomainCategory: RulesetCategory =
    (editingRule?.category as RulesetCategory) || defaultCategory;
  let formTargetIfcClass =
    editingRule?.target_ifc_class || lockedTargetIfcClass || "";
  let formPropertySet = editingRule?.property_set || "Pset_Compliance";
  let formPropertyName = editingRule?.property_name || "";
  let formOperator = editingRule?.operator || "==";
  let formCheckValue = editingRule?.check_value || "";

  // The compliance engine always scales a length property's real IFC value to
  // millimetres before comparing (module2_ifc_read._resolve_element_property,
  // Pass 8) — regardless of the source model's own declared unit — so a
  // dimensional rule's check_value has to already be in millimetres or the
  // comparison is silently wrong. This lets the author type in whatever unit
  // is natural and converts it to mm right before saving.
  const UNIT_TO_MM: Record<string, number> = { mm: 1, cm: 10, m: 1000, in: 25.4, ft: 304.8 };
  let formValueInputUnit = "mm";

  $: selectedPropertyMeta = propertySuggestions.find((p) => p.name === formPropertyName);
  $: isLengthProperty = selectedPropertyMeta?.unit === "mm";
  $: convertedValuePreview =
    isLengthProperty && formValueInputUnit !== "mm" && formCheckValue.trim() && !isNaN(Number(formCheckValue))
      ? `= ${(Number(formCheckValue) * UNIT_TO_MM[formValueInputUnit]).toFixed(2)} mm`
      : "";

  function applyPropertySuggestion() {
    const match = propertySuggestions.find((p) => p.name === formPropertyName);
    if (match) formPropertySet = match.propertySet;
    formValueInputUnit = "mm";
  }

  let formValueMin = editingRule?.value_min || "";
  let formValueMax = editingRule?.value_max || "";
  let formValueMinProperty = editingRule?.value_min_property || "";
  let formValueMaxProperty = editingRule?.value_max_property || "";
  let formValueMinOffset =
    editingRule?.value_min_offset !== undefined &&
    editingRule?.value_min_offset !== null
      ? String(editingRule.value_min_offset)
      : "";
  let formValueMaxOffset =
    editingRule?.value_max_offset !== undefined &&
    editingRule?.value_max_offset !== null
      ? String(editingRule.value_max_offset)
      : "";
  let formCompareProperty = editingRule?.compare_property || "";
  let formNamePattern = editingRule?.name_pattern || "";
  let formUniquenessScope = editingRule?.uniqueness_scope || "building";
  let formUnit = editingRule?.unit || "";
  let formSeverity = editingRule?.severity || "Medium";
  let formNeedsReview = editingRule?.needs_review || 0;

  let isSaving = false;
  let saveError = "";

  async function handleSaveRule() {
    if (!formRuleId.trim() || !formPropertyName.trim()) {
      saveError = "Rule ID and Property Name are required.";
      return;
    }
    isSaving = true;
    saveError = "";
    try {
      // Convert the authored value into millimetres — the unit the compliance
      // engine always compares length properties in (see the UNIT_TO_MM
      // comment above) — so what gets saved is what actually gets checked.
      let finalCheckValue = formCheckValue;
      let finalUnit = formUnit || "";
      if (isLengthProperty) {
        finalUnit = "mm";
        if (
          formValueInputUnit !== "mm" &&
          formCheckValue.trim() &&
          !isNaN(Number(formCheckValue))
        ) {
          finalCheckValue = String(
            Math.round(Number(formCheckValue) * UNIT_TO_MM[formValueInputUnit] * 100) / 100,
          );
        }
      }

      const payload: Partial<Rule> = {
        rule_id: formRuleId,
        description: formDescription,
        mechanism: formMechanism,
        ruleset_id: formRulesetId,
        rule_category: formCategory,
        category: formDomainCategory,
        target_ifc_class: formTargetIfcClass || null,
        property_set: formPropertySet,
        property_name: formPropertyName,
        operator: formOperator,
        check_value: finalCheckValue,
        value_min: formValueMin || null,
        value_max: formValueMax || null,
        value_min_property: formValueMinProperty || "",
        value_max_property: formValueMaxProperty || "",
        value_min_offset: formValueMinOffset || "0",
        value_max_offset: formValueMaxOffset || "0",
        compare_property: formCompareProperty || "",
        name_pattern: formNamePattern || "",
        uniqueness_scope: formUniquenessScope || "building",
        unit: finalUnit,
        severity: formSeverity,
        needs_review: formNeedsReview,
      };

      const saved =
        isEditing && editingRule
          ? await rulesApi.update(editingRule.id, payload)
          : await rulesApi.create(payload);
      onSaved(saved);
    } catch (err: any) {
      saveError = `Save failed: ${err.message}`;
    } finally {
      isSaving = false;
    }
  }
</script>

<div class="space-y-4">
  {#if saveError}
    <div class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
      {saveError}
    </div>
  {/if}

  {#if compact}
    <div class="grid grid-cols-2 gap-3">
      <div>
        <label
          for="rule-id"
          class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
          >Rule ID *</label
        >
        <input
          id="rule-id"
          type="text"
          bind:value={formRuleId}
          placeholder="e.g. OBC-9.9.4.2"
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        />
      </div>
      <div>
        <label
          for="rule-sev-top"
          class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
          >Severity</label
        >
        <select
          id="rule-sev-top"
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
    </div>
  {:else}
    <div class="grid grid-cols-3 gap-3">
      <div>
        <label
          for="rule-id"
          class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
          >Rule ID *</label
        >
        <input
          id="rule-id"
          type="text"
          bind:value={formRuleId}
          placeholder="e.g. OBC-9.9.4.2"
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        />
      </div>
      <div>
        <label
          for="rule-domain-category"
          class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
          >Category *</label
        >
        <select
          id="rule-domain-category"
          bind:value={formDomainCategory}
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        >
          <option value="Arch">Arch</option>
          <option value="Piping">Piping</option>
          <option value="seismic">seismic</option>
        </select>
      </div>
      <div>
        <label
          for="rule-mechanism"
          class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
          >Mechanism</label
        >
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
  {/if}

  <div>
    <span class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
      Target IFC Class
    </span>
    {#if lockedTargetIfcClass}
      <div class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300">
        {lockedTargetIfcClass}
      </div>
      <p class="text-[11px] text-slate-500 mt-1">
        Every rule added here targets this element type.
      </p>
    {:else}
      <input
        id="rule-target-ifc-class"
        type="text"
        bind:value={formTargetIfcClass}
        placeholder="e.g. IfcDoor, IfcWindow (leave blank to apply to any element)"
        class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#0071e3]"
      />
    {/if}
  </div>

  <div>
    <label
      for="rule-desc"
      class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
      >Description</label
    >
    <textarea
      id="rule-desc"
      bind:value={formDescription}
      rows="2"
      class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
    ></textarea>
  </div>

  <div class="grid {compact ? 'grid-cols-1' : 'grid-cols-3'} gap-3">
    {#if !compact}
      <div>
        <label
          for="rule-pset"
          class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
          >Property Set</label
        >
        <input
          id="rule-pset"
          type="text"
          bind:value={formPropertySet}
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        />
      </div>
    {/if}
    <div>
      <label
        for="rule-pname-{formInstanceId}"
        class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
        >Property *</label
      >
      {#if propertySuggestions.length}
        <select
          id="rule-pname-{formInstanceId}"
          bind:value={formPropertyName}
          on:change={applyPropertySuggestion}
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        >
          <option value="" disabled>Choose a property…</option>
          {#each propertySuggestions as prop}
            <option value={prop.name}>{prop.label}</option>
          {/each}
        </select>
      {:else}
        <input
          id="rule-pname-{formInstanceId}"
          type="text"
          bind:value={formPropertyName}
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        />
      {/if}
    </div>
    {#if !compact}
      <div>
        <label
          for="rule-unit"
          class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
          >Unit</label
        >
        <input
          id="rule-unit"
          type="text"
          bind:value={formUnit}
          placeholder="e.g. mm, min, m²"
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        />
      </div>
    {/if}
  </div>

  <div class="grid grid-cols-2 gap-3">
    <div>
      <label
        for="rule-op"
        class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
        >Operator</label
      >
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
        {#if !compact}
          <option value="field_consistency"
            >field_consistency (Element match)</option
          >
          <option value="unique_within_scope"
            >unique_within_scope (Uniqueness)</option
          >
        {/if}
      </select>
    </div>
    <div>
      <label
        for="rule-val"
        class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
        >Expected / Target Value</label
      >
      {#if isLengthProperty}
        <div class="flex gap-1.5">
          <input
            id="rule-val"
            type="text"
            bind:value={formCheckValue}
            placeholder="e.g. 2.03"
            class="flex-1 min-w-0 bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
          />
          <select
            bind:value={formValueInputUnit}
            aria-label="Value unit"
            class="shrink-0 bg-slate-950 border border-slate-800 rounded-xl px-2 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
          >
            <option value="mm">mm</option>
            <option value="cm">cm</option>
            <option value="m">m</option>
            <option value="in">in</option>
            <option value="ft">ft</option>
          </select>
        </div>
        <p class="text-[11px] text-slate-500 mt-1 h-3.5">
          {convertedValuePreview || "Compared in millimetres — the IFC unit BIM-Guard checks against."}
        </p>
      {:else}
        <input
          id="rule-val"
          type="text"
          bind:value={formCheckValue}
          placeholder="Literal value or threshold"
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        />
      {/if}
    </div>
  </div>

  <!-- Field Consistency section -->
  {#if !compact && formOperator === "field_consistency"}
    <div class="p-3 rounded-xl bg-slate-950 border border-amber-900/40 space-y-2.5">
      <div class="text-[11px] font-bold text-amber-400 uppercase tracking-wider">
        Field Consistency (Element-to-Element Property Match)
      </div>
      <p class="text-[11px] text-slate-400">
        Validates that Property Name's value matches another property on
        the SAME element (e.g. wall Name matches Cod_Object).
      </p>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label
            for="rule-compare-prop"
            class="block text-[11px] font-semibold text-slate-300 mb-1"
            >Compare Property</label
          >
          <input
            id="rule-compare-prop"
            type="text"
            bind:value={formCompareProperty}
            placeholder="e.g. Cod_Object"
            class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
          />
        </div>
        <div>
          <label
            for="rule-name-pattern"
            class="block text-[11px] font-semibold text-slate-300 mb-1"
            >Name Pattern (Regex extraction)</label
          >
          <input
            id="rule-name-pattern"
            type="text"
            bind:value={formNamePattern}
            placeholder="e.g. ([A-Z]+)_.*_(\d+)$"
            class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
          />
        </div>
      </div>
    </div>
  {/if}

  <!-- Uniqueness Scope section -->
  {#if !compact && formOperator === "unique_within_scope"}
    <div class="p-3 rounded-xl bg-slate-950 border border-purple-900/40 space-y-2.5">
      <div class="text-[11px] font-bold text-purple-400 uppercase tracking-wider">
        Scope Uniqueness Verification
      </div>
      <p class="text-[11px] text-slate-400">
        Ensures Property Name's value is unique across elements within the
        selected building hierarchy scope.
      </p>
      <div>
        <label
          for="rule-unique-scope"
          class="block text-[11px] font-semibold text-slate-300 mb-1"
          >Uniqueness Scope</label
        >
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

  {#if !compact}
    <!-- Dynamic relative threshold section -->
    <div class="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2.5">
      <div class="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
        <SlidersHorizontal class="w-3.5 h-3.5 text-blue-400" />
        <span>Dynamic Property-Relative Range (Optional)</span>
      </div>
      <p class="text-[11px] text-slate-400">
        Compare target property dynamically against other properties on the
        same element with optional offsets (e.g. RiserHeight &lt;= 0.5 *
        StairHeight + 25mm).
      </p>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label
            for="rule-min-prop"
            class="block text-[11px] font-semibold text-slate-300 mb-1"
            >Min Dynamic Property / Offset</label
          >
          <div class="grid grid-cols-2 gap-2">
            <input
              id="rule-min-prop"
              type="text"
              bind:value={formValueMinProperty}
              placeholder="e.g. TreadWidth"
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
          <label
            for="rule-max-prop"
            class="block text-[11px] font-semibold text-slate-300 mb-1"
            >Max Dynamic Property / Offset</label
          >
          <div class="grid grid-cols-2 gap-2">
            <input
              id="rule-max-prop"
              type="text"
              bind:value={formValueMaxProperty}
              placeholder="e.g. TreadWidth"
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
        <label
          for="rule-sev"
          class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
          >Severity</label
        >
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
        <label
          for="rule-ruleset"
          class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1"
          >Ruleset ID</label
        >
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
  {/if}

  <div class="flex justify-end gap-2 pt-3 border-t border-slate-800">
    <button
      type="button"
      on:click={onCancel}
      class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white"
    >
      Cancel
    </button>
    <button
      type="button"
      disabled={isSaving}
      on:click={handleSaveRule}
      class="px-5 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white disabled:opacity-50"
    >
      {isSaving ? "Saving..." : "Save Rule"}
    </button>
  </div>
</div>
