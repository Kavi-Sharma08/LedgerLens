"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { Drawer, DetailField, DrawerSection } from "@/components/common/drawer";
import { ConfidenceIndicator } from "@/components/domain/confidence-indicator";
import { EvidenceList } from "@/components/domain/evidence-list";
import { StatusBadge, exceptionReasonLabel } from "@/components/domain/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMoney, formatDate, formatDateTime } from "@/lib/format";
import {
  getTransaction,
  listTransactionMatches,
} from "@/lib/api/transactions";

/**
 * Transaction detail side panel.
 * Everything shown comes from the backend: the canonical transaction plus the
 * match documents the engine persisted for it (score breakdown, reasons,
 * matched fields). When no match exists we say so plainly — the frontend
 * never guesses why a record didn't match beyond reporting stored reasons.
 */
export function TransactionDrawer({ transactionId, onClose }) {
  const [loaded, setLoaded] = useState(null); // { id, transaction, matches }
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!transactionId) return;
    const controller = new AbortController();

    Promise.all([
      getTransaction(transactionId, { signal: controller.signal }),
      listTransactionMatches(transactionId, { signal: controller.signal }).catch(() => null),
    ])
      .then(([txn, matchPage]) => {
        if (controller.signal.aborted) return;
        setLoaded({ id: transactionId, transaction: txn, matches: matchPage ? matchPage.items : [] });
        setError(null);
      })
      .catch((err) => {
        if (err?.name === "AbortError" || controller.signal.aborted) return;
        setError(err?.message || "Unable to load this transaction.");
      });

    return () => controller.abort();
  }, [transactionId]);

  return (
    <Drawer open={Boolean(transactionId)} onClose={onClose} label="Transaction details">
      <TransactionDetail
        transactionId={transactionId}
        loaded={loaded}
        error={error}
      />
    </Drawer>
  );
}

export function TransactionDetail({ transactionId, loaded, error }) {
  if (error && loaded?.id !== transactionId) {
    return (
      <p role="alert" className="px-5 py-8 text-sm text-destructive">
        {error}
      </p>
    );
  }
  if (!loaded || loaded.id !== transactionId || !loaded.transaction) {
    return <DrawerSkeleton />;
  }

  const { transaction, matches } = loaded;

  const match = matches?.[0] ?? null;
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
          <StatusBadge kind="reconciliation" value={match?.status ?? "UNMATCHED"} />
        </div>
        <p className="mt-1 truncate text-sm text-muted-foreground">
          {transaction.counterparty || transaction.description || "No counterparty recorded"}
        </p>
      </header>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-4 px-5 pb-5">
        <DetailField label="Date">{formatDate(transaction.transactionDate)}</DetailField>
        <DetailField label="Direction">{humanize(transaction.direction)}</DetailField>
        <DetailField label="Currency">{transaction.currency}</DetailField>
        <DetailField label="Type">{humanize(transaction.transactionType)}</DetailField>
        <DetailField label="Reference" className="col-span-2">
          <span className="font-mono text-[13px]">{transaction.reference || "—"}</span>
        </DetailField>
        <DetailField label="Description" className="col-span-2">
          {transaction.description || "—"}
        </DetailField>
        <DetailField label="Record status">{humanize(transaction.status)}</DetailField>
        <DetailField label="Imported">{formatDateTime(transaction.createdAt)}</DetailField>
        {transaction.sourceRecordId && (
          <DetailField label="Source reference" className="col-span-2">
            <span className="font-mono text-[13px]">{transaction.sourceRecordId}</span>
          </DetailField>
        )}
      </dl>

      <DrawerSection title="Reconciliation result">
        {!match ? (
          <NoMatchNotice />
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2.5">
              <span className="text-sm text-muted-foreground">Confidence</span>
              <ConfidenceIndicator confidence={match.confidence} />
            </div>
            <EvidenceList
              scoreBreakdown={match.scoreBreakdown}
              reasons={match.reasons}
            />
          </div>
        )}
      </DrawerSection>

      {match && (
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
      )}
    </article>
  );
}

function NoMatchNotice() {
  return (
    <div className="rounded-lg border border-dashed border-border bg-muted/30 px-4 py-4">
      <StatusBadge kind="reconciliation" value="UNMATCHED" />
      <p className="mt-2.5 text-sm font-medium text-foreground">No confident match found.</p>
      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
        No transaction from another source fell within matching tolerance for this
        record during a reconciliation run. Run a reconciliation after importing more
        data, or check the exceptions workspace if this record was flagged there.
      </p>
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

function DrawerSkeleton() {
  return (
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
