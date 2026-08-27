import { NextResponse } from "next/server";

import { getAuthDatabase } from "@/lib/mongo";
import {
  findPendingInvitation,
  getInvitationContext,
} from "@/lib/invitations";

const INVITATIONS = "invitations";

/**
 * Public invitation metadata, used by the accept page and the signup form
 * to show workspace context before the invitee registers or signs in.
 *
 * Only returns what was already mailed to the invitee (workspace name +
 * invited email) plus validity — never tokens or membership data.
 */
export async function GET(request) {
  const token = new URL(request.url).searchParams.get("token") ?? "";

  if (!token) {
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
      await db.collection(INVITATIONS).updateOne(
        { _id: invitation._id },
        { $set: { status: "EXPIRED" } }
      );
      return NextResponse.json(
        { detail: "This invitation has expired. Please request a new one." },
        { status: 410 }
      );
    }

    return NextResponse.json(await getInvitationContext(db, invitation));
  } catch (error) {
    console.error("[invitation-lookup] error:", error);
    return NextResponse.json(
      { detail: "Something went wrong. Please try again." },
      { status: 500 }
    );
  }
}