"use client";

import { useState } from "react";
import { CircleCheck, LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/auth/password-input";
import { DrawerSection } from "@/components/common/drawer";

function validatePassword(password) {
  if (!password) return "Enter a new password.";
  if (password.length < 8) return "Passwords need to be at least 8 characters long.";
  if (!/[a-zA-Z]/.test(password) || !/\d/.test(password))
    return "Include at least one letter and one number.";
  return null;
}

/**
 * Password management section in settings.
 * Allows setting a new password (for Google-only users) or changing existing password.
 */
export function PasswordSection() {
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
      const response = await fetch("/api/set-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(data?.detail || "We couldn't update your password. Please try again.");
      }

      setSuccess(true);
      setPassword("");
      setConfirmPassword("");
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <DrawerSection title="Password">
        {success && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-success/10 px-3 py-2 text-sm text-success">
            <CircleCheck className="size-4 shrink-0" aria-hidden="true" />
            Your password has been updated.
          </div>
        )}
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="new-password" className="text-sm font-medium text-foreground">
              New password
            </label>
            <PasswordInput
              id="new-password"
              name="password"
              autoComplete="new-password"
              placeholder="At least 8 characters"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setFieldError(null);
                setFormError(null);
                setSuccess(false);
              }}
            />
            {fieldError && (
              <p role="alert" className="text-xs text-destructive">
                {fieldError}
              </p>
            )}
          </div>
          <div className="space-y-2">
            <label htmlFor="confirm-pw" className="text-sm font-medium text-foreground">
              Confirm password
            </label>
            <PasswordInput
              id="confirm-pw"
              name="confirmPassword"
              autoComplete="new-password"
              placeholder="Re-enter your password"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                setFormError(null);
                setSuccess(false);
              }}
            />
          </div>
          {formError && (
            <p role="alert" className="text-sm text-destructive">
              {formError}
            </p>
          )}
          <div className="flex justify-end">
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting && <LoaderCircle className="animate-spin" aria-hidden="true" />}
              {submitting ? "Saving..." : "Set password"}
            </Button>
          </div>
        </form>
        <p className="mt-3 text-xs text-muted-foreground">
          Create a password to sign in without Google. You can also continue using Google to sign in.
        </p>
      </DrawerSection>
    </div>
  );
}
