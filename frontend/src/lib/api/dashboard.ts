import { InMemoryCache, SWRStore, type SWROptions } from "../cache";
import { getActiveOrgId } from "../authToken";
import { API_BASE, apiFetch, handleResponse } from "./client";
import { projectsApi } from "./projects";
import { rulesApi } from "./rules";
import { documentsApi } from "./documents";

const _dashboardStatsStore = new SWRStore<string, any>(new InMemoryCache(), 15_000);

export const dashboardApi = {
  getCachedStats(orgId?: number | null): any | null {
    const effectiveOrg = orgId !== undefined ? orgId : getActiveOrgId();
    const key = `org:${effectiveOrg ?? "all"}`;
    return _dashboardStatsStore.getCached(key) || null;
  },

  async getStats(options: SWROptions & { organization_id?: number | null } = {}): Promise<any> {
    const effectiveOrg = options.organization_id !== undefined ? options.organization_id : getActiveOrgId();
    const key = `org:${effectiveOrg ?? "all"}`;
    return _dashboardStatsStore.execute(
      key,
      async () => {
        const query = effectiveOrg ? `?organization_id=${effectiveOrg}` : "";
        const res = await apiFetch(`${API_BASE}/dashboard/stats${query}`);
        return handleResponse<any>(res);
      },
      options,
    );
  },

  prefetchAll(): void {
    Promise.allSettled([
      projectsApi.list(),
      rulesApi.list(),
      rulesApi.folders(),
      documentsApi.list(),
      dashboardApi.getStats(),
    ]).catch(() => {});
  },

  invalidateCache() {
    _dashboardStatsStore.clear();
  },
};
