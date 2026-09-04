"use client";

import { useEffect, useState } from "react";

import { Drawer, DetailField, DrawerSection } from "@/components/common/drawer";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfidenceIndicator } from "@/components/domain/confidence-indicator";
import { EvidenceList } from "@/components/domain/evidence-list";
import { AiAnalysis } from "@/components/domain/ai-analysis";
import { StatusBadge, humanize } from "@/components/domain/status-badge";
import { useAiContext } from "@/components/common/ai-context";
import { formatMoney, formatDate, formatDateTime } from "@/lib/format";
import {
  getTransaction,
  listTransactionMatches,
} from "@/lib/api/transactions";
import { analyzeTransaction } from "@/lib/api/ai";
import { getSource } from "@/lib/api/sources";
import { getRun } from "@/lib/api/reconciliations";

/**
 * Transaction detail side panel.
 *
 * Everything shown comes from the backend for the currently active workspace:
 * the canonical transaction, its source, its reconciliation run (when opened
 * from a Unmatched record) and the match documents the engine persisted for it.
 * The frontend never recomputes matching outcomes — it only renders stored
 * results and explains an unmatched outcome in plain language.
 */
export function TransactionDrawer({ transactionId, onClose, context }) {
  const { setTransactionContext, clearEntityContext } = useAiContext();
  const [loaded, setLoaded] = useState(null); // { id, transaction, matches, source, run }
  const [error, setError] = useState(null);

  const runId = context?.runId;

  useEffect(() => {
    if (transactionId) {
      setTransactionContext(transactionId, runId);
    }
    return () => {
      clearEntityContext();
    };
  }, [transactionId, runId, setTransactionContext, clearEntityContext]);


  useEffect(() => {
    if (!transactionId) return;
    const controller = new AbortController();

    const fetchSource = (txn) =>
      txn?.sourceId
        ? getSource(txn.sourceId, { signal: controller.signal }).catch(() => null)
        : Promise.resolve(null);

    const fetchRun = () =>
      runId
        ? getRun(runId, { signal: controller.signal }).catch(() => null)
        : Promise.resolve(null);

    getTransaction(transactionId, { signal: controller.signal })
      .then((txn) => Promise.all([txn, fetchSource(txn), listTransactionMatches(transactionId, { signal: controller.signal }).catch(() => null), fetchRun()]))
      .then(([txn, source, matchPage, run]) => {
        if (controller.signal.aborted) return;
        setLoaded({
          id: transactionId,
          transaction: txn,
          source,
          matches: matchPage ? matchPage.items : [],
          run,
        });
        setError(null);
      })
      .catch((err) => {
        if (err?.name === "AbortError" || controller.signal.aborted) return;
        setError(err);
      });

    return () => controller.abort();
  }, [transactionId, runId]);

  return (
    <Drawer open={Boolean(transactionId)} onClose={onClose} label="Transaction details">
      <TransactionDetail
        transactionId={transactionId}
        loaded={loaded}
        error={error}
        context={context}
      />
    </Drawer>
  );
}

export function TransactionDetail({ transactionId, loaded, error, context }) {
  if (error && loaded?.id !== transactionId) {
    return <TransactionErrorState error={error} transactionId={transactionId} />;
  }
  if (!loaded || loaded.id !== transactionId || !loaded.transaction) {
    return <DrawerSkeleton />;
  }

  const { transaction, matches, source, run } = loaded;
  const match = matches?.[0] ?? null;
  const isUnmatched = context?.kind === "unmatched" || !match;
  const counterpartIds = match
    ? (match.transactionIds || []).filter((id) => id !== transaction.id)
    : [];

  return (
    <article>
      <header className="px-5 py-5">
        <div className="flex items-start justify-between gap-3">
          <p className="text-2xl font-semibold tabular-nums tracking-tight text-foreground">
            {formatMoney(transaction.amount, transaction.currency)}
          </p>
          <StatusBadge
            kind="reconciliation"
            value={isUnmatched ? "UNMATCHED" : match?.status ?? "UNMATCHED"}
          />
        </div>
        <p className="mt-1 truncate text-sm text-muted-foreground">
          {transaction.counterparty || transaction.description || "No counterparty recorded"}
        </p>
      </header>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-4 px-5 pb-5">
        <DetailField label="Date">{formatDate(transaction.transactionDate)}</DetailField>
        <DetailField label="Direction">{humanize(transaction.direction)}</DetailField>
        <DetailField label="Amount">{formatMoney(transaction.amount, transaction.currency)}</DetailField>
        <DetailField label="Currency">{transaction.currency}</DetailField>
        <DetailField label="Type">{humanize(transaction.transactionType)}</DetailField>
        <DetailField label="Record status">{humanize(transaction.status)}</DetailField>
        <DetailField label="Counterparty">{transaction.counterparty || "—"}</DetailField>
        {transaction.postedDate && (
          <DetailField label="Posted">{formatDate(transaction.postedDate)}</DetailField>
        )}
        <DetailField label="Reference" className="col-span-2">
          <span className="text-[13px]">{transaction.reference || "—"}</span>
        </DetailField>
        <DetailField label="Description" className="col-span-2">
          {transaction.description || "—"}
        </DetailField>
        <DetailField label="Source" className="col-span-2">
          {source ? (
            <span>
              {source.name}
              {source.institution ? ` · ${source.institution}` : ""}
              {source.accountIdentifier ? ` (${source.accountIdentifier})` : ""}
            </span>
          ) : (
            <span className="text-[13px]">—</span>
          )}
        </DetailField>
        <DetailField label="Account" className="col-span-2">
          <span>{transaction.accountIdentifier || "—"}</span>
        </DetailField>
        <DetailField label="Imported">{formatDateTime(transaction.createdAt)}</DetailField>
      </dl>

      {hasMetadata(transaction.metadata) && (
        <DrawerSection title="Metadata">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
            {Object.entries(transaction.metadata || {}).map(([key, value]) => (
              <DetailField key={key} label={humanize(key)}>
                {formatMetadataValue(value)}
              </DetailField>
            ))}
          </dl>
        </DrawerSection>
      )}

      {isUnmatched ? (
        <DrawerSection title={run ? "Unmatched in this reconciliation" : "Reconciliation result"}>
          <UnmatchedNotice run={run} transaction={transaction} />
        </DrawerSection>
      ) : (
        <>
          <DrawerSection title="Reconciliation result">
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2.5">
                <span className="text-sm text-muted-foreground">Confidence</span>
                <ConfidenceIndicator confidence={match?.confidence} />
              </div>
              <EvidenceList
                scoreBreakdown={match?.scoreBreakdown}
                reasons={match?.reasons}
              />
            </div>
          </DrawerSection>

          <DrawerSection title="Matched with">
            {counterpartIds.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Counterpart details are not available for this match yet.
              </p>
            ) : (
              <ul role="list" className="space-y-2">
                {counterpartIds.map((id) => (
                  <CounterpartRow key={id} transactionId={id} />
                ))}
              </ul>
            )}
          </DrawerSection>
        </>
      )}

      <DrawerSection title="AI explanation">
        <AiAnalysis
          label="Explain this transaction"
          analyze={({ signal }) => analyzeTransaction(transaction.id, { signal })}
        />
      </DrawerSection>
    </article>
  );
}

/**
 * Plain-language explanation for a valid unmatched outcome. This is a
 * reconciliation result, not an error: the engine found no counterpart (or
 * none satisfied its criteria) within the run's scoped sources.
 */
function UnmatchedNotice({ run, transaction }) {
  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-dashed border-border bg-muted/30 px-4 py-4">
        <StatusBadge kind="reconciliation" value="UNMATCHED" />
        <p className="mt-2.5 text-sm font-medium text-foreground">
          No corresponding transaction was found.
        </p>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          No matching record was found in the other source(s) for this transaction.
        </p>
      </div>
    </div>
  );
}

function TransactionErrorState({ error, transactionId }) {
  const status = error?.status;
  const code = error?.code;

  let title = "Unable to load transaction";
  let message =
    error?.message ||
    "LedgerLens is having trouble right now. Please try again in a few moments.";

  if (status === 403) {
    title = "Access restricted";
    message =
      "You don't have permission to view this transaction in this workspace. Ask your workspace owner or administrator to grant you access.";
  } else if (status === 404) {
    if (code === "transaction_not_found") {
      title = "Transaction not found";
      message =
        "This transaction doesn't exist, or it may belong to a different workspace.";
    } else {
      title = "Workspace not selected";
      message = "No workspace is selected. Please choose a workspace and try again.";
    }
  } else if (!status || status >= 500) {
    title = "Unable to load transaction";
    message =
      "LedgerLens is having trouble right now. Please try again in a few moments.";
  }

  return (
    <div role="alert" className="px-5 py-8">
      <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-card px-6 py-10 text-center">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <p className="mt-1 max-w-sm text-sm leading-relaxed text-muted-foreground">
          {message}
        </p>
      </div>
    </div>
  );
}

function CounterpartRow({ transactionId }) {
  const [counterpart, setCounterpart] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getTransaction(transactionId, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setCounterpart(data);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, [transactionId]);

  if (failed) {
    return (
      <li className="rounded-lg border border-border px-3 py-2.5 text-sm text-muted-foreground">
        Counterpart details unavailable.
      </li>
    );
  }

  return (
    <li className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2.5">
      {counterpart ? (
        <>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">
              {counterpart.counterparty || counterpart.description || "Transaction"}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatDate(counterpart.transactionDate)}
              {counterpart.reference ? ` · ${counterpart.reference}` : ""}
            </p>
          </div>
          <span className="shrink-0 text-sm font-medium tabular-nums text-foreground">
            {formatMoney(counterpart.amount, counterpart.currency)}
          </span>
        </>
      ) : (
        <div className="flex w-full items-center justify-between gap-3">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 w-16" />
        </div>
      )}
    </li>
  );
}

function hasMetadata(metadata) {
  return Boolean(metadata && Object.keys(metadata).length > 0);
}

function formatMetadataValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return "—";
    }
  }
  return String(value);
}

function DrawerSkeleton() {  return (
    <div aria-busy="true" aria-label="Loading transaction">
      <div className="space-y-2 px-5 py-5">
        <Skeleton className="h-7 w-36" />
        <Skeleton className="h-4 w-56" />
      </div>
      <div className="grid grid-cols-2 gap-4 px-5 pb-6">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="space-y-1.5">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-4 w-24" />
          </div>
        ))}
      </div>
      <div className="border-t border-border px-5 py-4">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="mt-3 h-20 w-full rounded-lg" />
      </div>
    </div>
  );
}
