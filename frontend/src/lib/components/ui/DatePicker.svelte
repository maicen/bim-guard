<script lang="ts" module>
  import { DatePicker as DatePickerPrimitive } from "bits-ui";

  export const DatePickerRoot = DatePickerPrimitive.Root;
  export const DatePickerTrigger = DatePickerPrimitive.Trigger;
  export const DatePickerContent = DatePickerPrimitive.Content;
  export const DatePickerCalendar = DatePickerPrimitive.Calendar;
  export const DatePickerInput = DatePickerPrimitive.Input;
</script>

<script lang="ts">
  import { Calendar as CalendarIcon, ChevronLeft, ChevronRight } from "lucide-svelte";
  import { parseDate, type DateValue } from "@internationalized/date";
  import { cn } from "../../utils/cn";

  interface Props {
    value?: DateValue | string;
    onValueChange?: (val: string | DateValue | undefined) => void;
    placeholder?: string;
    disabled?: boolean;
    class?: string;
  }

  let {
    value = $bindable(),
    onValueChange,
    placeholder = "Pick a date",
    disabled = false,
    class: className,
  }: Props = $props();

  let parsedValue = $derived.by(() => {
    if (!value) return undefined;
    if (typeof value === "string") {
      try {
        return parseDate(value.split("T")[0]);
      } catch {
        return undefined;
      }
    }
    return value;
  });

  function handleValueChange(newVal: DateValue | undefined) {
    if (typeof value === "string" || value === undefined) {
      const strVal = newVal ? newVal.toString() : "";
      value = strVal;
      onValueChange?.(strVal);
    } else {
      value = newVal;
      onValueChange?.(newVal);
    }
  }
</script>

<DatePickerPrimitive.Root value={parsedValue} onValueChange={handleValueChange} {disabled}>
  <div class={cn("relative inline-flex w-full", className)}>
    <DatePickerPrimitive.Input
      class="flex h-9 w-full items-center rounded-xl border border-border-default bg-surface-canvas px-3 text-xs text-fg-primary placeholder:text-fg-muted focus-within:border-accent focus-within:ring-1 focus-within:ring-accent"
    >
      {#snippet children({ segments })}
        <div class="flex flex-1 items-center gap-0.5">
          {#each segments as { part, value: segVal } (part)}
            <DatePickerPrimitive.Segment
              {part}
              class="rounded px-0.5 text-xs text-fg-primary focus:bg-accent focus:text-white focus:outline-hidden"
            >
              {segVal}
            </DatePickerPrimitive.Segment>
          {/each}
        </div>
        <DatePickerPrimitive.Trigger
          class="rounded p-1 text-fg-muted transition-colors hover:text-fg-primary focus-visible:outline-hidden"
        >
          <CalendarIcon class="h-3.5 w-3.5" />
        </DatePickerPrimitive.Trigger>
      {/snippet}
    </DatePickerPrimitive.Input>
  </div>

  <DatePickerPrimitive.Content
    class="z-50 rounded-2xl border border-border-default bg-surface-card p-3 shadow-xl duration-150 animate-in fade-in zoom-in-95"
    sideOffset={6}
  >
    <DatePickerPrimitive.Calendar>
      {#snippet children({ months, weekdays })}
        <DatePickerPrimitive.Header class="flex items-center justify-between pb-3">
          <DatePickerPrimitive.PrevButton
            class="inline-flex h-7 w-7 items-center justify-center rounded-lg text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
          >
            <ChevronLeft class="h-4 w-4" />
          </DatePickerPrimitive.PrevButton>
          <DatePickerPrimitive.Heading class="text-xs font-semibold text-fg-primary" />
          <DatePickerPrimitive.NextButton
            class="inline-flex h-7 w-7 items-center justify-center rounded-lg text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
          >
            <ChevronRight class="h-4 w-4" />
          </DatePickerPrimitive.NextButton>
        </DatePickerPrimitive.Header>

        {#each months as month}
          <DatePickerPrimitive.Grid class="w-full border-collapse select-none space-y-1">
            <DatePickerPrimitive.GridHead>
              <DatePickerPrimitive.GridRow class="flex w-full justify-between">
                {#each weekdays as day}
                  <DatePickerPrimitive.HeadCell class="w-8 text-center text-nano text-fg-muted">
                    {day.slice(0, 2)}
                  </DatePickerPrimitive.HeadCell>
                {/each}
              </DatePickerPrimitive.GridRow>
            </DatePickerPrimitive.GridHead>

            <DatePickerPrimitive.GridBody>
              {#each month.weeks as weekDates}
                <DatePickerPrimitive.GridRow class="flex w-full justify-between">
                  {#each weekDates as date}
                    <DatePickerPrimitive.Cell {date} month={month.value}>
                      <DatePickerPrimitive.Day
                        class="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-medium text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary data-[selected]:bg-accent data-[selected]:font-semibold data-[selected]:text-white data-[today]:border data-[today]:border-accent/60"
                      >
                        {date.day}
                      </DatePickerPrimitive.Day>
                    </DatePickerPrimitive.Cell>
                  {/each}
                </DatePickerPrimitive.GridRow>
              {/each}
            </DatePickerPrimitive.GridBody>
          </DatePickerPrimitive.Grid>
        {/each}
      {/snippet}
    </DatePickerPrimitive.Calendar>
  </DatePickerPrimitive.Content>
</DatePickerPrimitive.Root>
