"use client";

import { createContext, useContext } from "react";
import { Menu as MenuPrimitive } from "@base-ui/react/menu";

import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";

/**
 * React context that tracks whether a DropdownMenuGroup is mounted.
 * DropdownMenuLabel uses this to fall back to a plain element if
 * the Base UI MenuGroup context isn't available (e.g. portal timing).
 */
const MenuGroupCtx = createContext(false);

const DropdownMenu = MenuPrimitive.Root;
const DropdownMenuTrigger = MenuPrimitive.Trigger;

function DropdownMenuContent({
  className,
  align = "start",
  sideOffset = 6,
  ...props
}) {
  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Positioner align={align} sideOffset={sideOffset} className="outline-none">
        <MenuPrimitive.Popup
          data-slot="dropdown-menu-content"
          className={cn(
            "z-50 min-w-[10rem] origin-(--transform-origin) overflow-hidden rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-lg",
            "transition data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
            className
          )}
          {...props}
        />
      </MenuPrimitive.Positioner>
    </MenuPrimitive.Portal>
  );
}

function DropdownMenuItem({ className, variant = "default", ...props }) {
  return (
    <MenuPrimitive.Item
      data-slot="dropdown-menu-item"
      className={cn(
        "relative flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none select-none",
        "focus:bg-muted focus:text-foreground data-disabled:pointer-events-none data-disabled:opacity-50",
        "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        variant === "destructive" &&
          "text-destructive focus:bg-destructive/10 focus:text-destructive",
        className
      )}
      {...props}
    />
  );
}

/**
 * Group label with a defensive fallback. If the Base UI MenuGroup context
 * is missing (portal timing, mismatched versions), render a plain div
 * instead of throwing.
 */
function DropdownMenuLabel({ className, ...props }) {
  const inGroup = useContext(MenuGroupCtx);

  if (!inGroup) {
    return (
      <div
        data-slot="dropdown-menu-label"
        className={cn("px-2 py-1.5 text-xs font-medium text-muted-foreground", className)}
        {...props}
      />
    );
  }

  return (
    <MenuPrimitive.GroupLabel
      data-slot="dropdown-menu-label"
      className={cn("px-2 py-1.5 text-xs font-medium text-muted-foreground", className)}
      {...props}
    />
  );
}

function DropdownMenuGroup({ children, ...props }) {
  return (
    <MenuGroupCtx.Provider value={true}>
      <MenuPrimitive.Group data-slot="dropdown-menu-group" {...props}>
        {children}
      </MenuPrimitive.Group>
    </MenuGroupCtx.Provider>
  );
}

function DropdownMenuSeparator({ className, ...props }) {
  return (
    <Separator
      orientation="horizontal"
      className={cn("-mx-1 my-1 bg-border", className)}
      {...props}
    />
  );
}

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuGroup,
  DropdownMenuSeparator,
};
