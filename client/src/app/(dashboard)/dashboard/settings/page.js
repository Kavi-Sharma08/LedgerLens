import { Settings } from "lucide-react";

import { ComingSoon } from "@/components/layout/coming-soon";

export const metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <ComingSoon
      icon={Settings}
      title="Workspace settings are coming soon"
      description="Profile details, workspace members, and role management will be managed from here."
    />
  );
}
