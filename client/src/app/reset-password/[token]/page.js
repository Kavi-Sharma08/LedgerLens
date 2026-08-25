"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { CircleCheck, LoaderCircle } from "lucide-react";

import { AuthShell } from "@/components/auth/auth-shell";
import { PasswordInput } from "@/components/auth/password-input";
import { Button } from "@/components/ui/button";

function validatePassword(password) {
  if (!password) return "Enter a new password.";
  if (password.length < 8) return "Passwords need to be at least 8 characters long.";
  if (!/[a-zA-Z]/.test(password) || !/\d/.test(password))
    return "Include at least one letter and one number.";
  return null;
}

export default function ResetPasswordPage() {
  const params = useParams();
  const router = useRouter();
  const token = params?.token;

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldError, setFieldError] = useState(null);
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setFormError(null);
    setSuccess(false);

    const error = validatePassword(password);
    if (error) {
      setFieldError(error);
      return;
    }
    if (password !== confirmPassword) {
      setFieldError(null);
      setFormError("Passwords don't match.");
      return;
    }

    setFieldError(null);
    setSubmitting(true);

    try {
      const response = await fetch("/api/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(data?.detail || "We couldn't reset your password.");
      }

      setSuccess(true);
      setTimeout(() => router.push("/login"), 3000);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <AuthShell
        title="Password reset"
        subtitle="Your password has been updated. You'll be redirected to sign in shortly."
        footer={
          <Link
            href="/login"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Go to sign in
          </Link>
        }
      >
        <div className="flex items-center gap-2.5 rounded-lg bg-success/10 px-3 py-3 text-sm text-success">
          <CircleCheck className="size-5 shrink-0" aria-hidden="true" />
          Password updated successfully.
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Reset your password"
      subtitle="Enter your new password below."
      footer={
        <>
          Remember your password?{" "}
          <Link
            href="/login"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="reset-password" className="text-sm font-medium text-foreground">
            New password
          </label>
          <PasswordInput
            id="reset-password"
            name="password"
            autoComplete="new-password"
            placeholder="At least 8 characters"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setFieldError(null);
              setFormError(null);
            }}
          />
          {fieldError && (
            <p role="alert" className="text-xs text-destructive">
              {fieldError}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <label htmlFor="confirm-reset" className="text-sm font-medium text-foreground">
            Confirm password
          </label>
          <PasswordInput
            id="confirm-reset"
            name="confirmPassword"
            autoComplete="new-password"
            placeholder="Re-enter your password"
            value={confirmPassword}
            onChange={(e) => {
              setConfirmPassword(e.target.value);
              setFormError(null);
            }}
          />
        </div>

        {formError && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-sm text-destructive">
            {formError}
          </div>
        )}

        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting && <LoaderCircle className="animate-spin" aria-hidden="true" />}
          {submitting ? "Resetting..." : "Reset password"}
        </Button>
      </form>
    </AuthShell>
  );
}
