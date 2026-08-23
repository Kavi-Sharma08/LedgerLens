import { redirect } from "next/navigation";

import { auth } from "@/lib/auth";

/**
 * Auth screens are for signed-out users. Anyone with a valid session landing on
 * /login, /signup, or /forgot-password goes straight to the dashboard.
 * Auth.js resolves this server-side — no protected-content flash either way.
 */
export default async function AuthLayout({ children }) {
  const session = await auth();
  if (session?.user) {
    redirect("/dashboard");
  }
  return children;
}
