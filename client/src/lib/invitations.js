import crypto from "crypto";

import { getAuthDatabase } from "@/lib/mongo";

const INVITATIONS = "invitations";
const USERS = "users";
const WORKSPACES = "workspaces";

export function hashInvitationToken(token) {
  return crypto.createHash("sha256").update(token).digest("hex");
}

export async function findPendingInvitation(db, token) {
  return db.collection(INVITATIONS).findOne({
    tokenHash: hashInvitationToken(token),
    status: "PENDING",
  });
}

async function _workspaceName(db, invitation) {
  const ws = await db
    .collection(WORKSPACES)
    .findOne({ _id: invitation.workspaceId }, { projection: { name: 1 } });
  return ws?.name ?? null;
}

async function invitedByName(db, invitation) {
  if (!invitation.invitedBy) return null;
  const inviter = await db
    .collection(USERS)
    .findOne({ _id: invitation.invitedBy }, { projection: { name: 1, email: 1 } });
  return inviter?.name || inviter?.email || null;
}

export async function getInvitationContext(db, invitation) {
  const [wsName, invitedBy] = await Promise.all([
    _workspaceName(db, invitation),
    invitedByName(db, invitation),
  ]);
  return {
    workspaceId: invitation.workspaceId.toString(),
    workspaceName: wsName,
    invitedBy,
    invitedEmail: invitation.email.toLowerCase().trim(),
    role: invitation.role,
    status: invitation.status,
    expiresAt: invitation.expiresAt
      ? new Date(invitation.expiresAt).toISOString()
      : null,
  };
}

export async function invitationContextByToken(token) {
  const db = await getAuthDatabase();
  const invitation = await findPendingInvitation(db, token);
  if (!invitation) return null;
  return { db, invitation, context: await getInvitationContext(db, invitation) };
}