"use client";

import { createContext, useCallback, useContext, useState } from "react";

const AiContext = createContext({
  aiContext: {
    reconciliationRunId: null,
    transactionId: null,
    matchId: null,
    exceptionId: null,
    entityType: "WORKSPACE",
    activeRunSummary: null,
  },
  copilotOpen: false,
  setCopilotOpen: () => {},
  setReconciliationContext: () => {},
  setTransactionContext: () => {},
  setMatchContext: () => {},
  setExceptionContext: () => {},
  clearEntityContext: () => {},
  navigationTarget: null,
  setNavigationTarget: () => {},
});

export function AiContextProvider({ children }) {
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [navigationTarget, setNavigationTarget] = useState(null);
  const [aiContext, setAiContextState] = useState({
    reconciliationRunId: null,
    transactionId: null,
    matchId: null,
    exceptionId: null,
    entityType: "WORKSPACE",
    activeRunSummary: null,
  });

  const setReconciliationContext = useCallback((runId, summary = null) => {
    setAiContextState({
      reconciliationRunId: runId || null,
      transactionId: null,
      matchId: null,
      exceptionId: null,
      entityType: "RECONCILIATION",
      activeRunSummary: summary,
    });
  }, []);

  const setTransactionContext = useCallback((txnId, runId = null) => {
    setAiContextState((prev) => ({
      ...prev,
      transactionId: txnId || null,
      reconciliationRunId: runId || prev.reconciliationRunId,
      entityType: "TRANSACTION",
    }));
  }, []);

  const setMatchContext = useCallback((matchId, runId = null) => {
    setAiContextState((prev) => ({
      ...prev,
      matchId: matchId || null,
      reconciliationRunId: runId || prev.reconciliationRunId,
      entityType: "MATCH",
    }));
  }, []);

  const setExceptionContext = useCallback((exceptionId, runId = null) => {
    setAiContextState((prev) => ({
      ...prev,
      exceptionId: exceptionId || null,
      reconciliationRunId: runId || prev.reconciliationRunId,
      entityType: "EXCEPTION",
    }));
  }, []);

  const clearEntityContext = useCallback(() => {
    setAiContextState((prev) => ({
      ...prev,
      transactionId: null,
      matchId: null,
      exceptionId: null,
      entityType: prev.reconciliationRunId ? "RECONCILIATION" : "WORKSPACE",
    }));
  }, []);

  return (
    <AiContext.Provider
      value={{
        aiContext,
        copilotOpen,
        setCopilotOpen,
        setReconciliationContext,
        setTransactionContext,
        setMatchContext,
        setExceptionContext,
        clearEntityContext,
        navigationTarget,
        setNavigationTarget,
      }}
    >
      {children}
    </AiContext.Provider>
  );
}

export function useAiContext() {
  return useContext(AiContext);
}
