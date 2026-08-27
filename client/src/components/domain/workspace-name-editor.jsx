"use client";

import { useState } from "react";
import { CircleCheck, LoaderCircle, Pencil } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { updateWorkspace } from "@/lib/api/workspaces";

/**
 * Inline workspace name editor. Shows the current name with an edit button,
 * and switches to an input + save/cancel flow on click.
 */
export function WorkspaceNameEditor({ workspaceId, initialName }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(initialName || "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  function handleEdit() {
    setEditing(true);
    setName(initialName || "");
    setError(null);
    setSuccess(false);
  }

  function handleCancel() {
    setEditing(false);
    setName(initialName || "");
    setError(null);
  }

  async function handleSave() {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Enter a workspace name.");
      return;
    }
    if (trimmed === initialName) {
      setEditing(false);
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccess(false);

    try {
      await updateWorkspace(workspaceId, { name: trimmed });
      setSuccess(true);
      setEditing(false);
    } catch (err) {
      setError(err?.message || "Failed to update workspace name.");
    } finally {
      setSubmitting(false);
    }
  }

  if (editing) {
    return (
      <div className="flex items-center gap-2">
        <Input
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSave();
            if (e.key === "Escape") handleCancel();
          }}
          autoFocus
          className="h-8 max-w-xs text-sm"
          aria-label="Workspace name"
        />
        <Button size="sm" onClick={handleSave} disabled={submitting}>
          {submitting ? (
            <LoaderCircle className="animate-spin" aria-hidden="true" />
          ) : (
            "Save"
          )}
        </Button>
        <Button size="sm" variant="ghost" onClick={handleCancel} disabled={submitting}>
          Cancel
        </Button>
        {error && (
          <p role="alert" className="text-xs text-destructive">{error}</p>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span>{initialName || "—"}</span>
      <button
        type="button"
        onClick={handleEdit}
        className="inline-flex items-center justify-center rounded-md p-1 text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
        aria-label="Edit workspace name"
      >
        <Pencil className="size-3.5" aria-hidden="true" />
      </button>
      {success && (
        <span className="flex items-center gap-1 text-xs text-success">
          <CircleCheck className="size-3.5" aria-hidden="true" />
          Saved
        </span>
      )}
    </div>
  );
}
