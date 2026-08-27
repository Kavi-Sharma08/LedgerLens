"use client";

import { useCallback, useEffect, useState } from "react";
import { LoaderCircle, UserMinus, UserPlus, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DrawerSection } from "@/components/common/drawer";
import { ErrorState } from "@/components/common/error-state";
import { EmptyState } from "@/components/common/empty-state";
import {
  listMembers,
  updateMemberRole,
  removeMember,
} from "@/lib/api/workspaces";
import {
  inviteMember,
  listInvitations,
} from "@/lib/api/invitations";

const ROLE_LABELS = {
  OWNER: { label: "Owner", variant: "primary" },
  ADMIN: { label: "Admin", variant: "info" },
  MEMBER: { label: "Member", variant: "secondary" },
  VIEWER: { label: "Viewer", variant: "outline" },
};

const INVITE_ROLE_OPTIONS = [
  { value: "ADMIN", label: "Admin" },
  { value: "MEMBER", label: "Member" },
  { value: "VIEWER", label: "Viewer" },
];

const ROLE_OPTIONS = ["ADMIN", "MEMBER", "VIEWER"];

function initials(name) {
  if (!name) return "?";
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

function InviteDialog({ workspaceId, open, onOpenChange, onInvited }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("MEMBER");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!email.trim()) return;
    setSending(true);
    setError(null);

    try {
      await inviteMember(workspaceId, { email: email.trim(), role });
      setEmail("");
      setRole("MEMBER");
      onInvited?.();
      onOpenChange(false);
    } catch (err) {
      setError(err?.message || "Failed to send invitation.");
    } finally {
      setSending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Invite member</DialogTitle>
          <DialogDescription>
            Send an email invitation to collaborate in this workspace.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="invite-email">Email address</Label>
            <Input
              id="invite-email"
              type="email"
              placeholder="colleague@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={sending}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="invite-role">Role</Label>
            <Select
              value={role}
              onValueChange={setRole}
              items={INVITE_ROLE_OPTIONS}
              placeholder="Select a role"
            />
          </div>
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={sending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={sending || !email.trim()}>
              {sending ? (
                <>
                  <LoaderCircle className="mr-2 size-4 animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Mail className="mr-2 size-4" />
                  Send invitation
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function WorkspaceMembersSection({ workspaceId, currentUserRole }) {
  const [members, setMembers] = useState([]);
  const [invitations, setInvitations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [acting, setActing] = useState(null);
  const [inviteOpen, setInviteOpen] = useState(false);

  const canInvite = currentUserRole === "OWNER" || currentUserRole === "ADMIN";

  const loadData = useCallback(
    ({ signal, silent = false } = {}) => {
      if (!silent) setLoading(true);
      Promise.all([
        listMembers(workspaceId, { signal }),
        listInvitations(workspaceId, { signal }).catch(() => []),
      ])
        .then(([membersData, invitationsData]) => {
          if (!signal?.aborted) {
            setMembers(membersData);
            setInvitations(
              (invitationsData || []).filter((inv) => inv.status === "PENDING")
            );
            setError(null);
          }
        })
        .catch((err) => {
          if (!signal?.aborted && err?.name !== "AbortError") {
            setError(err?.message || "Failed to load members.");
          }
        })
        .finally(() => {
          if (!signal?.aborted) setLoading(false);
        });
    },
    [workspaceId]
  );

  useEffect(() => {
    const controller = new AbortController();
    listMembers(workspaceId, { signal: controller.signal })
      .then((membersData) => {
        if (!controller.signal.aborted) {
          setMembers(membersData);
          setError(null);
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted && err?.name !== "AbortError") {
          setError(err?.message || "Failed to load members.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [workspaceId]);

  async function handleChangeRole(userId, newRole) {
    setActing(userId);
    try {
      await updateMemberRole(workspaceId, userId, newRole);
      loadData();
    } catch (err) {
      setError(err?.message || "Failed to update role.");
    } finally {
      setActing(null);
    }
  }

  async function handleRemove(userId) {
    setActing(userId);
    try {
      await removeMember(workspaceId, userId);
      loadData();
    } catch (err) {
      setError(err?.message || "Failed to remove member.");
    } finally {
      setActing(null);
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <DrawerSection
        title="Members"
        action={
          canInvite ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setInviteOpen(true)}
            >
              <UserPlus className="mr-1.5 size-4" />
              Invite member
            </Button>
          ) : undefined
        }
      >
        {error && !loading && (
          <ErrorState
            title="Unable to load members"
            message={error}
            className="border-0 py-4"
          />
        )}
        {loading && members.length === 0 && (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
            Loading members...
          </div>
        )}
        {!loading && members.length === 0 && invitations.length === 0 && !error && (
          <EmptyState
            title="No members"
            description="No members found for this workspace."
            className="py-4"
          />
        )}
        {(members.length > 0 || invitations.length > 0) && (
          <ul role="list" className="divide-y divide-border">
            {members.map((member) => {
              const roleInfo = ROLE_LABELS[member.role] || ROLE_LABELS.MEMBER;
              const isOwner = member.role === "OWNER";
              return (
                <li
                  key={member.id}
                  className="flex items-center justify-between gap-4 py-3"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-medium text-muted-foreground">
                      {initials(member.userName)}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {member.userName || "Unknown"}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {member.userEmail || "\u2014"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant={roleInfo.variant}>{roleInfo.label}</Badge>
                    {!isOwner && (
                      <DropdownMenu>
                        <DropdownMenuTrigger
                          className="flex size-8 items-center justify-center rounded-md text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
                          aria-label={`Actions for ${member.userName || "member"}`}
                          disabled={acting === member.id}
                        >
                          {acting === member.id ? (
                            <LoaderCircle className="size-4 animate-spin" />
                          ) : (
                            <svg
                              viewBox="0 0 16 16"
                              fill="currentColor"
                              className="size-4"
                            >
                              <circle cx="8" cy="3" r="1.5" />
                              <circle cx="8" cy="8" r="1.5" />
                              <circle cx="8" cy="13" r="1.5" />
                            </svg>
                          )}
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-44">
                          {ROLE_OPTIONS.filter((r) => r !== member.role).map(
                            (role) => (
                              <DropdownMenuItem
                                key={role}
                                onClick={() =>
                                  handleChangeRole(member.userId, role)
                                }
                              >
                                Change to {ROLE_LABELS[role]?.label || role}
                              </DropdownMenuItem>
                            )
                          )}
                          <DropdownMenuItem
                            variant="destructive"
                            onClick={() => handleRemove(member.userId)}
                          >
                            <UserMinus className="size-4" aria-hidden="true" />
                            Remove from workspace
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                </li>
              );
            })}
            {invitations.map((inv) => (
              <li
                key={inv.id}
                className="flex items-center justify-between gap-4 py-3"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-medium text-muted-foreground">
                    {initials(inv.email)}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {inv.email}
                    </p>
                    <p className="text-xs text-muted-foreground truncate">
                      Invited {inv.invitedBy ? `by ${inv.invitedBy}` : ""}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Badge variant="outline">
                    {ROLE_LABELS[inv.role]?.label || inv.role}
                  </Badge>
                  <Badge variant="warning">Pending</Badge>
                </div>
              </li>
            ))}
          </ul>
        )}
      </DrawerSection>

      <InviteDialog
        workspaceId={workspaceId}
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        onInvited={() => loadData({ silent: true })}
      />
    </div>
  );
}
