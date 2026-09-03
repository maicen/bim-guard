<script lang="ts">
  import { untrack } from "svelte";
  import { SlidersHorizontal } from "lucide-svelte";
  import { rulesApi } from "../api";
  import type { BSDDClassItem, BSDDPropertyItem, Rule, RulesetCategory } from "../types";
  import type { IfcPropertySuggestion } from "../archDomains";
  import BsddAutocomplete from "./BsddAutocomplete.svelte";

  interface Props {
    editingRule?: Rule | null;
    defaultRulesetId?: string;
    defaultCategory?: RulesetCategory;
    /**
     * When set, the rule's target IFC class is fixed (shown read-only) instead
     * of a free-text field — used when this form is opened from a specific
     * element-category page (e.g. Doors) so every rule created there is
     * correctly scoped without the user having to know the IFC class name.
     */
    lockedTargetIfcClass?: string | null;
    /**
     * Suggested property_name/property_set pairs for the locked target class,
     * offered as autocomplete — the field stays free text so any property can
     * still be typed.
     */
    propertySuggestions?: IfcPropertySuggestion[];
    /**
     * Hides the advanced/rarely-needed fields (mechanism, ruleset override,
     * field-consistency, uniqueness scope, dynamic ranges, needs-review) for
     * contexts — like the Manual Rule Editor — that just want a quick
     * property check against a known element type.
     */
    compact?: boolean;
    onCancel: () => void;
    onSaved: (rule: Rule) => void;
  }

  let {
    editingRule = null,
    defaultRulesetId = "BUILDING-CODE-PART9",
    defaultCategory = "Arch",
    lockedTargetIfcClass = null,
    propertySuggestions = [],
    compact = false,
    onCancel,
    onSaved,
  }: Props = $props();

  // The form seeds its fields from `editingRule` once and then owns them —
  // re-deriving would discard whatever the user has typed. RulesView and
  // ManualRuleEditorView both mount this inside an {#if}, so it remounts for
  // each rule; untrack states that the one-time read is deliberate.
  const seed = untrack(() => editingRule);
  const seedRulesetId = untrack(() => defaultRulesetId);
  const seedCategory = untrack(() => defaultCategory);
  const seedLockedClass = untrack(() => lockedTargetIfcClass);

  const isEditing = !!seed;
  const formInstanceId = Math.random().toString(36).slice(2, 8);

  let formRuleId = $state(seed?.rule_id || "");
  let formDescription = $state(seed?.description || "");
  let formMechanism = $state(seed?.mechanism || "CODE");
  let formRulesetId = $state(seed?.ruleset_id || seedRulesetId);
  // Carried through from the edited rule; not user-editable in this form.
  const formCategory = seed?.rule_category || "property_check";
  let formDomainCategory: RulesetCategory = $state(
    (seed?.category as RulesetCategory) || seedCategory,
  );
  let formTargetIfcClass = $state(seed?.target_ifc_class || seedLockedClass || "");
  let formPropertySet = $state(seed?.property_set || "Pset_Compliance");
  let formPropertyName = $state(seed?.property_name || "");
  let formOperator = $state(seed?.operator || "==");
  let formCheckValue = $state(seed?.check_value || "");

  // The compliance engine always scales a length property's real IFC value to
  // millimetres before comparing (ifc_reader._resolve_element_property,
  // Pass 8) — regardless of the source model's own declared unit — so a
  // dimensional rule's check_value has to already be in millimetres or the
  // comparison is silently wrong. This lets the author type in whatever unit
  // is natural and converts it to mm right before saving.
  const UNIT_TO_MM: Record<string, number> = { mm: 1, cm: 10, m: 1000, in: 25.4, ft: 304.8 };
  let formValueInputUnit = $state("mm");

  let selectedPropertyMeta = $derived(propertySuggestions.find((p) => p.name === formPropertyName));
  let isLengthProperty = $derived(selectedPropertyMeta?.unit === "mm");
  let convertedValuePreview = $derived(
    isLengthProperty &&
      formValueInputUnit !== "mm" &&
      formCheckValue.trim() &&
      !isNaN(Number(formCheckValue))
      ? `= ${(Number(formCheckValue) * UNIT_TO_MM[formValueInputUnit]).toFixed(2)} mm`
      : "",
  );

  function applyPropertySuggestion() {
    const match = propertySuggestions.find((p) => p.name === formPropertyName);
    if (match) formPropertySet = match.propertySet;
    formValueInputUnit = "mm";
  }

  // bSDD-sourced picks. A class item narrows target_ifc_class only; a
  // property item also carries the property set and unit bSDD standardizes
  // for it, so filling those saves the retyping applyPropertySuggestion above
  // does for the per-category suggestion list.
  function handleTargetClassPick(item: BSDDClassItem | BSDDPropertyItem) {
    if ("code" in item) formTargetIfcClass = item.code;
  }

  function handlePropertyNamePick(item: BSDDClassItem | BSDDPropertyItem) {
    if ("code" in item) return;
    formPropertyName = item.name;
    if (item.property_set) formPropertySet = item.property_set;
    if (item.units) formUnit = item.units;
    formValueInputUnit = "mm";
  }

  const formValueMin = seed?.value_min || "";
  const formValueMax = seed?.value_max || "";
  let formValueMinProperty = $state(seed?.value_min_property || "");
  let formValueMaxProperty = $state(seed?.value_max_property || "");
  let formValueMinOffset = $state(
    seed?.value_min_offset !== undefined && seed?.value_min_offset !== null
      ? String(seed.value_min_offset)
      : "",
  );
  let formValueMaxOffset = $state(
    seed?.value_max_offset !== undefined && seed?.value_max_offset !== null
      ? String(seed.value_max_offset)
      : "",
  );
  let formCompareProperty = $state(seed?.compare_property || "");
  let formNamePattern = $state(seed?.name_pattern || "");
  let formUniquenessScope = $state(seed?.uniqueness_scope || "building");
  let formUnit = $state(seed?.unit || "");
  let formSeverity = $state(seed?.severity || "Medium");
  let formNeedsReview = $state(seed?.needs_review || 0);

  let isSaving = $state(false);
  let saveError = $state("");

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
        isEditing && seed
          ? await rulesApi.update(seed.id, payload)
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
    <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300">
      {saveError}
    </div>
  {/if}

  {#if compact}
    <div class="grid grid-cols-2 gap-3">
      <div>
        <label
          for="rule-id"
          class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
          >Rule ID *</label
        >
        <input
          id="rule-id"
          type="text"
          bind:value={formRuleId}
          placeholder="e.g. OBC-9.9.4.2"
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
        />
      </div>
      <div>
        <label
          for="rule-sev-top"
          class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
          >Severity</label
        >
        <select
          id="rule-sev-top"
          bind:value={formSeverity}
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
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
          class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
          >Rule ID *</label
        >
        <input
          id="rule-id"
          type="text"
          bind:value={formRuleId}
          placeholder="e.g. OBC-9.9.4.2"
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
        />
      </div>
      <div>
        <label
          for="rule-domain-category"
          class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
          >Category *</label
        >
        <select
          id="rule-domain-category"
          bind:value={formDomainCategory}
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
        >
          <option value="Arch">Arch</option>
          <option value="Piping">Piping</option>
          <option value="seismic">seismic</option>
        </select>
      </div>
      <div>
        <label
          for="rule-mechanism"
          class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
          >Mechanism</label
        >
        <select
          id="rule-mechanism"
          bind:value={formMechanism}
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
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
    <span class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300">
      Target IFC Class
    </span>
    {#if lockedTargetIfcClass}
      <div
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 font-mono text-xs text-slate-300"
      >
        {lockedTargetIfcClass}
      </div>
      <p class="mt-1 text-caption text-slate-500">
        Every rule added here targets this element type.
      </p>
    {:else}
      <BsddAutocomplete
        id="rule-target-ifc-class"
        mode="class"
        bind:value={formTargetIfcClass}
        placeholder="e.g. IfcDoor, IfcWindow (leave blank to apply to any element) — search bSDD as you type"
        onSelect={handleTargetClassPick}
        class="font-mono"
      />
    {/if}
  </div>

  <div>
    <label
      for="rule-desc"
      class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
      >Description</label
    >
    <textarea
      id="rule-desc"
      bind:value={formDescription}
      rows="2"
      class="w-full rounded-xl border border-slate-800 bg-slate-950 p-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
    ></textarea>
  </div>

  <div class="grid {compact ? 'grid-cols-1' : 'grid-cols-3'} gap-3">
    {#if !compact}
      <div>
        <label
          for="rule-pset"
          class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
          >Property Set</label
        >
        <input
          id="rule-pset"
          type="text"
          bind:value={formPropertySet}
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
        />
      </div>
    {/if}
    <div>
      <label
        for="rule-pname-{formInstanceId}"
        class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
        >Property *</label
      >
      {#if propertySuggestions.length}
        <select
          id="rule-pname-{formInstanceId}"
          bind:value={formPropertyName}
          onchange={applyPropertySuggestion}
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
        >
          <option value="" disabled>Choose a property…</option>
          {#each propertySuggestions as prop (prop.name)}
            <option value={prop.name}>{prop.label}</option>
          {/each}
        </select>
      {:else}
        <BsddAutocomplete
          id="rule-pname-{formInstanceId}"
          mode="property"
          bind:value={formPropertyName}
          placeholder="search bSDD as you type"
          onSelect={handlePropertyNamePick}
        />
      {/if}
    </div>
    {#if !compact}
      <div>
        <label
          for="rule-unit"
          class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
          >Unit</label
        >
        <input
          id="rule-unit"
          type="text"
          bind:value={formUnit}
          placeholder="e.g. mm, min, m²"
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
        />
      </div>
    {/if}
  </div>

  <div class="grid grid-cols-2 gap-3">
    <div>
      <label
        for="rule-op"
        class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
        >Operator</label
      >
      <select
        id="rule-op"
        bind:value={formOperator}
        class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
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
          <option value="field_consistency">field_consistency (Element match)</option>
          <option value="unique_within_scope">unique_within_scope (Uniqueness)</option>
        {/if}
      </select>
    </div>
    <div>
      <label
        for="rule-val"
        class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
        >Expected / Target Value</label
      >
      {#if isLengthProperty}
        <div class="flex gap-1.5">
          <input
            id="rule-val"
            type="text"
            bind:value={formCheckValue}
            placeholder="e.g. 2.03"
            class="min-w-0 flex-1 rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          />
          <select
            bind:value={formValueInputUnit}
            aria-label="Value unit"
            class="shrink-0 rounded-xl border border-slate-800 bg-slate-950 px-2 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            <option value="mm">mm</option>
            <option value="cm">cm</option>
            <option value="m">m</option>
            <option value="in">in</option>
            <option value="ft">ft</option>
          </select>
        </div>
        <p class="mt-1 h-3.5 text-caption text-slate-500">
          {convertedValuePreview ||
            "Compared in millimetres — the IFC unit BIM-Guard checks against."}
        </p>
      {:else}
        <input
          id="rule-val"
          type="text"
          bind:value={formCheckValue}
          placeholder="Literal value or threshold"
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
        />
      {/if}
    </div>
  </div>

  <!-- Field Consistency section -->
  {#if !compact && formOperator === "field_consistency"}
    <div class="space-y-2.5 rounded-xl border border-amber-900/40 bg-slate-950 p-3">
      <div class="text-caption font-bold uppercase tracking-wider text-amber-400">
        Field Consistency (Element-to-Element Property Match)
      </div>
      <p class="text-caption text-slate-400">
        Validates that Property Name's value matches another property on the SAME element (e.g. wall
        Name matches Cod_Object).
      </p>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label
            for="rule-compare-prop"
            class="mb-1 block text-caption font-semibold text-slate-300">Compare Property</label
          >
          <input
            id="rule-compare-prop"
            type="text"
            bind:value={formCompareProperty}
            placeholder="e.g. Cod_Object"
            class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          />
        </div>
        <div>
          <label
            for="rule-name-pattern"
            class="mb-1 block text-caption font-semibold text-slate-300"
            >Name Pattern (Regex extraction)</label
          >
          <input
            id="rule-name-pattern"
            type="text"
            bind:value={formNamePattern}
            placeholder="e.g. ([A-Z]+)_.*_(\d+)$"
            class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          />
        </div>
      </div>
    </div>
  {/if}

  <!-- Uniqueness Scope section -->
  {#if !compact && formOperator === "unique_within_scope"}
    <div class="space-y-2.5 rounded-xl border border-purple-900/40 bg-slate-950 p-3">
      <div class="text-caption font-bold uppercase tracking-wider text-purple-400">
        Scope Uniqueness Verification
      </div>
      <p class="text-caption text-slate-400">
        Ensures Property Name's value is unique across elements within the selected building
        hierarchy scope.
      </p>
      <div>
        <label for="rule-unique-scope" class="mb-1 block text-caption font-semibold text-slate-300"
          >Uniqueness Scope</label
        >
        <select
          id="rule-unique-scope"
          bind:value={formUniquenessScope}
          class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
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
    <div class="space-y-2.5 rounded-xl border border-slate-800 bg-slate-950 p-3">
      <div
        class="flex items-center gap-1.5 text-caption font-bold uppercase tracking-wider text-slate-300"
      >
        <SlidersHorizontal class="h-3.5 w-3.5 text-blue-400" />
        <span>Dynamic Property-Relative Range (Optional)</span>
      </div>
      <p class="text-caption text-slate-400">
        Compare target property dynamically against other properties on the same element with
        optional offsets (e.g. RiserHeight &lt;= 0.5 * StairHeight + 25mm).
      </p>

      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label for="rule-min-prop" class="mb-1 block text-caption font-semibold text-slate-300"
            >Min Dynamic Property / Offset</label
          >
          <div class="grid grid-cols-2 gap-2">
            <input
              id="rule-min-prop"
              type="text"
              bind:value={formValueMinProperty}
              placeholder="e.g. TreadWidth"
              class="rounded-xl border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
            <input
              type="number"
              bind:value={formValueMinOffset}
              placeholder="Offset (0)"
              class="rounded-xl border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
        </div>
        <div>
          <label for="rule-max-prop" class="mb-1 block text-caption font-semibold text-slate-300"
            >Max Dynamic Property / Offset</label
          >
          <div class="grid grid-cols-2 gap-2">
            <input
              id="rule-max-prop"
              type="text"
              bind:value={formValueMaxProperty}
              placeholder="e.g. TreadWidth"
              class="rounded-xl border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
            <input
              type="number"
              bind:value={formValueMaxOffset}
              placeholder="Offset (+25)"
              class="rounded-xl border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div>
        <label
          for="rule-sev"
          class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
          >Severity</label
        >
        <select
          id="rule-sev"
          bind:value={formSeverity}
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
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
          class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-300"
          >Ruleset ID</label
        >
        <input
          id="rule-ruleset"
          type="text"
          bind:value={formRulesetId}
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
        />
      </div>
    </div>

    <div>
      <label class="flex cursor-pointer items-center gap-2 text-xs text-slate-300">
        <input
          type="checkbox"
          checked={formNeedsReview === 1}
          onchange={(e) => (formNeedsReview = e.currentTarget.checked ? 1 : 0)}
          class="rounded border-slate-700 bg-slate-950 text-accent"
        />
        <span>Flag for engineering review (Needs Review)</span>
      </label>
    </div>
  {/if}

  <div class="flex justify-end gap-2 border-t border-slate-800 pt-3">
    <button
      type="button"
      onclick={onCancel}
      class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 hover:bg-slate-700"
    >
      Cancel
    </button>
    <button
      type="button"
      disabled={isSaving}
      onclick={handleSaveRule}
      class="rounded-full bg-accent px-5 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
    >
      {isSaving ? "Saving..." : "Save Rule"}
    </button>
  </div>
</div>
