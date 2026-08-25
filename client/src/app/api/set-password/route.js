import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { setPassword } from "@/lib/registration";

/**
 * Set or change a LedgerLens password for the authenticated user.
 * Google-only accounts can create a password; existing password users can change it.
 */
export async function POST(request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json(
      { detail: "Your session has expired or is invalid. Please sign in again." },
      { status: 401 }
    );
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body." }, { status: 422 });
  }

  const { password } = body;
  if (!password || typeof password !== "string") {
    return NextResponse.json({ detail: "Password is required." }, { status: 422 });
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
    await setPassword(session.user.id, password);
  } catch (error) {
    console.error("[set-password] failed:", error);
    return NextResponse.json(
      { detail: "We couldn't update your password. Please try again." },
      { status: 500 }
    );
  }

  return NextResponse.json({ status: "ok" });
}
