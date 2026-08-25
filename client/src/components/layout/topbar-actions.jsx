"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";
import { Building2, Check, ChevronsUpDown, LogOut, Plus } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { listWorkspaces } from "@/lib/api/workspaces";

function initials(name) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

/**
 * Set the active workspace cookie so the proxy sends X-LL-Workspace-Id.
 * The cookie is HttpOnly=false so the browser can read it, but the backend
 * still verifies membership — the cookie is not authorization.
 */
function setActiveWorkspaceCookie(workspaceId) {
  document.cookie = `ll-active-workspace=${workspaceId}; path=/; max-age=31536000; SameSite=Lax`;
}

/**
 * Workspace switcher + user menu for the top bar.
 * Fetches all workspaces the user belongs to and allows switching.
 */
export function TopbarActions({ user, workspace, allWorkspaces: initialWorkspaces }) {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState(initialWorkspaces || []);
  const [loading, setLoading] = useState(!initialWorkspaces || initialWorkspaces.length === 0);

  // Fetch workspaces on mount if not provided
  useEffect(() => {
    if (initialWorkspaces && initialWorkspaces.length > 0) return;
    const controller = new AbortController();
    listWorkspaces({ signal: controller.signal })
      .then((ws) => {
        if (!controller.signal.aborted) setWorkspaces(ws);
      })
      .catch(() => {})
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [initialWorkspaces]);

  const switchWorkspace = useCallback(
    async (ws) => {
      if (ws.id === workspace?.id) return;
      try {
        await fetch("/api/workspace/activate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspaceId: ws.id }),
        });
      } catch {
        // Cookie set failed — fall back to client-side for resilience.
        document.cookie = `ll-active-workspace=${ws.id}; path=/; max-age=31536000; SameSite=Lax`;
      }
      window.location.reload();
    },
    [workspace?.id]
  );

  return (
    <div className="flex items-center gap-1.5">
      {/* Workspace switcher */}
      <DropdownMenu>
        <DropdownMenuTrigger
          className="flex h-8 items-center gap-2 rounded-md border border-border bg-card px-2.5 text-sm font-medium outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 aria-expanded:bg-muted"
          aria-label={`Workspace: ${workspace?.name ?? "None"}. Open switcher`}
        >
          <Building2 className="size-4 text-primary" aria-hidden="true" />
          <span className="max-w-36 truncate">{workspace?.name ?? "No workspace"}</span>
          <ChevronsUpDown className="size-3.5 text-muted-foreground" aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-64">
          <DropdownMenuGroup>
            <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
            {workspaces.length > 0 ? (
              workspaces.map((ws) => (
                <DropdownMenuItem
                  key={ws.id}
                  onClick={() => switchWorkspace(ws)}
                  className={ws.id === workspace?.id ? "bg-muted/50" : ""}
                >
                  <Building2 className="size-4 text-primary" aria-hidden="true" />
                  <span className="flex-1 truncate">{ws.name}</span>
                  {ws.id === workspace?.id && (
                    <Check className="size-4 text-success" aria-hidden="true" />
                  )}
                </DropdownMenuItem>
              ))
            ) : loading ? (
              <DropdownMenuItem disabled>Loading...</DropdownMenuItem>
            ) : (
              <DropdownMenuItem disabled>No workspaces yet</DropdownMenuItem>
            )}
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => router.push("/dashboard/settings")}>
            <Plus className="size-4" aria-hidden="true" />
            Create workspace
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

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
          <DropdownMenuGroup>
            <DropdownMenuLabel className="normal-case">
              <span className="block truncate text-sm font-medium text-foreground">{user?.name}</span>
              <span className="block truncate text-xs font-normal">{user?.email}</span>
            </DropdownMenuLabel>
          </DropdownMenuGroup>
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
