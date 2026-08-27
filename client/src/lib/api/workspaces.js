import { api } from "./client";

/**
 * Workspace API — workspace switching, members, settings.
 *
 * All calls go through the Next.js authenticated proxy so the session
 * cookie is validated before any request reaches FastAPI.
 */

export async function listWorkspaces({ signal } = {}) {
  return api.get("/api/workspaces", { signal });
}

export async function getCurrentWorkspace({ signal } = {}) {
  return api.get("/api/workspaces/current", { signal });
}

export async function createWorkspace({ name, type }, { signal } = {}) {
  return api.post("/api/workspaces", { name, type }, { signal });
}

export async function updateWorkspace(workspaceId, { name }, { signal } = {}) {
  return api.patch(`/api/workspaces/${workspaceId}`, { name }, { signal });
}

export async function listMembers(workspaceId, { signal } = {}) {
  return api.get(`/api/workspaces/${workspaceId}/members`, { signal });
}

export async function updateMemberRole(workspaceId, userId, role, { signal } = {}) {
  return api.patch(`/api/workspaces/${workspaceId}/members/${userId}`, { role }, { signal });
}

export async function removeMember(workspaceId, userId, { signal } = {}) {
  return api.delete(`/api/workspaces/${workspaceId}/members/${userId}`, { signal });
}

export async function readWorkspacePermissions(workspaceId, { signal } = {}) {
  return api.get(`/api/workspaces/${workspaceId}/permissions`, { signal });
}

export async function updateWorkspacePermissions(
  workspaceId,
  { role, permissions },
  { signal } = {}
) {
  return api.patch(
    `/api/workspaces/${workspaceId}/permissions`,
    { role, permissions },
    { signal }
  );
}
