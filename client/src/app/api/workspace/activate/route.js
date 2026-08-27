import { NextResponse } from "next/server";

import { auth } from "@/lib/auth";
import { getAuthDatabase } from "@/lib/mongo";
import { ObjectId } from "mongodb";

/**
 * Set the active workspace cookie for the authenticated user.
 *
 * Called by client components after workspace creation or switching.
 * The cookie is HttpOnly=false so the browser can read it, but the backend
 * still verifies membership on every request — the cookie is NOT authorization.
 *
 * Security: This route verifies the user actually has an ACTIVE membership
 * in the requested workspace before setting the cookie. A forged workspaceId
 * is rejected.
 *
 * If no workspaceId is provided, we auto-select the user's first valid workspace.
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
    body = {};
  }

  let workspaceId = body?.workspaceId;

  try {
    const db = await getAuthDatabase();

    // If no workspaceId provided, auto-select the first valid workspace
    if (!workspaceId || typeof workspaceId !== "string") {
      const membership = await db.collection("workspace_members").findOne({
        userId: new ObjectId(session.user.id),
        status: "ACTIVE",
      });

      if (!membership) {
        return NextResponse.json(
          { detail: "You don't belong to any workspace yet." },
          { status: 404 }
        );
      }

      workspaceId = membership.workspaceId.toString();
    } else {
      // Validate MongoDB ObjectId format
      if (!/^[a-fA-F0-9]{24}$/.test(workspaceId)) {
        return NextResponse.json({ detail: "Invalid workspace ID format." }, { status: 400 });
      }

      // Verify the user actually has an ACTIVE membership in this workspace.
      const membership = await db.collection("workspace_members").findOne({
        workspaceId: new ObjectId(workspaceId),
        userId: new ObjectId(session.user.id),
        status: "ACTIVE",
      });

      if (!membership) {
        return NextResponse.json(
          { detail: "You don't have access to that workspace." },
          { status: 403 }
        );
      }
    }
  } catch (error) {
    console.error("[workspace-activate] membership check failed:", error);
    return NextResponse.json(
      { detail: "We couldn't verify workspace access. Please try again." },
      { status: 500 }
    );
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
