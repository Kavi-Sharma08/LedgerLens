import { NextResponse } from "next/server";

import { auth } from "@/lib/auth";

/**
 * Set the active workspace cookie for the authenticated user.
 *
 * Called by client components after workspace creation or switching.
 * The cookie is HttpOnly=false so the browser can read it, but the backend
 * still verifies membership on every request — the cookie is NOT authorization.
 */
export async function POST(request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json(
      { detail: "Your session has expired. Please sign in again." },
      { status: 401 }
    );
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body." }, { status: 400 });
  }

  const workspaceId = body?.workspaceId;
  if (!workspaceId || typeof workspaceId !== "string") {
    return NextResponse.json({ detail: "workspaceId is required." }, { status: 400 });
  }

  // Validate MongoDB ObjectId format
  if (!/^[a-fA-F0-9]{24}$/.test(workspaceId)) {
    return NextResponse.json({ detail: "Invalid workspace ID format." }, { status: 400 });
  }

  const response = NextResponse.json({ ok: true, workspaceId });
  response.cookies.set("ll-active-workspace", workspaceId, {
    path: "/",
    maxAge: 60 * 60 * 24 * 365, // 1 year
    sameSite: "lax",
    httpOnly: false,
  });

  return response;
}
