"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LogoMark } from "@/components/common/logo";

/**
 * Onboarding form for users who have no workspace yet.
 * Creates a workspace via the existing backend create-workspace endpoint
 * and establishes it as the active workspace.
 */
export function OnboardingForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Enter a workspace name.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch("/api/workspace/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed }),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        throw new Error(data?.detail || "Couldn't create workspace. Try again.");
      }

      // The create route now also sets the cookie, but activate explicitly
      // to be safe in case of race conditions.
      if (data?.id) {
        await fetch("/api/workspace/activate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspaceId: data.id }),
        }).catch(() => {});
      }

      window.location.replace("/dashboard");
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center text-center">
          <LogoMark className="size-10 text-white" />
          <h1 className="mt-6 text-2xl font-semibold tracking-tight text-foreground">
            Create your workspace
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            A workspace is where your financial records live. Give it a name
            you&rsquo;ll recognize — usually your company or personal finance.
          </p>
        </div>
        <form onSubmit={handleSubmit} noValidate className="mt-8 space-y-4">
          <div className="space-y-2">
            <Label htmlFor="workspace-name">Workspace name</Label>
            <Input
              id="workspace-name"
              placeholder="e.g. Acme Corp"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setError(null);
              }}
              autoFocus
              aria-invalid={Boolean(error)}
            />
            {error && (
              <p role="alert" className="text-xs text-destructive">
                {error}
              </p>
            )}
          </div>
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting && <LoaderCircle className="animate-spin" aria-hidden="true" />}
            {submitting ? "Creating workspace..." : "Create workspace"}
          </Button>
        </form>
      </div>
    </div>
  );
}
