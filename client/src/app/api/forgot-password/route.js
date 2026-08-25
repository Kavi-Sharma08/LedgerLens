import { NextResponse } from "next/server";
import crypto from "crypto";
import { ObjectId } from "mongodb";
import { getAuthDatabase } from "@/lib/mongo";

/**
 * Password reset request. Always returns a generic success message to avoid
 * revealing whether an email exists in the system.
 *
 * Flow:
 * 1. Find user by email
 * 2. Generate a secure reset token (stored hashed)
 * 3. Send email with reset link
 * 4. Always return "check your inbox"
 */
const TOKEN_COLLECTION = "password_reset_tokens";
const USERS = "users";
const TOKEN_EXPIRY_MS = 30 * 60 * 1000; // 30 minutes

export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    // Always return the same response
    return NextResponse.json({ status: "ok" });
  }

  const { email } = body;
  if (!email || typeof email !== "string") {
    return NextResponse.json({ status: "ok" });
  }

  const normalizedEmail = email.trim().toLowerCase();

  try {
    const db = await getAuthDatabase();
    const user = await db[USERS].findOne({ email: normalizedEmail });

    if (user) {
      // Generate a random token
      const rawToken = crypto.randomBytes(32).toString("hex");
      const tokenHash = crypto.createHash("sha256").update(rawToken).digest("hex");
      const now = new Date();

      // Invalidate any existing tokens for this user
      await db[TOKEN_COLLECTION].deleteMany({ userId: user._id });

      // Store the hashed token
      await db[TOKEN_COLLECTION].insertOne({
        userId: user._id,
        tokenHash,
        expiresAt: new Date(now.getTime() + TOKEN_EXPIRY_MS),
        usedAt: null,
        createdAt: now,
      });

      // TODO: Send email with reset link containing rawToken
      // For now, log it for development
      if (process.env.NODE_ENV !== "production") {
        console.log(`[forgot-password] Reset token for ${normalizedEmail}: ${rawToken}`);
        console.log(`[forgot-password] Reset URL: ${process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"}/reset-password/${rawToken}`);
      }
    }
  } catch (error) {
    console.error("[forgot-password] error:", error);
    // Still return ok — never reveal errors about email existence
  }

  return NextResponse.json({ status: "ok" });
}
