import { writable, derived, get } from 'svelte/store';

export type ThemeMode = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'bimguard_theme';

function getSystemPreference(): ResolvedTheme {
  if (typeof window === 'undefined') return 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function getStoredTheme(): ThemeMode {
  if (typeof window === 'undefined') return 'dark';
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark' || stored === 'system') {
      return stored;
    }
  } catch {
    // LocalStorage might be restricted
  }
  return 'dark';
}

export const themeMode = writable<ThemeMode>(getStoredTheme());
export const systemDark = writable<boolean>(
  typeof window !== 'undefined'
    ? window.matchMedia('(prefers-color-scheme: dark)').matches
    : true
);

export const resolvedTheme = derived(
  [themeMode, systemDark],
  ([$mode, $isSysDark]): ResolvedTheme => {
    if ($mode === 'system') {
      return $isSysDark ? 'dark' : 'light';
    }
    return $mode;
  }
);

export function applyThemeToDom(resolved: ResolvedTheme) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  const body = document.body;
  if (resolved === 'dark') {
    root.classList.add('dark');
    root.classList.remove('light');
    if (body) {
      body.classList.add('dark');
      body.classList.remove('light');
    }
    root.setAttribute('data-theme', 'dark');
    root.style.colorScheme = 'dark';
  } else {
    root.classList.remove('dark');
    root.classList.add('light');
    if (body) {
      body.classList.remove('dark');
      body.classList.add('light');
    }
    root.setAttribute('data-theme', 'light');
    root.style.colorScheme = 'light';
  }
}

export function setTheme(mode: ThemeMode) {
  themeMode.set(mode);
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // Ignore storage errors
  }
  const resolved = mode === 'system' ? getSystemPreference() : mode;
  applyThemeToDom(resolved);
}

export function toggleTheme() {
  const current = get(resolvedTheme);
  const next: ThemeMode = current === 'dark' ? 'light' : 'dark';
  setTheme(next);
}

let isInitialized = false;

export function initTheme() {
  if (typeof window === 'undefined' || isInitialized) return;
  isInitialized = true;

  const currentMode = getStoredTheme();
  themeMode.set(currentMode);

  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  const handleMediaChange = (e: MediaQueryListEvent) => {
    systemDark.set(e.matches);
    if (get(themeMode) === 'system') {
      applyThemeToDom(e.matches ? 'dark' : 'light');
    }
  };

  if (mediaQuery.addEventListener) {
    mediaQuery.addEventListener('change', handleMediaChange);
  } else {
    mediaQuery.addListener(handleMediaChange);
  }

  // Initial DOM application
  const resolved = currentMode === 'system' ? getSystemPreference() : currentMode;
  applyThemeToDom(resolved);
}
