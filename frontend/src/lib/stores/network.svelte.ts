/**
 * Tracks whether the browser reports itself online, so the app can show a
 * clear "you're offline" banner instead of letting every in-flight request
 * fail one at a time with its own generic network-error message.
 *
 * `navigator.onLine` is a coarse signal (true doesn't guarantee real
 * connectivity, e.g. behind a captive portal) but the transition events are
 * reliable enough to drive a banner: going offline is always reported, and
 * coming back online fires as soon as the OS sees a route again.
 */

function createNetworkStatus() {
  let online = $state(typeof navigator === "undefined" || navigator.onLine);

  if (typeof window !== "undefined") {
    window.addEventListener("online", () => (online = true));
    window.addEventListener("offline", () => (online = false));
  }

  return {
    get online() {
      return online;
    },
  };
}

export const networkStatus = createNetworkStatus();
