import type { CurrentUserResponse, ProfileUpdatePayload, UserProfile } from "../types";
import { API_BASE, apiFetch, handleResponse } from "./client";

export const authApi = {
  /** Fetch the signed-in caller's identity. Requires a Supabase access token. */
  async me(accessToken: string): Promise<CurrentUserResponse> {
    const res = await apiFetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return handleResponse<CurrentUserResponse>(res);
  },

  async updateProfile(accessToken: string, payload: ProfileUpdatePayload): Promise<UserProfile> {
    const res = await apiFetch(`${API_BASE}/auth/profile`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify(payload),
    });
    return handleResponse<UserProfile>(res);
  },
};
