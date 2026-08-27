import "server-only";

import bcrypt from "bcryptjs";
import { ObjectId } from "mongodb";

import { getAuthDatabase } from "@/lib/mongo";
import { findPendingInvitation } from "@/lib/invitations";

/**
 * Account + workspace data access for the authentication layer.
 *
 * Auth.js owns authentication; this module is its persistence arm. FastAPI has
 * no counterpart for these operations — it consumes the resulting records via
 * business APIs only.
 */

const USERS = "users";
const WORKSPACES = "workspaces";
const WORKSPACE_MEMBERS = "workspace_members";

const BCRYPT_ROUNDS = 12;
const SLUG_CLEANUP = /[^a-z0-9]+/g;

export class RegistrationError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "RegistrationError";
    this.code = code;
  }
}

function slugify(name) {
  const slug = name
    .trim()
    .toLowerCase()
    .replace(SLUG_CLEANUP, "-")
    .replace(/^-+|-+$/g, "");
  return slug.slice(0, 48) || "workspace";
}

async function uniqueSlug(db, desired) {
  const base = slugify(desired);
  let candidate = base;
  let suffix = 1;
  while (await db.collection(WORKSPACES).findOne({ slug: candidate }, { projection: { _id: 1 } })) {
    suffix += 1;
    candidate = `${base}-${suffix}`;
  }
  return candidate;
}

/** Returns the raw user document or null. Never exposes passwordHash. */
export async function findUserByEmail(email) {
  const db = await getAuthDatabase();
  return db.collection(USERS).findOne({ email: email.trim().toLowerCase() });
}

/**
 * Validates an email/password pair against stored credentials.
 * Returns a minimal adapter-shaped user (id, name, email, image) or null.
 */
export async function verifyUserCredentials(email, password) {
  const user = await findUserByEmail(email);
  if (!user || !user.passwordHash) return null;

  const matches = await bcrypt.compare(password, user.passwordHash);
  if (!matches) return null;

  return {
    id: user._id.toString(),
    name: user.name ?? "",
    email: user.email,
    image: user.image ?? user.avatar ?? null,
  };
}

/**
 * Creates the user and, for signups without an invitation, their owned
 * workspace. When an invitationToken is present the user is created WITHOUT
 * a workspace — the invitation's accept flow adds them to the invited
 * workspace right after they sign in. The unique index on users.email
 * remains the concurrency source of truth.
 */
export async function registerAccount({ name, email, password, workspaceName, invitationToken }) {
  const db = await getAuthDatabase();
  const normalizedEmail = email.trim().toLowerCase();

  if (await findUserByEmail(normalizedEmail)) {
    throw new RegistrationError("email_already_registered", "Email already registered.");
  }

  if (invitationToken) {
    const now = new Date();
    const invitation = await findPendingInvitation(db, invitationToken);
    if (!invitation) {
      throw new RegistrationError("invalid_invitation", "This invitation is no longer valid.");
    }
    if (
      invitation.email.toLowerCase().trim() !== normalizedEmail ||
      (invitation.expiresAt && new Date(invitation.expiresAt).getTime() < now.getTime())
    ) {
      throw new RegistrationError("invalid_invitation", "This invitation isn't valid for that email.");
    }
  }

  const passwordHash = await bcrypt.hash(password, BCRYPT_ROUNDS);
  const now = new Date();

  let result;
  try {
    result = await db.collection(USERS).insertOne({
      name: name.trim(),
      email: normalizedEmail,
      emailVerified: null,
      image: null,
      avatar: null,
      passwordHash,
      createdAt: now,
      updatedAt: now,
    });
  } catch (error) {
    // Duplicate key from concurrent registration with the same email.
    if (error?.code === 11000) {
      throw new RegistrationError("email_already_registered", "Email already registered.");
    }
    throw error;
  }

  if (!invitationToken) {
    const workspaceId = new ObjectId();
    await db.collection(WORKSPACES).insertOne({
      _id: workspaceId,
      name: workspaceName.trim(),
      slug: await uniqueSlug(db, workspaceName),
      ownerId: result.insertedId,
      createdAt: now,
      updatedAt: now,
    });

    // Create OWNER membership record
    await db.collection(WORKSPACE_MEMBERS).insertOne({
      workspaceId: workspaceId,
      userId: result.insertedId,
      role: "OWNER",
      status: "ACTIVE",
      joinedAt: now,
      createdAt: now,
      updatedAt: now,
    });
  }

  return { userId: result.insertedId.toString(), email: normalizedEmail };
}

/**
 * Gives a first-time Google user their default workspace.
 * Wired to Auth.js's createUser event; runs after the adapter inserted the user.
 */
export async function ensureDefaultWorkspace(user) {
  if (!user?.id) return;

  const db = await getAuthDatabase();
  let _id;
  try {
    _id = typeof user.id === "string" ? ObjectId.createFromHexString(user.id) : user.id;
  } catch {
    return;
  }

  // Check if user already has any workspace membership
  const existingMembership = await db.collection(WORKSPACE_MEMBERS).findOne({ userId: _id });
  if (existingMembership) return;

  const workspaceId = new ObjectId();
  const displayName = user.name || user.email?.split("@")[0] || "Workspace";
  const now = new Date();

  await db.collection(WORKSPACES).insertOne({
    _id: workspaceId,
    name: `${displayName}'s Workspace`,
    slug: await uniqueSlug(db, displayName),
    ownerId: _id,
    createdAt: now,
    updatedAt: now,
  });

  // Create OWNER membership record
  await db.collection(WORKSPACE_MEMBERS).insertOne({
    workspaceId: workspaceId,
    userId: _id,
    role: "OWNER",
    status: "ACTIVE",
    joinedAt: now,
    createdAt: now,
    updatedAt: now,
  });
}

/**
 * Set or update a LedgerLens password for the user.
 * Google-only accounts can create a password; existing password users can change it.
 */
export async function setPassword(userId, newPassword) {
  const db = await getAuthDatabase();
  const passwordHash = await bcrypt.hash(newPassword, BCRYPT_ROUNDS);
  const _id = typeof userId === "string" ? ObjectId.createFromHexString(userId) : userId;

  await db.collection(USERS).updateOne(
    { _id },
    { $set: { passwordHash, updatedAt: new Date() } }
  );
}
