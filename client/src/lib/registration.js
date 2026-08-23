import "server-only";

import bcrypt from "bcryptjs";
import { ObjectId } from "mongodb";

import { getAuthDatabase } from "@/lib/mongo";

/**
 * Account + workspace data access for the authentication layer.
 *
 * Auth.js owns authentication; this module is its persistence arm. FastAPI has
 * no counterpart for these operations — it consumes the resulting records via
 * business APIs only.
 */

const USERS = "users";
const WORKSPACES = "workspaces";

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
  while (await db[WORKSPACES].findOne({ slug: candidate }, { projection: { _id: 1 } })) {
    suffix += 1;
    candidate = `${base}-${suffix}`;
  }
  return candidate;
}

/** Returns the raw user document or null. Never exposes passwordHash. */
export async function findUserByEmail(email) {
  const db = await getAuthDatabase();
  return db[USERS].findOne({ email: email.trim().toLowerCase() });
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
 * Creates the first user and their owned workspace in one flow.
 * The unique index on users.email remains the concurrency source of truth.
 */
export async function registerAccount({ name, email, password, workspaceName }) {
  const db = await getAuthDatabase();
  const normalizedEmail = email.trim().toLowerCase();

  if (await findUserByEmail(normalizedEmail)) {
    throw new RegistrationError("email_already_registered", "Email already registered.");
  }

  const passwordHash = await bcrypt.hash(password, BCRYPT_ROUNDS);
  const now = new Date();

  let result;
  try {
    result = await db[USERS].insertOne({
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

  await db[WORKSPACES].insertOne({
    name: workspaceName.trim(),
    slug: await uniqueSlug(db, workspaceName),
    ownerId: result.insertedId,
    createdAt: now,
    updatedAt: now,
  });

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

  const displayName = user.name || user.email?.split("@")[0] || "Workspace";
  await db[WORKSPACES].insertOne({
    name: `${displayName}'s Workspace`,
    slug: await uniqueSlug(db, displayName),
    ownerId: _id,
    createdAt: new Date(),
    updatedAt: new Date(),
  });
}
