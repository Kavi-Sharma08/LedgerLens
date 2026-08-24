"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Layers, Plus, Upload } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Select } from "@/components/ui/select";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, humanize } from "@/components/domain/status-badge";
import { SourceTypeIcon, sourceTypeLabel } from "@/components/domain/source-type";
import { listSources, createSource } from "@/lib/api/sources";
import { listFiles, uploadFile } from "@/lib/api/files";
import { formatCount, formatDateTime } from "@/lib/format";

/**
 * Sources screen: connect financial sources and import their statements.
 * Upload progress, duplicate detection and processing status all reflect the
 * backend's own state machine — the UI never pretends a file succeeded.
 */
export function SourcesView() {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [openSourceId, setOpenSourceId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    listSources({ limit: 50, signal: controller.signal })
      .then((result) => {
        if (!cancelled && !controller.signal.aborted) {
          setSources(result.items);
          setError(null);
        }
      })
      .catch((err) => {
        if (err?.name === "AbortError" || controller.signal.aborted || cancelled) return;
        setError(err?.message || null);
      })
      .finally(() => {
        if (!cancelled && !controller.signal.aborted) setLoading(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [reloadKey]);

  function handleCreated() {
    setReloadKey((key) => key + 1);
  }

  function handleRetry() {
    setLoading(true);
    setReloadKey((key) => key + 1);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Connect at least two sources to start reconciling between them.
        </p>
        <CreateSourceDialog onCreated={handleCreated} />
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2" aria-busy="true" aria-label="Loading sources">
          {[0, 1].map((index) => (
            <Skeleton key={index} className="h-44 rounded-xl" />
          ))}
        </div>
      ) : error ? (
        <ErrorState
          title="Unable to load sources"
          message={error}
          onRetry={handleRetry}
        />
      ) : sources.length === 0 ? (
        <EmptyState
          icon={Layers}
          title="No financial sources yet"
          description="Add your bank account, payment processor or accounting system. Each source holds the statements you'll reconcile against each other."
        />
      ) : (
        <ul role="list" className="grid gap-4 sm:grid-cols-2">
          {sources.map((source) => (
            <li key={source.id}>
              <SourceCard
                source={source}
                expanded={openSourceId === source.id}
                onToggle={() =>
                  setOpenSourceId((current) => (current === source.id ? null : source.id))
                }
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SourceCard({ source, expanded, onToggle }) {
  return (
    <div className="rounded-xl border border-border bg-card transition-shadow hover:shadow-sm">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-start gap-3 p-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/50 rounded-xl"
      >
        <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent">
          <SourceTypeIcon type={source.type} className="size-5 text-primary" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="truncate font-medium text-foreground">{source.name}</span>
            {source.status !== "ACTIVE" && (
              <Badge variant="neutral">{humanize(source.status)}</Badge>
            )}
          </span>
          <span className="mt-0.5 block truncate text-sm text-muted-foreground">
            {source.institution || sourceTypeLabel(source.type)} · {source.currency}
          </span>
        </span>
        <span
          aria-hidden="true"
          className={
            "mt-1 shrink-0 text-muted-foreground transition-transform " +
            (expanded ? "rotate-180" : "")
          }
        >
          ▾
        </span>
      </button>

      {expanded && (
        <div className="border-t border-border p-4 pt-3">
          <FilesPanel sourceId={source.id} />
        </div>
      )}
    </div>
  );
}

function FilesPanel({ sourceId }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState(null);
  const [uploadError, setUploadError] = useState(null);

  const loadFiles = useCallback(
    ({ silent = false } = {}) => {
      // State updates stay in promise callbacks; the polling interval and the
      // effect both call this without synchronous mutation.
      return listFiles({ sourceId, limit: 20 })
        .then((result) => {
          setFiles(result.items);
          setError(null);
        })
        .catch((err) => {
          if (err?.name === "AbortError") return;
          setError(err?.message || null);
        })
        .finally(() => {
          if (!silent) setLoading(false);
        });
    },
    [sourceId]
  );

  useEffect(() => {
    loadFiles();
    // Files may sit in PROCESSING for a while; poll while the panel is open.
    const timer = setInterval(() => loadFiles({ silent: true }), 5000);
    return () => clearInterval(timer);
  }, [loadFiles]);

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setUploading(true);
    setProgress(0);
    setUploadResult(null);
    setUploadError(null);
    try {
      const response = await uploadFile({
        sourceId,
        file,
        onProgress: setProgress,
      });
      setUploadResult(response);
      await loadFiles({ silent: true });
    } catch (err) {
      if (err?.name === "AbortError") return;
      setUploadError(err?.message || null);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
          Imported files
        </h4>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv,.json,application/json,.xlsx,.xls"
          onChange={handleUpload}
          className="sr-only"
          aria-label="Choose a statement file to import"
        />
        <Button
          size="xs"
          disabled={uploading}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload aria-hidden="true" data-icon="inline-start" />
          {uploading ? `Importing… ${progress}%` : "Import file"}
        </Button>
      </div>

      {uploading && (
        <div
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Uploading file"
          className="h-1.5 overflow-hidden rounded-full bg-muted"
        >
          <div className="h-full bg-primary transition-[width]" style={{ width: `${progress}%` }} />
        </div>
      )}

      {uploadResult && (
        <div
          role="status"
          className={
            "rounded-lg px-3 py-2 text-sm " +
            (uploadResult.isDuplicate
              ? "bg-muted text-muted-foreground"
              : "bg-success/10 text-success")
          }
        >
          {uploadResult.isDuplicate ? (
            <>
              This file was already imported — its records were skipped to avoid duplicates.
            </>
          ) : (
            <>
              Import accepted. Processing{" "}
              {formatCount(uploadResult.file.transactionCount ?? 0)} records…
            </>
          )}
        </div>
      )}

      {uploadError && (
        <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {uploadError}
        </p>
      )}

      {loading ? (
        <Skeleton className="h-16 w-full rounded-lg" />
      ) : error ? (
        <p role="alert" className="text-sm text-destructive">{error}</p>
      ) : files.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-3 py-4 text-center text-sm text-muted-foreground">
          No files imported yet for this source.
        </p>
      ) : (
        <ul role="list" className="divide-y divide-border rounded-lg border border-border">
          {files.map((file) => (
            <li key={file.id} className="flex items-center gap-3 px-3 py-2.5">
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-foreground">
                  {file.fileName}
                </span>
                <span className="block text-xs text-muted-foreground">
                  {formatDateTime(file.uploadedAt)}
                  {file.transactionCount > 0 &&
                    ` · ${formatCount(file.transactionCount)} records`}
                  {file.skippedDuplicateCount > 0 &&
                    ` · ${formatCount(file.skippedDuplicateCount)} duplicates skipped`}
                  {file.errorCount > 0 && ` · ${formatCount(file.errorCount)} errors`}
                </span>
                {file.error && (
                  <span className="mt-0.5 block truncate text-xs text-destructive">
                    {file.error}
                  </span>
                )}
              </span>
              <StatusBadge kind="file" value={file.status} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const SOURCE_TYPE_ITEMS = [
  { value: "BANK", label: "Bank account" },
  { value: "PAYMENT_PROCESSOR", label: "Payment processor" },
  { value: "ACCOUNTING", label: "Accounting system" },
  { value: "CARD", label: "Card issuer" },
  { value: "ERP", label: "ERP / ledger" },
  { value: "MANUAL", label: "Manual entry" },
];

function CreateSourceDialog({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("BANK");
  const [institution, setInstitution] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await createSource({
        name: name.trim(),
        type,
        institution: institution.trim() || undefined,
      });
      setName("");
      setInstitution("");
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(err?.message || "The source couldn't be created.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm"><Plus aria-hidden="true" /> Add source</Button>} />
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Add a financial source</DialogTitle>
            <DialogDescription>
              A source is one system of record — a bank account, a payment processor.
              You&rsquo;ll import its statements as files.
            </DialogDescription>
          </DialogHeader>

          <div className="mt-4 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="source-name">Name</Label>
              <Input
                id="source-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. HDFC Current Account"
                required
                maxLength={120}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="source-type">Type</Label>
              <Select
                value={type}
                onValueChange={setType}
                items={SOURCE_TYPE_ITEMS}
                placeholder="Choose a type"
                triggerClassName="w-full"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="source-institution">Institution (optional)</Label>
              <Input
                id="source-institution"
                value={institution}
                onChange={(event) => setInstitution(event.target.value)}
                placeholder="e.g. HDFC Bank"
                maxLength={160}
              />
            </div>
          </div>

          {error && (
            <p role="alert" className="mt-3 text-sm text-destructive">
              {error}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!name.trim() || creating}>
              {creating ? "Creating…" : "Create source"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
