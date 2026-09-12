<script lang="ts">
  import { Upload } from "lucide-svelte";
  import Modal from "../Modal.svelte";
  import RulesetImportForm from "../RulesetImportForm.svelte";
  import type { IdsImportResult } from "../../types";

  interface Props {
    isOpen: boolean;
    defaultRulesetId?: string;
    onClose: () => void;
    onImported: (result: IdsImportResult) => void;
  }

  let {
    isOpen = false,
    defaultRulesetId = "",
    onClose,
    onImported,
  }: Props = $props();
</script>

<Modal
  {isOpen}
  title="Import Ruleset"
  subtitle="Parse a buildingSMART IDS (.ids/XML) or BIM-Guard JSON ruleset file into new rules"
  icon={Upload}
  maxWidth="max-w-lg"
  {onClose}
>
  <RulesetImportForm
    {defaultRulesetId}
    onCancel={onClose}
    onImported={(result) => {
      onImported(result);
      onClose();
    }}
  />
</Modal>
