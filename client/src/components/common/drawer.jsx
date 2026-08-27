"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Accessible side panel for record detail (transactions, exceptions, matches).
 * - role=dialog + aria-modal, labelled by `label`
 * - Escape closes; backdrop click closes
 * - scroll locked while open; focus moves into the panel and returns on close
 */
export function Drawer({ open, onClose, label, children, widthClass = "max-w-xl" }) {
  const panelRef = useRef(null);
  const previouslyFocused = useRef(null);

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement;

    function onKeyDown(event) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
      previouslyFocused.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="absolute inset-0 bg-navy/40 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        className={cn(
          "absolute inset-y-0 right-0 flex w-full flex-col border-l border-border bg-background shadow-2xl outline-none",
          widthClass
        )}
      >
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
          <span className="text-sm font-semibold text-foreground">{label}</span>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="Close panel"
          >
            <X aria-hidden="true" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

/**
 * Small labelled field row used inside drawers.
 */
export function DetailField({ label, children, className }) {
  return (
    <div className={cn("min-w-0", className)}>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 truncate text-sm text-foreground">{children}</dd>
    </div>
  );
}

/**
 * Section separator used inside drawer bodies.
 */
export function DrawerSection({ title, action, children, className }) {
  return (
    <section className={cn("border-t border-border px-5 py-4", className)}>
      {title && (
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
            {title}
          </h3>
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </section>
  );
}
