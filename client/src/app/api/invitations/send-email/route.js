import { NextResponse } from "next/server";
import { sendInvitationEmail } from "@/lib/mailer";

/**
 * Send an invitation email. Called by the client after the backend
 * creates the invitation and returns the raw token + metadata.
 */
export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request." }, { status: 400 });
  }

  const { to, workspaceName, invitedByName, acceptUrl } = body;

  if (!to || !workspaceName || !invitedByName || !acceptUrl) {
    return NextResponse.json({ detail: "Missing required fields." }, { status: 400 });
  }

  try {
    await sendInvitationEmail({ to, workspaceName, invitedByName, acceptUrl });
    return NextResponse.json({ status: "ok" });
  } catch (error) {
    console.error("[send-invitation-email] error:", error);
    return NextResponse.json(
      { detail: "Failed to send invitation email." },
      { status: 500 }
    );
  }
}
