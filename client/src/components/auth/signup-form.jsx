"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/auth/password-input";
import { GoogleButton } from "@/components/auth/google-button";
import { FormDivider } from "@/components/auth/form-divider";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate(values) {
  const errors = {};
  if (!values.name.trim()) errors.name = "Enter your full name.";
  if (!values.workspaceName.trim())
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
  const [values, setValues] = useState({
    name: "",
    workspaceName: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [existingEmail, setExistingEmail] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  function setField(name, value) {
    setValues((prev) => ({ ...prev, [name]: value }));
    setFieldErrors((prev) => (prev[name] ? { ...prev, [name]: undefined } : prev));
    setFormError(null);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const errors = validate(values);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    setFormError(null);
    setExistingEmail(false);

    try {
      await registerAccount({
        name: values.name.trim(),
        workspaceName: values.workspaceName.trim(),
        email: values.email.trim(),
        password: values.password,
      });
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
        "Your workspace is ready — we just couldn't sign you in automatically. Please sign in."
      );
      setSubmitting(false);
      return;
    }

    router.replace("/dashboard");
    router.refresh();
  }

  return (
    <div className="space-y-6">
      <GoogleButton />
      <FormDivider label="or sign up with email" />

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="name">Full name</Label>
          <Input
            id="name"
            name="name"
            autoComplete="name"
            placeholder="Alex Rivera"
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            aria-invalid={Boolean(fieldErrors.name)}
            aria-describedby={fieldErrors.name ? "name-error" : undefined}
          />
          <FieldError id="name-error" message={fieldErrors.name} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="workspaceName">Workspace name</Label>
          <Input
            id="workspaceName"
            name="workspaceName"
            placeholder="Acme Inc."
            value={values.workspaceName}
            onChange={(e) => setField("workspaceName", e.target.value)}
            aria-invalid={Boolean(fieldErrors.workspaceName)}
            aria-describedby={fieldErrors.workspaceName ? "workspace-error" : undefined}
          />
          <FieldError id="workspace-error" message={fieldErrors.workspaceName} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="signup-email">Work email</Label>
          <Input
            id="signup-email"
            name="email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            value={values.email}
            onChange={(e) => setField("email", e.target.value)}
            aria-invalid={Boolean(fieldErrors.email)}
            aria-describedby={fieldErrors.email ? "signup-email-error" : undefined}
          />
          <FieldError id="signup-email-error" message={fieldErrors.email} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="signup-password">Password</Label>
          <PasswordInput
            name="password"
            autoComplete="new-password"
            placeholder="At least 8 characters"
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

        <div className="space-y-2">
          <Label htmlFor="confirm-password">Confirm password</Label>
          <PasswordInput
            name="confirmPassword"
            autoComplete="new-password"
            placeholder="Re-enter your password"
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
                <Link href="/login" className="font-medium underline underline-offset-4">
                  Sign in
                </Link>
              </>
            )}
          </div>
        )}

        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting && <LoaderCircle className="animate-spin" aria-hidden="true" />}
          {submitting ? "Creating workspace…" : "Create workspace"}
        </Button>

        <p className="text-center text-xs leading-relaxed text-muted-foreground">
          By creating a workspace you agree to our{" "}
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
