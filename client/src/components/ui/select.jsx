"use client";

import { Select as SelectPrimitive } from "@base-ui/react/select";
import { Check, ChevronsUpDown } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Thin styled wrapper around Base UI's accessible Select.
 * items: [{ value: string, label: string }]
 * Fully controlled: `value` + `onValueChange`. The trigger renders the
 * matching item's label itself so no internal value-rendering is assumed.
 */
function Select({ value, onValueChange, items, className, triggerClassName, placeholder }) {
  const selected = items.find((item) => item.value === value);

  return (
    <SelectPrimitive.Root
      value={value || null}
      onValueChange={(next) => onValueChange(next ?? "")}
    >
      <SelectPrimitive.Trigger
        aria-label={placeholder}
        data-slot="select-trigger"
        className={cn(
          "flex h-8 w-full items-center justify-between gap-1.5 rounded-lg border border-input bg-card px-2.5 text-sm whitespace-nowrap outline-none transition-colors",
          "hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-expanded:bg-muted",
          "data-placeholder-disabled:text-muted-foreground disabled:pointer-events-none disabled:opacity-50",
          triggerClassName
        )}
      >
        <span className={cn("truncate", !selected && "text-muted-foreground")}>
          {selected ? selected.label : placeholder}
        </span>
        <SelectPrimitive.Icon>
          <ChevronsUpDown className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>

      <SelectPrimitive.Portal>
        <SelectPrimitive.Positioner align="start" sideOffset={6} className="outline-none z-50">
          <SelectPrimitive.Popup
            data-slot="select-content"
            className="max-h-(--available-height) min-w-[var(--anchor-width)] origin-(--transform-origin) overflow-y-auto overflow-x-hidden rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-lg transition data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95"
          >
            <SelectPrimitive.List>
              {items.map((item) => (
                <SelectPrimitive.Item
                  key={item.value}
                  value={item.value || null}
                  data-slot="select-item"
                  className={cn(
                    "relative flex cursor-pointer items-center gap-2 rounded-md py-1.5 pr-7 pl-2.5 text-sm outline-none select-none",
                    "focus:bg-muted focus:text-foreground data-highlighted:bg-muted data-highlighted:text-foreground",
                    item.value === value && "font-medium"
                  )}
                >
                  <SelectPrimitive.ItemText>{item.label}</SelectPrimitive.ItemText>
                  <SelectPrimitive.ItemIndicator className="absolute right-2 flex items-center">
                    <Check className="size-3.5 text-primary" aria-hidden="true" />
                  </SelectPrimitive.ItemIndicator>
                </SelectPrimitive.Item>
              ))}
            </SelectPrimitive.List>
          </SelectPrimitive.Popup>
        </SelectPrimitive.Positioner>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

export { Select };
