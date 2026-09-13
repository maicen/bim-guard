<script lang="ts" module>
  import { DateRangePicker as DateRangePickerPrimitive } from "bits-ui";

  export const DateRangePickerRoot = DateRangePickerPrimitive.Root;
  export const DateRangePickerTrigger = DateRangePickerPrimitive.Trigger;
  export const DateRangePickerContent = DateRangePickerPrimitive.Content;
  export const DateRangePickerCalendar = DateRangePickerPrimitive.Calendar;
  export const DateRangePickerInput = DateRangePickerPrimitive.Input;
</script>

<script lang="ts">
  import { Calendar as CalendarIcon, ChevronLeft, ChevronRight } from "lucide-svelte";
  import type { DateRange } from "bits-ui";
  import { cn } from "../../utils/cn";

  interface Props {
    value?: DateRange;
    onValueChange?: (val: DateRange | undefined) => void;
    placeholder?: string;
    disabled?: boolean;
    class?: string;
  }

  let {
    value = $bindable(),
    onValueChange,
    placeholder = "Select date range",
    disabled = false,
    class: className,
  }: Props = $props();
</script>

<DateRangePickerPrimitive.Root bind:value {onValueChange} {disabled}>
  <div class={cn("relative inline-flex w-full", className)}>
    <div class="flex h-9 w-full items-center rounded-xl border border-border-default bg-surface-canvas px-3 text-xs text-fg-primary placeholder:text-fg-muted focus-within:border-accent focus-within:ring-1 focus-within:ring-accent">
      <DateRangePickerPrimitive.Input type="start" class="flex items-center gap-0.5">
        {#snippet children({ segments })}
          {#each segments as { part, value: segVal } (part)}
            <DateRangePickerPrimitive.Segment
              {part}
              class="rounded px-0.5 text-xs text-fg-primary focus:bg-accent focus:text-white focus:outline-hidden"
            >
              {segVal}
            </DateRangePickerPrimitive.Segment>
          {/each}
        {/snippet}
      </DateRangePickerPrimitive.Input>
      <span class="px-2 text-fg-muted">–</span>
      <DateRangePickerPrimitive.Input type="end" class="flex items-center gap-0.5">
        {#snippet children({ segments })}
          {#each segments as { part, value: segVal } (part)}
            <DateRangePickerPrimitive.Segment
              {part}
              class="rounded px-0.5 text-xs text-fg-primary focus:bg-accent focus:text-white focus:outline-hidden"
            >
              {segVal}
            </DateRangePickerPrimitive.Segment>
          {/each}
        {/snippet}
      </DateRangePickerPrimitive.Input>
      <div class="ml-auto">
        <DateRangePickerPrimitive.Trigger
          class="rounded p-1 text-fg-muted transition-colors hover:text-fg-primary focus-visible:outline-hidden"
        >
          <CalendarIcon class="h-3.5 w-3.5" />
        </DateRangePickerPrimitive.Trigger>
      </div>
    </div>
  </div>

  <DateRangePickerPrimitive.Content
    class="z-50 rounded-2xl border border-border-default bg-surface-card p-3 shadow-xl duration-150 animate-in fade-in zoom-in-95"
    sideOffset={6}
  >
    <DateRangePickerPrimitive.Calendar>
      {#snippet children({ months, weekdays })}
        <DateRangePickerPrimitive.Header class="flex items-center justify-between pb-3">
          <DateRangePickerPrimitive.PrevButton
            class="inline-flex h-7 w-7 items-center justify-center rounded-lg text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
          >
            <ChevronLeft class="h-4 w-4" />
          </DateRangePickerPrimitive.PrevButton>
          <DateRangePickerPrimitive.Heading class="text-xs font-semibold text-fg-primary" />
          <DateRangePickerPrimitive.NextButton
            class="inline-flex h-7 w-7 items-center justify-center rounded-lg text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
          >
            <ChevronRight class="h-4 w-4" />
          </DateRangePickerPrimitive.NextButton>
        </DateRangePickerPrimitive.Header>

        {#each months as month}
          <DateRangePickerPrimitive.Grid class="w-full border-collapse select-none space-y-1">
            <DateRangePickerPrimitive.GridHead>
              <DateRangePickerPrimitive.GridRow class="flex w-full justify-between">
                {#each weekdays as day}
                  <DateRangePickerPrimitive.HeadCell class="w-8 text-center text-nano text-fg-muted">
                    {day.slice(0, 2)}
                  </DateRangePickerPrimitive.HeadCell>
                {/each}
              </DateRangePickerPrimitive.GridRow>
            </DateRangePickerPrimitive.GridHead>

            <DateRangePickerPrimitive.GridBody>
              {#each month.weeks as weekDates}
                <DateRangePickerPrimitive.GridRow class="flex w-full justify-between">
                  {#each weekDates as date}
                    <DateRangePickerPrimitive.Cell {date} month={month.value}>
                      <DateRangePickerPrimitive.Day
                        class="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-medium text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary data-[selected]:bg-accent data-[selected]:font-semibold data-[selected]:text-white data-[highlighted]:bg-surface-selected data-[today]:border data-[today]:border-accent/60"
                      >
                        {date.day}
                      </DateRangePickerPrimitive.Day>
                    </DateRangePickerPrimitive.Cell>
                  {/each}
                </DateRangePickerPrimitive.GridRow>
              {/each}
            </DateRangePickerPrimitive.GridBody>
          </DateRangePickerPrimitive.Grid>
        {/each}
      {/snippet}
    </DateRangePickerPrimitive.Calendar>
  </DateRangePickerPrimitive.Content>
</DateRangePickerPrimitive.Root>
