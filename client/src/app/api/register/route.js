import { NextResponse } from "next/server";

import {
  RegistrationError,
  registerAccount,
} from "@/lib/registration";

/**
 * Account registration (email + password).
 *
 * Creates the user (and their first workspace unless they were invited) in
 * MongoDB, then the client signs in through Auth.js's Credentials provider —
 * this route never creates sessions itself. Invited users redirect to the
 * accept-invitation flow after signing in, where the membership is created.
 */

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function invalid(detail, code = "invalid_request") {
  return NextResponse.json({ detail, code }, { status: 400 });
}

export async function POST(request) {
  let payload;
  try {
    payload = await request.json();
  } catch {
    return invalid("The registration request could not be read.");
  }

  const name = typeof payload?.name === "string" ? payload.name.trim() : "";
  const workspaceName =
    typeof payload?.workspaceName === "string" ? payload.workspaceName.trim() : "";
  const invitationToken =
    typeof payload?.invitationToken === "string" ? payload.invitationToken.trim() : "";
  const email = typeof payload?.email === "string" ? payload.email.trim() : "";
  const password = typeof payload?.password === "string" ? payload.password : "";

  if (!name) return invalid("Enter your full name.");
  if (!invitationToken && !workspaceName)
    return invalid("Give your workspace a name.");
  if (!EMAIL_PATTERN.test(email)) return invalid("Enter a valid email address.");
  if (
    password.length < 8 ||
    !/[a-zA-Z]/.test(password) ||
    !/\d/.test(password)
  ) {
    return invalid(
      "Passwords need at least 8 characters including one letter and one number."
    );
  }

  if (name.length > 100 || workspaceName.length > 80 || email.length > 254) {
    return invalid("One of the fields is too long.");
  }

  try {
    const account = await registerAccount({
      name,
      email,
      password,
      workspaceName,
      invitationToken: invitationToken || undefined,
    });
    return NextResponse.json(account, { status: 201 });
  } catch (error) {
    if (error instanceof RegistrationError && error.code === "email_already_registered") {
      return NextResponse.json(
        {
          detail: "An account with this email already exists.",
          code: error.code,
        },
        { status: 409 }
      );
    }
    if (error instanceof RegistrationError && error.code === "invalid_invitation") {
      return NextResponse.json({ detail: error.message, code: error.code }, { status: 400 });
    }
    console.error("[register] failed:", error);
    return NextResponse.json(
      { detail: "We couldn't create your account right now. Please try again." },
      { status: 500 }
    );
  }
}
