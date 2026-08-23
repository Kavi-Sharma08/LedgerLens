"use client";

import { useEffect, useState } from "react";

import { healthApi } from "@/lib/api/health";
import { cn } from "@/lib/utils";

const STATES = {
  checking: { label: "Checking API", tone: "bg-muted-foreground/40", animate: true },
  online: { label: "API connected", tone: "bg-success" },
  degraded: { label: "API degraded", tone: "bg-warning" },
  offline: { label: "API offline", tone: "bg-destructive" },
};

/**
 * Development-facing connectivity indicator for the FastAPI backend.
 * Polls /api/health so integration problems surface immediately.
 */
function ApiStatusBadge({ className, intervalMs = 30000 }) {
  const [state, setState] = useState("checking");

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const health = await healthApi.checkHealth();
        if (cancelled) return;
        setState(health?.database === "connected" ? "online" : "degraded");
      } catch {
        if (!cancelled) setState("offline");
      }
    }

    check();
    const timer = setInterval(check, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [intervalMs]);

  const config = STATES[state];

  return (
    <div
      className={cn("flex items-center gap-2 text-xs text-muted-foreground", className)}
      role="status"
      aria-live="polite"
      title={`Backend status: ${config.label}`}
    >
      <span className={cn("size-1.5 rounded-full dot", config.tone, config.animate && "animate-pulse")} />
      {config.label}
    </div>
  );
}

export { ApiStatusBadge };
