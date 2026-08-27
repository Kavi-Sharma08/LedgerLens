import { api } from "./client";

export async function inviteMember(workspaceId, { email, role }, { signal } = {}) {
  const result = await api.post(
    `/api/workspaces/${workspaceId}/invitations`,
    { email, role },
    { signal }
  );

  if (result?.rawToken && result?.email) {
    const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
    const acceptUrl = `${appUrl}/accept-invitation/${result.rawToken}`;

    try {
      await fetch("/api/invitations/send-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          to: result.email,
          workspaceName: result.workspaceName,
          invitedByName: result.invitedBy,
          acceptUrl,
        }),
      });
    } catch {
      // Email failure should not block the invitation flow
    }
  }

  return result;
}

export async function listInvitations(workspaceId, { signal } = {}) {
  return api.get(`/api/workspaces/${workspaceId}/invitations`, { signal });
}

export async function acceptInvitation(token, { signal } = {}) {
  return api.post("/api/invitations/accept", { token }, { signal });
}
