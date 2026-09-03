/**
 * Shared modal-dialog behaviour: focus containment, focus restoration, body
 * scroll locking, and a stack so Escape only dismisses the topmost dialog.
 *
 * Used by `<Modal>` and `<ConfirmModal>` (and any future drawer/popover that
 * needs the same semantics) via the `dialog` attachment:
 *
 *     <div {@attach dialog(onClose)} role="dialog" aria-modal="true"> … </div>
 */

/** Selector for things a keyboard user can land on. */
const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

/**
 * Open dialogs, deepest last. Escape and the scroll lock consult this so
 * stacked dialogs behave: the top one closes, and the lock lifts only when the
 * last dialog goes away.
 */
const stack: HTMLElement[] = [];

let savedOverflow: string | null = null;
let savedPaddingRight: string | null = null;

function lockScroll() {
  if (stack.length !== 1) return; // already locked by an outer dialog
  const { body } = document;
  savedOverflow = body.style.overflow;
  savedPaddingRight = body.style.paddingRight;
  // Compensate for the scrollbar so the page doesn't jump sideways.
  const gap = window.innerWidth - document.documentElement.clientWidth;
  if (gap > 0) {
    const current = parseFloat(getComputedStyle(body).paddingRight) || 0;
    body.style.paddingRight = `${current + gap}px`;
  }
  body.style.overflow = "hidden";
}

function unlockScroll() {
  if (stack.length !== 0) return; // an outer dialog is still open
  const { body } = document;
  body.style.overflow = savedOverflow ?? "";
  body.style.paddingRight = savedPaddingRight ?? "";
  savedOverflow = savedPaddingRight = null;
}

function focusableWithin(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => el.offsetParent !== null || el === document.activeElement,
  );
}

export interface DialogOptions {
  /** Skip moving focus into the dialog on open. */
  autoFocus?: boolean;
  /** Skip Escape-to-close (the caller handles dismissal itself). */
  closeOnEscape?: boolean;
}

/**
 * Attachment that makes its element behave as a modal dialog.
 *
 * Runs when the element mounts and tears down when it unmounts, so opening and
 * closing is driven by `{#if isOpen}` in the component rather than by an effect.
 */
export function dialog(onClose: () => void, options: DialogOptions = {}) {
  const { autoFocus = true, closeOnEscape = true } = options;

  return (node: HTMLElement) => {
    const previouslyFocused = document.activeElement as HTMLElement | null;

    stack.push(node);
    lockScroll();

    if (autoFocus) {
      // Prefer the first real control; fall back to the dialog itself so focus
      // never stays behind on the trigger.
      const first = focusableWithin(node)[0];
      if (first) {
        first.focus();
      } else {
        node.tabIndex = -1;
        node.focus();
      }
    }

    function handleKeydown(event: KeyboardEvent) {
      // Only the topmost dialog reacts.
      if (stack[stack.length - 1] !== node) return;

      if (event.key === "Escape" && closeOnEscape) {
        event.stopPropagation();
        onClose();
        return;
      }

      if (event.key !== "Tab") return;

      const items = focusableWithin(node);
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;

      // Wrap at both ends, and pull focus back in if it has escaped the dialog.
      if (event.shiftKey && (active === first || !node.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !node.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeydown, true);

    return () => {
      document.removeEventListener("keydown", handleKeydown, true);
      const index = stack.indexOf(node);
      if (index !== -1) stack.splice(index, 1);
      unlockScroll();
      // Return focus to whatever opened the dialog, if it is still around.
      if (previouslyFocused && document.contains(previouslyFocused)) {
        previouslyFocused.focus();
      }
    };
  };
}

let idCounter = 0;
/** Unique id for wiring aria-labelledby/aria-describedby per dialog instance. */
export function dialogId(prefix = "dialog"): string {
  idCounter += 1;
  return `${prefix}-${idCounter}`;
}
