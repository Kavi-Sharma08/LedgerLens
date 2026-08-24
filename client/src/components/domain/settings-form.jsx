"use client";

import { signOut } from "next-auth/react";

import { Button } from "@/components/ui/button";

/**
 * Session actions for the settings page. Sign-out goes through Auth.js and
 * lands back on the login screen.
 */
export function SettingsForm() {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-border bg-card px-5 py-4">
      <div>
        <p className="text-sm font-medium text-foreground">Sign out</p>
        <p className="mt-0.5 text-sm text-muted-foreground">
          End your session on this device.
        </p>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={() => signOut({ redirectTo: "/login" })}
      >
        Sign out
      </Button>
    </div>
  );
}
