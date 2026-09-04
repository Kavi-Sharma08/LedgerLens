"use client";

import { useState } from "react";
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

/** Auth.js error codes (arrive via ?error= after failed OAuth redirects). */
const OAUTH_ERROR_MESSAGES = {
  Configuration:
    "LedgerLens is temporarily misconfigured. Please try again in a few minutes.",
  AccessDenied:
    "Access was denied. If you declined the Google prompt, try signing in again.",
  OAuthAccountNotLinked:
    "This Google account isn't linked to an existing LedgerLens account yet. Sign in with your email and password first.",
  Verification: "The sign-in link has expired. Please request a new one.",
};

function validate({ email, password }) {
  const errors = {};
  if (!email.trim()) errors.email = "Enter your email address.";
  else if (!EMAIL_PATTERN.test(email.trim()))
    errors.email = "That email address doesn't look right. Check it and try again.";
  if (!password) errors.password = "Enter your password.";
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

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/dashboard";
  const invitationToken = searchParams.get("invitation");

  const [values, setValues] = useState({ email: "", password: "" });
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(
    OAUTH_ERROR_MESSAGES[searchParams.get("error")] ?? null
  );
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

    // redirect:false keeps us on-page so we can show friendly errors.
    const result = await signIn("credentials", {
      email: values.email.trim(),
      password: values.password,
      redirect: false,
    });

    if (result?.error) {
      setFormError(
        "We couldn't sign you in. Check your email and password and try again."
      );
      setSubmitting(false);
      return;
    }

    if (invitationToken) {
      router.replace(`/accept-invitation/${invitationToken}`);
    } else {
      router.replace(nextPath.startsWith("/") ? nextPath : "/dashboard");
    }
    router.refresh();
  }

  return (
    <div className="space-y-6">
      <GoogleButton
        redirectTo={invitationToken ? `/accept-invitation/${invitationToken}` : nextPath}
      />
      <FormDivider label="or continue with email" />

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            className="h-11"
            value={values.email}
            onChange={(e) => setField("email", e.target.value)}
            aria-invalid={Boolean(fieldErrors.email)}
            aria-describedby={fieldErrors.email ? "email-error" : undefined}
          />
          <FieldError id="email-error" message={fieldErrors.email} />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link
              href="/forgot-password"
              className="rounded-sm text-xs font-medium text-muted-foreground underline-offset-4 hover:text-primary hover:underline outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              Forgot password?
            </Link>
          </div>
          <PasswordInput
            name="password"
            autoComplete="current-password"
            placeholder="Enter your password"
            className="h-11"
            value={values.password}
            onChange={(e) => setField("password", e.target.value)}
            aria-invalid={Boolean(fieldErrors.password)}
            aria-describedby={fieldErrors.password ? "password-error" : undefined}
          />
          <FieldError id="password-error" message={fieldErrors.password} />
        </div>

        {formError && (
          <div
            role="alert"
            className="rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-sm leading-relaxed text-destructive"
          >
            {formError}
          </div>
        )}

        <Button
          type="submit"
          className="h-11 w-full text-[15px]"
          disabled={submitting}
        >
          {submitting && <LoaderCircle className="animate-spin" aria-hidden="true" />}
          {submitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}

export { LoginForm };
