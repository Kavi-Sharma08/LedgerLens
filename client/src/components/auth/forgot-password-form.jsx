"use client";

import { useState } from "react";
import { CircleCheck, LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [sentTo, setSentTo] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!email.trim()) {
      setFieldError("Enter the email address you signed up with.");
      return;
    }
    if (!EMAIL_PATTERN.test(email.trim())) {
      setFieldError("That email address doesn't look right. Check it and try again.");
      return;
    }

    setSubmitting(true);
    setFieldError(null);

    try {
      await fetch("/api/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
    } catch {
      // Silently ignore — we always show the same response
    }

    setSentTo(email.trim());
    setSubmitting(false);
  }

  if (sentTo) {
    return (
      <div className="space-y-4" aria-live="polite">
        <div className="flex items-center gap-2.5">
          <CircleCheck className="size-5 text-success" aria-hidden="true" />
          <p className="text-sm font-medium text-foreground">Check your inbox</p>
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">
          If an account exists for <span className="font-medium text-foreground">{sentTo}</span>,
          we&rsquo;ve sent instructions to reset your password. The link expires in 30 minutes.
        </p>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Didn&rsquo;t get it? Check your spam folder, or{" "}
          <button
            type="button"
            onClick={() => setSentTo(null)}
            className="font-medium text-primary underline-offset-4 hover:underline outline-none focus-visible:ring-2 focus-visible:ring-ring/50 rounded-sm"
          >
            try another email
          </button>
          .
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="forgot-email">Email</Label>
        <Input
          id="forgot-email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@company.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setFieldError(null);
          }}
          aria-invalid={Boolean(fieldError)}
          aria-describedby={fieldError ? "forgot-email-error" : undefined}
        />
        {fieldError && (
          <p id="forgot-email-error" role="alert" className="text-xs text-destructive">
            {fieldError}
          </p>
        )}
      </div>

      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting && <LoaderCircle className="animate-spin" aria-hidden="true" />}
        {submitting ? "Sending..." : "Send reset instructions"}
      </Button>
    </form>
  );
}

export { ForgotPasswordForm };
