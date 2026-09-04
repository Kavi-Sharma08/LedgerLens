"use client";

import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Drawer, DetailField, DrawerSection } from "@/components/common/drawer";
import { ConfidenceIndicator } from "@/components/domain/confidence-indicator";
import { EvidenceList } from "@/components/domain/evidence-list";
import { StatusBadge, humanize } from "@/components/domain/status-badge";
import { TransactionDrawer } from "@/components/domain/transaction-drawer";
import { AiAnalysis } from "@/components/domain/ai-analysis";
import { useDashboard } from "@/components/common/dashboard-context";
import { useAiContext } from "@/components/common/ai-context";
import { getTransaction } from "@/lib/api/transactions";
import { approveMatch, rejectMatch } from "@/lib/api/reconciliations";
import { analyzeMatch } from "@/lib/api/ai";
import { formatDate, formatMoney } from "@/lib/format";

/**
 * Match detail side panel (Reconciliation -> Matched / Needs review).
 *
 * The match object itself comes from the run's persisted results — the UI
 * never re-derives a decision. The two (or more) sides of the match are each
 * fetched by id from the workspace-scoped transaction endpoint, so the panel
 * always shows authoritative records. Approve/Reject call the existing match
 * endpoints and are gated by the member's capabilities.
 */
export function MatchDrawer({ match, runId, onClose, onDecision }) {
  return (
    <Drawer open={Boolean(match)} onClose={onClose} label="Match details" widthClass="max-w-2xl">
      {match && (
        <MatchDetail match={match} runId={runId} onDecision={onDecision} />
      )}
    </Drawer>
  );
}

function MatchDetail({ match, runId, onDecision }) {
  const { can } = useDashboard();
  const { setMatchContext, clearEntityContext } = useAiContext();
  const [acting, setActing] = useState(null);
  const [openTransactionId, setOpenTransactionId] = useState(null);
  // Local echo of the decision so the panel reflects it immediately while the
  // parent refreshes the list from the backend.
  const [decidedAction, setDecidedAction] = useState(null);

  useEffect(() => {
    if (match?.id) {
      setMatchContext(match.id, runId);
    }
    return () => {
      clearEntityContext();
    };
  }, [match?.id, runId, setMatchContext, clearEntityContext]);


  const canApprove = Boolean(can.approveMatches);
  const canReject = Boolean(can.rejectMatches);
  const isDecided = decidedAction || Boolean(match.humanDecision);

  async function handleDecision(action) {
    setActing(action);
    try {
      if (action === "APPROVE") {
        await approveMatch(runId, match.id);
      } else {
        await rejectMatch(runId, match.id);
      }
      setDecidedAction(action === "APPROVE" ? "APPROVED" : "REJECTED");
      await onDecision?.();
    } catch {
      // Errors are surfaced by keeping the previous state (no-op).
    } finally {
      setActing(null);
    }
  }

  return (
    <article className="divide-y divide-border">
      <header className="px-5 py-5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="primary">{humanize(match.matchType)}</Badge>
            <StatusBadge kind="reconciliation" value={match.status} />
            {isDecided && (
              <Badge
                variant={isDecided === "APPROVED" ? "success" : "destructive"}
                className="text-xs"
              >
                {isDecided === "APPROVED" ? "Approved" : "Rejected"}
              </Badge>
            )}
          </div>
          <ConfidenceIndicator confidence={match.confidence} />
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          The engine grouped {match.transactionIds?.length ?? 1} record
          {(match.transactionIds?.length ?? 1) === 1 ? "" : "s"} into this match.
        </p>
        {match.mismatchedFields?.length > 0 && (
          <p className="mt-1 text-xs text-muted-foreground">
            Differing fields: {match.mismatchedFields.map(humanize).join(", ")}
          </p>
        )}
      </header>

      {match.transactionIds?.length > 0 && (
        <DrawerSection title={`Match sides (${match.transactionIds.length})`}>
          <ul role="list" className="space-y-3">
            {match.transactionIds.map((id, index) => (
              <MatchSide
                key={id}
                index={index}
                transactionId={id}
                onClick={() => setOpenTransactionId(id)}
              />
            ))}
          </ul>
        </DrawerSection>
      )}

      <DrawerSection title="Confidence & evidence">
        <div className="mb-3 flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2.5">
          <span className="text-sm text-muted-foreground">Confidence</span>
          <ConfidenceIndicator confidence={match.confidence} />
        </div>
        <EvidenceList scoreBreakdown={match.scoreBreakdown} reasons={match.reasons} />
      </DrawerSection>

      <DrawerSection title="AI explanation">
        <AiAnalysis
          label="Explain this match"
          analyze={({ signal }) => analyzeMatch(match.id, { signal })}
        />
      </DrawerSection>

      {(canApprove || canReject) && !isDecided && (
        <DrawerSection title="Decision">
          <p className="mb-3 text-sm text-muted-foreground">
            Confirm the engine&rsquo;s match, or reject it if it&rsquo;s a false positive.
          </p>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              className="text-success hover:text-success"
              disabled={acting !== null}
              onClick={() => handleDecision("APPROVE")}
            >
              {acting === "APPROVE" ? (
                "Saving..."
              ) : (
                <>
                  <Check aria-hidden="true" />
                  Approve
                </>
              )}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="text-destructive hover:text-destructive"
              disabled={acting !== null}
              onClick={() => handleDecision("REJECT")}
            >
              {acting === "REJECT" ? (
                "Saving..."
              ) : (
                <>
                  <X aria-hidden="true" />
                  Reject
                </>
              )}
            </Button>
          </div>
        </DrawerSection>
      )}

      <TransactionDrawer
        transactionId={openTransactionId}
        onClose={() => setOpenTransactionId(null)}
      />
    </article>
  );
}

function MatchSide({ index, transactionId, onClick }) {
  const [txn, setTxn] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getTransaction(transactionId, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setTxn(data);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, [transactionId]);

  return (
    <li className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between gap-3 px-3 py-1.5">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Side {index + 1}
        </span>
        <button
          type="button"
          onClick={onClick}
          className="text-xs font-medium text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 rounded-sm"
        >
          Open full record
        </button>
      </div>
      {failed ? (
        <p className="px-3 pb-3 text-sm text-muted-foreground">
          Record details unavailable.
        </p>
      ) : txn ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 px-3 pb-3">
          <DetailField label="Amount">
            <span className="tabular-nums">{formatMoney(txn.amount, txn.currency)}</span>
          </DetailField>
          <DetailField label="Date">{formatDate(txn.transactionDate)}</DetailField>
          <DetailField label="Counterparty">{txn.counterparty || "—"}</DetailField>
          <DetailField label="Direction">{humanize(txn.direction)}</DetailField>
          <DetailField label="Reference" className="col-span-2">
            <span className="text-xs">{txn.reference || "—"}</span>
          </DetailField>
          <DetailField label="Description" className="col-span-2">
            {txn.description || "—"}
          </DetailField>
        </dl>
      ) : (
        <div className="space-y-2 px-3 pb-3">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 w-32" />
        </div>
      )}
    </li>
  );
}
