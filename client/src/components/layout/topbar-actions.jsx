"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";
import {
  Building2,
  Check,
  ChevronsUpDown,
  LogOut,
  Plus,
  LoaderCircle,
} from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
 * Workspace switcher + user menu for the top bar.
 * Fetches all workspaces the user belongs to and allows switching.
 */
export function TopbarActions({ user, workspace, allWorkspaces: initialWorkspaces }) {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState(initialWorkspaces || []);
  const [loading, setLoading] = useState(!initialWorkspaces || initialWorkspaces.length === 0);
  const [switchError, setSwitchError] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [switching, setSwitching] = useState(null);

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
      setSwitchError(null);
      setSwitching(ws.id);
      try {
        const res = await fetch("/api/workspace/activate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspaceId: ws.id }),
        });

        if (!res.ok) {
          setSwitchError("You don't have access to that workspace.");
          setSwitching(null);
          return;
        }

        // Full reload: the server layout re-reads the new cookie and every
        // data view remounts against the activated workspace.
        window.location.replace("/dashboard");
      } catch {
        setSwitchError("Failed to switch workspace. Please try again.");
        setSwitching(null);
      }
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
                  disabled={switching !== null}
                  className={ws.id === workspace?.id ? "bg-muted/50" : ""}
                >
                  {switching === ws.id ? (
                    <LoaderCircle className="size-4 animate-spin text-muted-foreground" aria-hidden="true" />
                  ) : (
                    <Building2 className="size-4 text-primary" aria-hidden="true" />
                  )}
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
            {switchError && (
              <p className="px-2 py-1.5 text-xs text-destructive">{switchError}</p>
            )}
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" aria-hidden="true" />
            Create workspace
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Create workspace dialog */}
      <CreateWorkspaceDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(newWorkspace) => {
          setWorkspaces((prev) => [...prev, newWorkspace]);
          // The create route set the active-workspace cookie. Full reload so
          // the server layout renders with the new workspace active.
          window.location.replace("/dashboard");
        }}
      />

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

function CreateWorkspaceDialog({ open, onOpenChange, onCreated }) {
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;

    setCreating(true);
    setError(null);

    try {
      const res = await fetch("/api/workspace/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed }),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        throw new Error(data?.detail || "Couldn't create workspace. Try again.");
      }

      setName("");
      onOpenChange(false);
      onCreated?.(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create workspace</DialogTitle>
            <DialogDescription>
              Create a new workspace to organize your financial records.
            </DialogDescription>
          </DialogHeader>

          <div className="mt-4 space-y-2">
            <Label htmlFor="new-workspace-name">Workspace name</Label>
            <Input
              id="new-workspace-name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setError(null);
              }}
              placeholder="e.g. Company Finance"
              autoFocus
              required
              maxLength={120}
            />
            {error && (
              <p role="alert" className="text-xs text-destructive">{error}</p>
            )}
          </div>

          <DialogFooter className="mt-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={creating}>
              Cancel
            </Button>
            <Button type="submit" disabled={!name.trim() || creating}>
              {creating ? (
                <>
                  <LoaderCircle className="animate-spin" aria-hidden="true" />
                  Creating...
                </>
              ) : (
                "Create workspace"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
