"use client";

import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";
import { Building2, ChevronsUpDown, LogOut } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function initials(name) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

/**
 * Workspace switcher + user menu for the top bar.
 * Day 1: single workspace; the dropdown structure is ready for more.
 */
export function TopbarActions({ user, workspace }) {
  const router = useRouter();
  return (
    <div className="flex items-center gap-1.5">
      {/* Workspace switcher — visual placeholder until multi-workspace lands */}
      <DropdownMenu>
        <DropdownMenuTrigger
          className="flex h-8 items-center gap-2 rounded-md border border-border bg-card px-2.5 text-sm font-medium outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 aria-expanded:bg-muted"
          aria-label={`Workspace: ${workspace?.name ?? "None"}. Open switcher`}
        >
          <Building2 className="size-4 text-primary" aria-hidden="true" />
          <span className="max-w-36 truncate">{workspace?.name ?? "No workspace"}</span>
          <ChevronsUpDown className="size-3.5 text-muted-foreground" aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-60">
          <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
          {workspace ? (
            <DropdownMenuItem className="pointer-events-none" data-disabled>
              <Building2 className="size-4 text-primary" aria-hidden="true" />
              <span className="flex-1 truncate">{workspace.name}</span>
              <Badge variant="primary" className="ml-auto">Active</Badge>
            </DropdownMenuItem>
          ) : (
            <DropdownMenuItem disabled>No workspaces yet</DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Notifications placeholder */}
      <button
        type="button"
        aria-label="Notifications (no unread items)"
        title="Notifications arrive in a later phase"
        className="relative flex size-8 items-center justify-center rounded-md outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 text-muted-foreground hover:text-foreground"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="size-4"
          aria-hidden="true"
        >
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        <span aria-hidden="true" className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-warning" />
      </button>

      {/* User menu */}
      <DropdownMenu>
        <DropdownMenuTrigger
          className="flex h-8 items-center gap-2 rounded-full pr-2 pl-0.5 outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50"
          aria-label="Open account menu"
        >
          <Avatar size="sm">
            {user?.avatar && <AvatarImage src={user.avatar} alt="" />}
            <AvatarFallback>{initials(user?.name || "U")}</AvatarFallback>
          </Avatar>
          <span className="hidden max-w-28 truncate text-sm sm:block">{user?.name}</span>
          <ChevronsUpDown className="hidden size-3.5 text-muted-foreground sm:block" aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel className="normal-case">
            <span className="block truncate text-sm font-medium text-foreground">{user?.name}</span>
            <span className="block truncate text-xs font-normal">{user?.email}</span>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => router.push("/dashboard/settings")}>
            Settings
          </DropdownMenuItem>
          <DropdownMenuItem
            variant="destructive"
            onClick={() => signOut({ redirectTo: "/login" })}
          >
            <LogOut aria-hidden="true" />
            Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
