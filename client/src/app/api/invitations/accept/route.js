import { NextResponse } from "next/server";
import { ObjectId } from "mongodb";

import { auth } from "@/lib/auth";
import { getAuthDatabase } from "@/lib/mongo";
import {
  findPendingInvitation,
  getInvitationContext,
} from "@/lib/invitations";

const USERS = "users";
const WORKSPACE_MEMBERS = "workspace_members";

/**
 * Accept an invitation by raw token.
 *
 * Flow for the accept-invitation page:
 *   - No session + no account  -> status "requires_signup" (with context)
 *   - No session + account     -> status "requires_login" (with context)
 *   - Session, wrong email     -> status "wrong_account"
 *   - Session, matching email  -> membership created, invitation ACCEPTED,
 *                                 active-workspace cookie set, status "ok"
 *
 * The invitation is only marked ACCEPTED once the acceptance actually
 * completes — never before signup, otherwise the pending signup flow would
 * 404 on its own invitation.
 */
export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request." }, { status: 400 });
  }

  const { token } = body;
  if (!token || typeof token !== "string") {
    return NextResponse.json({ detail: "Invalid invitation token." }, { status: 400 });
  }

  try {
    const db = await getAuthDatabase();
    const invitation = await findPendingInvitation(db, token);

    if (!invitation) {
      return NextResponse.json(
        { detail: "This invitation is no longer valid or has already been accepted." },
        { status: 404 }
      );
    }

    if (invitation.expiresAt && new Date(invitation.expiresAt).getTime() < Date.now()) {
      await db.collection("invitations").updateOne(
        { _id: invitation._id },
        { $set: { status: "EXPIRED" } }
      );
      return NextResponse.json(
        { detail: "This invitation has expired. Please request a new one." },
        { status: 410 }
      );
    }

    const context = await getInvitationContext(db, invitation);
    const email = invitation.email.toLowerCase().trim();

    const existingUser = await db.collection(USERS).findOne({ email });

    const session = await auth();
    if (!session?.user?.id) {
      // Not signed in yet — tell the page whether to create an account or sign in.
      if (existingUser) {
        return NextResponse.json({ ...context, status: "requires_login" });
      }
      return NextResponse.json({ ...context, status: "requires_signup" });
    }

    // Signed in: the session identity must own the invited email.
    const sessionEmail = String(session.user.email ?? "").toLowerCase().trim();
    if (sessionEmail && sessionEmail !== email) {
      return NextResponse.json({
        ...context,
        status: "wrong_account",
        sessionEmail,
      });
    }

    const user = existingUser ?? (await db.collection(USERS).findOne({ _id: new ObjectId(session.user.id) }));
    if (!user) {
      return NextResponse.json(
        { detail: "We couldn't find your account. Please try again." },
        { status: 500 }
      );
    }

    const now = new Date();
    const existingMember = await db.collection(WORKSPACE_MEMBERS).findOne({
      workspaceId: invitation.workspaceId,
      userId: user._id,
    });

    if (!existingMember) {
      await db.collection(WORKSPACE_MEMBERS).insertOne({
        workspaceId: invitation.workspaceId,
        userId: user._id,
        role: invitation.role,
        status: "ACTIVE",
        joinedAt: now,
        createdAt: now,
        updatedAt: now,
      });
    } else if (existingMember.status !== "ACTIVE") {
      await db.collection(WORKSPACE_MEMBERS).updateOne(
        { _id: existingMember._id },
        { $set: { status: "ACTIVE", role: invitation.role, updatedAt: now } }
      );
    }

    await db.collection("invitations").updateOne(
      { _id: invitation._id },
      { $set: { status: "ACCEPTED", acceptedAt: now } }
    );

    const response = NextResponse.json({
      status: "ok",
      workspaceId: context.workspaceId,
      workspaceName: context.workspaceName,
      alreadyMember: Boolean(existingMember && existingMember.status === "ACTIVE"),
    });
    response.cookies.set("ll-active-workspace", context.workspaceId, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
      httpOnly: false,
    });
    return response;
  } catch (error) {
    console.error("[accept-invitation] error:", error);
    return NextResponse.json(
      { detail: "Something went wrong. Please try again." },
      { status: 500 }
    );
  }
}