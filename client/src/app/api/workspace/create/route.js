import { NextResponse } from "next/server";

import { apiConfig } from "@/config/site";
import { auth } from "@/lib/auth";

/**
 * Create a new workspace via the FastAPI backend.
 * Used by the onboarding page after signup or when a user has no workspaces.
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

  const name = typeof body?.name === "string" ? body.name.trim() : "";
  if (!name) {
    return NextResponse.json({ detail: "Workspace name is required." }, { status: 400 });
  }

  const secret = process.env.INTERNAL_API_SECRET;
  if (!secret) {
    return NextResponse.json({ detail: "Server configuration error." }, { status: 500 });
  }

  const headers = new Headers();
  headers.set("Accept", "application/json");
  headers.set("Content-Type", "application/json");
  headers.set("X-LL-User-Id", String(session.user.id));
  headers.set("X-LL-User-Email", encodeURIComponent(String(session.user.email ?? "")));
  headers.set("X-LL-Internal-Secret", secret);

  let upstream;
  try {
    upstream = await fetch(`${apiConfig.baseUrl}/api/workspaces`, {
      method: "POST",
      headers,
      body: JSON.stringify({ name }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { detail: "LedgerLens services are temporarily unavailable." },
      { status: 502 }
    );
  }

  const data = await upstream.json().catch(() => null);

  // If creation succeeded, also set the active workspace cookie
  if (upstream.ok && data?.id) {
    const response = NextResponse.json(data, { status: upstream.status });
    response.cookies.set("ll-active-workspace", data.id, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
      httpOnly: false,
    });
    return response;
  }

  return NextResponse.json(data, { status: upstream.status });
}
