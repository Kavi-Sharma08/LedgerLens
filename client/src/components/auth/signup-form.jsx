"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/auth/password-input";
import { GoogleButton } from "@/components/auth/google-button";
import { FormDivider } from "@/components/auth/form-divider";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate(values, { isInvitation }) {
  const errors = {};
  if (!values.name.trim()) errors.name = "Enter your full name.";
  if (!isInvitation && !values.workspaceName.trim())
    errors.workspaceName = "Give your workspace a name — usually your company.";
  if (!values.email.trim()) errors.email = "Enter your work email address.";
  else if (!EMAIL_PATTERN.test(values.email.trim()))
    errors.email = "That email address doesn't look right. Check it and try again.";

  if (!values.password) errors.password = "Choose a password.";
  else if (values.password.length < 8)
    errors.password = "Passwords need to be at least 8 characters long.";
  else if (!/[a-zA-Z]/.test(values.password) || !/\d/.test(values.password))
    errors.password = "Include at least one letter and one number in your password.";

  if (!values.confirmPassword) errors.confirmPassword = "Re-enter your password.";
  else if (values.confirmPassword !== values.password)
    errors.confirmPassword = "Passwords don't match. Re-enter them and try again.";

  return errors;
}

function FieldError({ id, message }) {
  if (!message) return null;
  return (
    <p id={id} role="alert" className="text-xs text-destructive">
      {message}
    </p>
  );
}

async function registerAccount(payload) {
  let response;
  try {
    response = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(
      "We couldn't reach LedgerLens. Check your internet connection and try again."
    );
  }

  const data = await response.json().catch(() => null);

  if (response.status === 409 || data?.code === "email_already_registered") {
    const error = new Error(data?.detail || "An account with this email already exists.");
    error.existingEmail = true;
    throw error;
  }
  if (!response.ok) {
    throw new Error(
      data?.detail ||
        "We couldn't create your workspace. Please try again in a moment."
    );
  }
  return data;
}

function SignupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const invitationToken = searchParams.get("invitation");
  const isInvitation = Boolean(invitationToken);
  const [values, setValues] = useState({
    name: "",
    workspaceName: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [invitationContext, setInvitationContext] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [existingEmail, setExistingEmail] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Prefill the invited email and show the workspace they're joining.
  useEffect(() => {
    if (!invitationToken || values.email) return;
    let cancelled = false;
    fetch(`/api/invitations/lookup?token=${encodeURIComponent(invitationToken)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        setInvitationContext(data);
        if (data.invitedEmail) setValues((prev) => ({ ...prev, email: data.invitedEmail }));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [invitationToken, values.email]);

  function setField(name, value) {
    setValues((prev) => ({ ...prev, [name]: value }));
    setFieldErrors((prev) => (prev[name] ? { ...prev, [name]: undefined } : prev));
    setFormError(null);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const errors = validate(values, { isInvitation });
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    setFormError(null);
    setExistingEmail(false);

    const payload = {
      name: values.name.trim(),
      email: values.email.trim(),
      password: values.password,
    };
    if (isInvitation) {
      payload.invitationToken = invitationToken;
    } else {
      payload.workspaceName = values.workspaceName.trim();
    }

    try {
      await registerAccount(payload);
    } catch (error) {
      setExistingEmail(Boolean(error.existingEmail));
      setFormError(error.message);
      setSubmitting(false);
      return;
    }

    // Account created — establish the Auth.js session immediately.
    const result = await signIn("credentials", {
      email: values.email.trim(),
      password: values.password,
      redirect: false,
    });

    if (result?.error) {
      // Registration succeeded but sign-in failed (e.g. transient DB issue).
      setFormError(
        "Your account is ready — we just couldn't sign you in automatically. Please sign in."
      );
      setSubmitting(false);
      return;
    }

    if (isInvitation) {
      router.replace(`/accept-invitation/${invitationToken}`);
    } else {
      router.replace("/dashboard");
    }
    router.refresh();
  }

  return (
    <div className="space-y-6">
      <GoogleButton redirectTo={isInvitation ? `/accept-invitation/${invitationToken}` : "/dashboard"} />
      <FormDivider label="or sign up with email" />

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <div className="space-y-1.5">
          <Label htmlFor="name">Full name</Label>
          <Input
            id="name"
            name="name"
            autoComplete="name"
            placeholder="Your full name"
            className="h-11"
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            aria-invalid={Boolean(fieldErrors.name)}
            aria-describedby={fieldErrors.name ? "name-error" : undefined}
          />
          <FieldError id="name-error" message={fieldErrors.name} />
        </div>

        {isInvitation ? (
          <div className="space-y-2 rounded-lg border border-primary/20 bg-primary/5 px-3.5 py-3">
            <p className="text-sm text-foreground">
              {invitationContext?.workspaceName
                ? `You'll be added to ${invitationContext.workspaceName} — no workspace to create.`
                : "This invitation will add you to a workspace after signup."}
            </p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Set a password below to create your account, then you&apos;ll be signed in
              and added to the workspace automatically.
            </p>
          </div>
        ) : (
          <div className="space-y-1.5">
            <Label htmlFor="workspaceName">Workspace name</Label>
            <Input
              id="workspaceName"
              name="workspaceName"
              placeholder="e.g. Acme Corp"
              className="h-11"
              value={values.workspaceName}
              onChange={(e) => setField("workspaceName", e.target.value)}
              aria-invalid={Boolean(fieldErrors.workspaceName)}
              aria-describedby={fieldErrors.workspaceName ? "workspace-error" : undefined}
            />
            <FieldError id="workspace-error" message={fieldErrors.workspaceName} />
          </div>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="signup-email">Work email</Label>
          <Input
            id="signup-email"
            name="email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            className="h-11"
            readOnly={isInvitation}
            value={values.email}
            onChange={(e) => setField("email", e.target.value)}
            aria-invalid={Boolean(fieldErrors.email)}
            aria-describedby={fieldErrors.email ? "signup-email-error" : undefined}
          />
          {isInvitation ? (
            <p id="signup-email-hint" className="text-xs text-muted-foreground">
              The invite was sent to this address, so it&apos;s used for your account.
            </p>
          ) : null}
          <FieldError id="signup-email-error" message={fieldErrors.email} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="signup-password">Password</Label>
          <PasswordInput
            name="password"
            autoComplete="new-password"
            placeholder="At least 8 characters"
            className="h-11"
            value={values.password}
            onChange={(e) => setField("password", e.target.value)}
            aria-invalid={Boolean(fieldErrors.password)}
            aria-describedby={
              fieldErrors.password ? "signup-password-error" : "signup-password-hint"
            }
          />
          {!fieldErrors.password && (
            <p id="signup-password-hint" className="text-xs text-muted-foreground">
              Use at least 8 characters with one letter and one number.
            </p>
          )}
          <FieldError id="signup-password-error" message={fieldErrors.password} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="confirm-password">Confirm password</Label>
          <PasswordInput
            name="confirmPassword"
            autoComplete="new-password"
            placeholder="Re-enter your password"
            className="h-11"
            value={values.confirmPassword}
            onChange={(e) => setField("confirmPassword", e.target.value)}
            aria-invalid={Boolean(fieldErrors.confirmPassword)}
            aria-describedby={
              fieldErrors.confirmPassword ? "confirm-password-error" : undefined
            }
          />
          <FieldError id="confirm-password-error" message={fieldErrors.confirmPassword} />
        </div>

        {formError && (
          <div
            role="alert"
            className="rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-sm leading-relaxed text-destructive"
          >
            {formError}
            {existingEmail && (
              <>
                {" "}
                <Link
                  href={isInvitation ? `/login?invitation=${invitationToken}` : "/login"}
                  className="font-medium underline underline-offset-4"
                >
                  Sign in
                </Link>
              </>
            )}
          </div>
        )}

        <Button type="submit" className="h-11 w-full text-[15px]" disabled={submitting}>
          {submitting && <LoaderCircle className="animate-spin" aria-hidden="true" />}
          {submitting
            ? isInvitation
              ? "Creating account…"
              : "Creating workspace…"
            : isInvitation
              ? "Create account"
              : "Create workspace"}
        </Button>

        <p className="text-center text-xs leading-relaxed text-muted-foreground">
          {isInvitation ? (
            "By creating an account you agree to our "
          ) : (
            "By creating a workspace you agree to our "
          )}
          <Link href="/#" className="underline underline-offset-4 hover:text-foreground">
            Terms of Service
          </Link>{" "}
          and{" "}
          <Link href="/#" className="underline underline-offset-4 hover:text-foreground">
            Privacy Policy
          </Link>
          .
        </p>
      </form>
    </div>
  );
}

export { SignupForm };
