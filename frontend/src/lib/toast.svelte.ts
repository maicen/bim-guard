/**
 * Transient notifications.
 *
 * The app previously had no feedback channel: bulk-action outcomes, uploads,
 * saves and sync results were either silent, logged to the console, or shown
 * through a native alert(). Toasts render into a single aria-live region
 * (see <Toaster>), so screen readers hear them too.
 *
 * Import the singleton and call it from anywhere:
 *
 *     import { toasts } from "../lib/toast.svelte";
 *     toasts.success("Deleted 3 projects");
 *     toasts.fromError(err);
 */

export type ToastVariant = "success" | "error" | "warning" | "info";

export interface Toast {
  id: number;
  variant: ToastVariant;
  message: string;
  /** Optional heading above the message. */
  title?: string;
  /** ms before auto-dismiss; 0 keeps it until dismissed. */
  duration: number;
}

/** Errors stay until dismissed; everything else clears itself. */
const DEFAULT_DURATION: Record<ToastVariant, number> = {
  success: 4000,
  info: 5000,
  warning: 7000,
  error: 0,
};

class ToastStore {
  items = $state<Toast[]>([]);
  #nextId = 0;
  #timers = new Map<number, ReturnType<typeof setTimeout>>();

  push(variant: ToastVariant, message: string, title?: string, duration?: number): number {
    const id = ++this.#nextId;
    const ms = duration ?? DEFAULT_DURATION[variant];
    this.items = [...this.items, { id, variant, message, title, duration: ms }];
    if (ms > 0) {
      this.#timers.set(
        id,
        setTimeout(() => this.dismiss(id), ms),
      );
    }
    return id;
  }

  dismiss(id: number) {
    const timer = this.#timers.get(id);
    if (timer) {
      clearTimeout(timer);
      this.#timers.delete(id);
    }
    this.items = this.items.filter((t) => t.id !== id);
  }

  clear() {
    for (const timer of this.#timers.values()) clearTimeout(timer);
    this.#timers.clear();
    this.items = [];
  }

  success = (message: string, title?: string) => this.push("success", message, title);
  error = (message: string, title?: string) => this.push("error", message, title);
  warning = (message: string, title?: string) => this.push("warning", message, title);
  info = (message: string, title?: string) => this.push("info", message, title);

  /**
   * Report a caught value as an error toast. Centralises the
   * `err instanceof Error ? err.message : String(err)` dance that would
   * otherwise be repeated at every call site.
   */
  fromError = (err: unknown, fallback = "Something went wrong.") =>
    this.error(err instanceof Error ? err.message || fallback : String(err) || fallback);
}

export const toasts = new ToastStore();
