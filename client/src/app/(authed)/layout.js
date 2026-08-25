import { redirect } from "next/navigation";

import { auth } from "@/lib/auth";

/**
 * Minimal authenticated layout for pages that don't need a workspace
 * (e.g. onboarding). Checks auth but does NOT require an active workspace.
 */
export default async function AuthedLayout({ children }) {
  const session = await auth();
  if (!session?.user?.id) {
    redirect("/login");
  }
  return children;
}
