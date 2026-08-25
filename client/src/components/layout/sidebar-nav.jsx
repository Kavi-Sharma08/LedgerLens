"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { dashboardNav, dashboardSecondaryNav } from "@/config/site";
import {
  ArrowLeftRight,
  History,
  LayoutDashboard,
  List,
  Plug,
  Settings,
  TriangleAlert,
} from "lucide-react";

import { cn } from "@/lib/utils";

const ICONS = {
  "layout-dashboard": LayoutDashboard,
  "arrow-left-right": ArrowLeftRight,
  list: List,
  "triangle-alert": TriangleAlert,
  plug: Plug,
  history: History,
  settings: Settings,
};

export function SidebarNav({ onNavigate }) {
  const pathname = usePathname();

  function renderItems(items) {
    return items.map((item) => {
      const Icon = ICONS[item.icon];
      const active = item.exact
        ? pathname === item.href
        : pathname.startsWith(item.href);
      return (
        <Link
          key={item.href}
          href={item.href}
          onClick={onNavigate}
          aria-current={active ? "page" : undefined}
          className={cn(
            "flex h-8 items-center gap-2.5 rounded-md px-2.5 text-sm outline-none transition-colors",
            "focus-visible:ring-2 focus-visible:ring-ring/50",
            active
              ? "bg-accent font-medium text-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          )}
        >
          {Icon && <Icon className="size-4 shrink-0" aria-hidden="true" />}
          <span className="truncate">{item.title}</span>
        </Link>
      );
    });
  }

  return (
    <nav aria-label="Dashboard navigation" className="flex flex-col gap-6">
      <div className="space-y-0.5">{renderItems(dashboardNav)}</div>
      <div className="space-y-0.5">
        <p className="px-2.5 pb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground/70">
          Workspace
        </p>
        {renderItems(dashboardSecondaryNav)}
      </div>
    </nav>
  );
}
