"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Drawer, DetailField, DrawerSection } from "@/components/common/drawer";
import { StatusBadge, exceptionReasonLabel } from "@/components/domain/status-badge";
import { TransactionDrawer } from "@/components/domain/transaction-drawer";
import { AiAnalysis } from "@/components/domain/ai-analysis";
import { useAiContext } from "@/components/common/ai-context";
import {
  updateExceptionStatus,
  addExceptionNote,
  updateExceptionNote,
  deleteExceptionNote,
} from "@/lib/api/exceptions";
import { analyzeException } from "@/lib/api/ai";
import { formatDateTime, formatRelativeTime } from "@/lib/format";

const STATUS_ACTIONS = [
  { value: "INVESTIGATING", label: "Start investigating" },
  { value: "RESOLVED", label: "Mark resolved" },
  { value: "DISMISSED", label: "Dismiss" },
  { value: "OPEN", label: "Reopen" },
];

const NOTE_MAX_LENGTH = 2000;

function noteErrorMessage(err) {
  if (err?.status === 403) return "You don't have permission to modify this exception.";
  if (err?.status === 404) return "Exception not found.";
  if (err?.status === 422) return err?.message || "Please enter a note.";
  return "Unable to save note. Please try again.";
}

function InvestigationNotes({ exceptionId, initialNotes, onNotesChanged }) {
  const [notes, setNotes] = useState(initialNotes);
  const [noteText, setNoteText] = useState("");
  const [saving, setSaving] = useState(false);
  const [addError, setAddError] = useState(null);

  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState("");
  const [savingEditId, setSavingEditId] = useState(null);
  const [editError, setEditError] = useState(null);

  const [confirmingDeleteId, setConfirmingDeleteId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [deleteError, setDeleteError] = useState(null);

  useEffect(() => {
    setNotes(initialNotes || []);
  }, [initialNotes]);

  function refresh() {
    return onNotesChanged?.();
  }

  async function handleAdd() {
    const text = noteText.trim();
    if (!text) {
      setAddError("Please enter a note.");
      return;
    }
    if (text.length > NOTE_MAX_LENGTH) {
      setAddError(`Note is too long. Keep it under ${NOTE_MAX_LENGTH} characters.`);
      return;
    }
    setSaving(true);
    setAddError(null);
    try {
      const created = await addExceptionNote(exceptionId, text);
      setNotes((prev) => [...prev, created]);
      setNoteText("");
      await refresh();
    } catch (err) {
      setAddError(noteErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleStartEdit(note) {
    setEditingId(note.id);
    setEditText(note.text);
    setEditError(null);
    setDeleteError(null);
  }

  function handleCancelEdit() {
    setEditingId(null);
    setEditText("");
    setEditError(null);
  }

  async function handleSaveEdit(note) {
    const text = editText.trim();
    if (!text) {
      setEditError("Please enter a note.");
      return;
    }
    if (text.length > NOTE_MAX_LENGTH) {
      setEditError(`Note is too long. Keep it under ${NOTE_MAX_LENGTH} characters.`);
      return;
    }
    setSavingEditId(note.id);
    setEditError(null);
    try {
      const updated = await updateExceptionNote(exceptionId, note.id, text);
      setNotes((prev) => prev.map((n) => (n.id === note.id ? updated : n)));
      setEditingId(null);
      setEditText("");
      await refresh();
    } catch (err) {
      setEditError(noteErrorMessage(err));
    } finally {
      setSavingEditId(null);
    }
  }

  function handleAskDelete(note) {
    setConfirmingDeleteId(note.id);
    setDeleteError(null);
    setEditError(null);
  }

  function handleCancelDelete() {
    setConfirmingDeleteId(null);
    setDeleteError(null);
  }

  async function handleConfirmDelete(note) {
    setDeletingId(note.id);
    setDeleteError(null);
    try {
      await deleteExceptionNote(exceptionId, note.id);
      setNotes((prev) => prev.filter((n) => n.id !== note.id));
      setConfirmingDeleteId(null);
      await refresh();
    } catch (err) {
      setDeleteError(noteErrorMessage(err));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div>
      {notes.length > 0 ? (
        <ul role="list" className="mb-4 space-y-3">
          {notes.map((note) => {
            const isEditing = editingId === note.id;
            const isConfirmingDelete = confirmingDeleteId === note.id;
            const meta = [
              note.createdBy,
              note.createdAt ? formatRelativeTime(note.createdAt) : null,
            ]
              .filter(Boolean)
              .join(" · ");

            return (
              <li key={note.id || note.text} className="rounded-lg bg-muted/40 px-3 py-2.5">
                {isEditing ? (
                  <div>
                    <textarea
                      autoFocus
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      rows={3}
                      maxLength={NOTE_MAX_LENGTH}
                      className="w-full resize-y rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring/50"
                    />
                    <div className="mt-2 flex justify-end gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={savingEditId === note.id}
                        onClick={handleCancelEdit}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={savingEditId === note.id || !editText.trim()}
                        onClick={() => handleSaveEdit(note)}
                      >
                        {savingEditId === note.id ? "Saving..." : "Save changes"}
                      </Button>
                    </div>
                    {editError && (
                      <p role="alert" className="mt-2 text-sm text-destructive">{editError}</p>
                    )}
                  </div>
                ) : (
                  <div>
                    <p className="text-sm leading-relaxed text-foreground">{note.text}</p>
                    <div className="mt-1.5 flex items-center justify-between gap-3">
                      <p className="text-xs text-muted-foreground">{meta}</p>
                      {note.id && (
                        <div className="flex shrink-0 gap-3 text-xs text-muted-foreground">
                          <button
                            type="button"
                            className="outline-none hover:text-foreground focus-visible:underline"
                            onClick={() => handleStartEdit(note)}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="outline-none hover:text-destructive focus-visible:underline"
                            onClick={() => handleAskDelete(note)}
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                    {isConfirmingDelete && (
                      <div className="mt-2 rounded-md border border-border bg-background px-3 py-2.5">
                        <p className="text-sm text-foreground">Delete this investigation note?</p>
                        <div className="mt-2 flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={deletingId === note.id}
                            onClick={handleCancelDelete}
                          >
                            Cancel
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            disabled={deletingId === note.id}
                            onClick={() => handleConfirmDelete(note)}
                          >
                            {deletingId === note.id ? "Deleting..." : "Delete"}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mb-4 text-sm text-muted-foreground">No investigation notes yet.</p>
      )}

      {deleteError && (
        <p role="alert" className="mb-3 text-sm text-destructive">{deleteError}</p>
      )}

      <div className="flex gap-2">
        <textarea
          value={noteText}
          onChange={(e) => setNoteText(e.target.value)}
          placeholder="Add a note..."
          rows={2}
          maxLength={NOTE_MAX_LENGTH}
          className="flex-1 resize-y rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring/50"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleAdd();
            }
          }}
        />
        <Button
          size="sm"
          variant="outline"
          disabled={saving}
          onClick={handleAdd}
        >
          {saving ? "Adding..." : "Add"}
        </Button>
      </div>
      {addError && (
        <p role="alert" className="mt-2 text-sm text-destructive">{addError}</p>
      )}
    </div>
  );
}

export function ExceptionDetailDrawer({
  exception,
  onClose,
  onStatusChange,
  onNoteAdded,
}) {
  const { setExceptionContext, clearEntityContext } = useAiContext();
  const [updatingStatus, setUpdatingStatus] = useState(null);
  const [openTransactionId, setOpenTransactionId] = useState(null);

  useEffect(() => {
    if (exception?.id) {
      setExceptionContext(exception.id, exception.reconciliationRunId);
    }
    return () => {
      clearEntityContext();
    };
  }, [exception?.id, exception?.reconciliationRunId, setExceptionContext, clearEntityContext]);

  if (!exception) return null;

  async function handleStatusChange(status) {
    setUpdatingStatus(status);
    try {
      await updateExceptionStatus(exception.id, status);
      await onStatusChange?.(status);
    } catch {
      // Error handled by keeping the previous state.
    } finally {
      setUpdatingStatus(null);
    }
  }

  return (
    <Drawer open={Boolean(exception)} onClose={onClose} label="Exception detail">
      <div className="divide-y divide-border">
        <DrawerSection>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
            <div className="col-span-2 flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-foreground">
                {exceptionReasonLabel(exception.reasonCode)}
              </span>
              <StatusBadge kind="exception" value={exception.status} />
            </div>
            <div className="col-span-2">
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Reason</dt>
              <dd className="mt-0.5 text-sm leading-relaxed text-muted-foreground">
                {exception.detail || "No matching candidate was found during reconciliation."}
              </dd>
            </div>
            <DetailField label="Detected">{formatDateTime(exception.createdAt)}</DetailField>
          </dl>
        </DrawerSection>

        {exception.transactionIds?.length > 0 && (
          <DrawerSection title="Linked transactions">
            <ul role="list" className="space-y-2">
              {exception.transactionIds.map((id) => (
                <li key={id}>
                  <button
                    type="button"
                    onClick={() => setOpenTransactionId(id)}
                    className="flex w-full items-center justify-between rounded-md bg-muted px-3 py-2 text-left text-sm text-foreground outline-none hover:bg-muted/70 focus-visible:ring-2 focus-visible:ring-ring/50"
                  >
                    <span className="truncate font-medium">Transaction</span>
                    <span className="text-xs text-primary">View details</span>
                  </button>
                </li>
              ))}
            </ul>
          </DrawerSection>
        )}

        <DrawerSection title="AI explanation">
          <AiAnalysis
            label="Explain this exception"
            analyze={({ signal }) => analyzeException(exception.id, { signal })}
          />
        </DrawerSection>

        <DrawerSection title="Actions">
          <div className="flex flex-wrap gap-2">
            {STATUS_ACTIONS.filter((a) => a.value !== exception.status).map((action) => (
              <Button
                key={action.value}
                variant="outline"
                size="sm"
                disabled={updatingStatus !== null}
                onClick={() => handleStatusChange(action.value)}
              >
                {updatingStatus === action.value ? "Saving..." : action.label}
              </Button>
            ))}
          </div>
        </DrawerSection>

        <DrawerSection title="Investigation notes">
          <InvestigationNotes
            exceptionId={exception.id}
            initialNotes={exception.notes || []}
            onNotesChanged={onNoteAdded}
          />
        </DrawerSection>
      </div>

      <TransactionDrawer
        transactionId={openTransactionId}
        onClose={() => setOpenTransactionId(null)}
      />
    </Drawer>
  );
}
