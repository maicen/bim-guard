import { getContext, setContext } from "svelte";

export const SIDEBAR_COOKIE_NAME = "sidebar_state";
export const SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 7;
export const SIDEBAR_WIDTH = "16rem";
export const SIDEBAR_WIDTH_MOBILE = "18rem";
export const SIDEBAR_WIDTH_ICON = "3.5rem";
export const SIDEBAR_KEYBOARD_SHORTCUT = "b";

const SIDEBAR_CONTEXT_KEY = Symbol("sidebar-context");

export class SidebarState {
  open = $state(true);
  openMobile = $state(false);
  isMobile = $state(false);

  constructor(initialOpen: boolean = true) {
    this.open = initialOpen;
  }

  get state(): "expanded" | "collapsed" {
    return this.open ? "expanded" : "collapsed";
  }

  setOpen = (value: boolean | ((val: boolean) => boolean)) => {
    this.open = typeof value === "function" ? value(this.open) : value;
  };

  setOpenMobile = (value: boolean | ((val: boolean) => boolean)) => {
    this.openMobile = typeof value === "function" ? value(this.openMobile) : value;
  };

  toggleSidebar = () => {
    if (this.isMobile) {
      this.openMobile = !this.openMobile;
    } else {
      this.open = !this.open;
    }
  };
}

export function setSidebar(state: SidebarState): SidebarState {
  return setContext(SIDEBAR_CONTEXT_KEY, state);
}

export function useSidebar(): SidebarState {
  const context = getContext<SidebarState>(SIDEBAR_CONTEXT_KEY);
  if (!context) {
    throw new Error("useSidebar must be used within a <SidebarProvider>");
  }
  return context;
}
