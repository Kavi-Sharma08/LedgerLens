"use client";

import { useRef } from "react";

import { cn } from "@/lib/utils";

/**
 * Minimal accessible tab strip (roving tabindex, arrow keys).
 * Controlled: value + onValueChange; panels are rendered by the caller.
 */
export function Tabs({ value, onValueChange, items, className, ariaLabel }) {
  const listRef = useRef(null);

  function onKeyDown(event) {
    const index = items.findIndex((item) => item.value === value);
    let next = null;
    if (event.key === "ArrowRight") next = items[(index + 1) % items.length];
    if (event.key === "ArrowLeft") next = items[(index - 1 + items.length) % items.length];
    if (event.key === "Home") next = items[0];
    if (event.key === "End") next = items[items.length - 1];
    if (next) {
      event.preventDefault();
      onValueChange(next.value);
      listRef.current
        ?.querySelector(`#tab-${next.value}`)
        ?.focus();
    }
  }

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={ariaLabel}
      onKeyDown={onKeyDown}
      className={cn("flex gap-1 overflow-x-auto border-b border-border", className)}
    >
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            id={`tab-${item.value}`}
            role="tab"
            type="button"
            aria-selected={active}
            aria-controls={`panel-${item.value}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onValueChange(item.value)}
            className={cn(
              "-mb-px shrink-0 whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium outline-none transition-colors",
              "focus-visible:ring-2 focus-visible:ring-ring/50 rounded-t-sm",
              active
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
            )}
          >
            {item.label}
            {typeof item.count === "number" && (
              <span
                className={cn(
                  "ml-1.5 inline-block min-w-5 rounded-full px-1.5 py-0.5 text-center text-[11px] font-semibold tabular-nums",
                  active ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                )}
              >
                {item.count.toLocaleString("en-IN")}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export function TabPanel({ value, active, children, className }) {
  if (!active) return null;
  return (
    <div
      role="tabpanel"
      id={`panel-${value}`}
      aria-labelledby={`tab-${value}`}
      tabIndex={0}
      className={cn("outline-none", className)}
    >
      {children}
    </div>
  );
}
