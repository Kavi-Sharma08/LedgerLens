import { NextResponse } from "next/server";
import crypto from "crypto";
import bcrypt from "bcryptjs";
import { getAuthDatabase } from "@/lib/mongo";

/**
 * Password reset completion. Validates the token, hashes the new password,
 * updates the user record, and marks the token as used.
 */
const TOKEN_COLLECTION = "password_reset_tokens";
const USERS = "users";
const BCRYPT_ROUNDS = 12;

export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body." }, { status: 422 });
  }

  const { token, password } = body;
  if (!token || typeof token !== "string") {
    return NextResponse.json({ detail: "Reset token is required." }, { status: 422 });
  }
  if (!password || typeof password !== "string") {
    return NextResponse.json({ detail: "New password is required." }, { status: 422 });
  }
  if (password.length < 8) {
    return NextResponse.json(
      { detail: "Password must be at least 8 characters long." },
      { status: 422 }
    );
  }
  if (!/[a-zA-Z]/.test(password) || !/\d/.test(password)) {
    return NextResponse.json(
      { detail: "Password must include at least one letter and one number." },
      { status: 422 }
    );
  }

  try {
    const db = await getAuthDatabase();
    const tokenHash = crypto.createHash("sha256").update(token).digest("hex");
    const now = new Date();

    // Find a valid, unused, non-expired token
    const resetToken = await db[TOKEN_COLLECTION].findOne({
      tokenHash,
      usedAt: null,
      expiresAt: { $gt: now },
    });

    if (!resetToken) {
      return NextResponse.json(
        { detail: "This reset link has expired or is invalid. Please request a new one." },
        { status: 422 }
      );
    }

    // Hash the new password
    const passwordHash = await bcrypt.hash(password, BCRYPT_ROUNDS);

    // Update the user's password
    await db[USERS].updateOne(
      { _id: resetToken.userId },
      { $set: { passwordHash, updatedAt: now } }
    );

    // Mark the token as used
    await db[TOKEN_COLLECTION].updateOne(
      { _id: resetToken._id },
      { $set: { usedAt: now } }
    );

    // Invalidate any other tokens for this user
    await db[TOKEN_COLLECTION].updateMany(
      { userId: resetToken.userId, _id: { $ne: resetToken._id } },
      { $set: { usedAt: now } }
    );
  } catch (error) {
    console.error("[reset-password] error:", error);
    return NextResponse.json(
      { detail: "We couldn't reset your password. Please try again." },
      { status: 500 }
    );
  }

  return NextResponse.json({ status: "ok" });
}
