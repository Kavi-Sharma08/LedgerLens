import Link from "next/link";

import { AuthShell } from "@/components/auth/auth-shell";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";

export const metadata = { title: "Reset your password" };

export default function ForgotPasswordPage() {
  return (
    <AuthShell
      title="Reset your password"
      subtitle="Enter the email you use for LedgerLens and we'll send you instructions to set a new password."
      footer={
        <>
          Remembered it?{" "}
          <Link
            href="/login"
            className="font-medium text-primary underline-offset-4 hover:underline outline-none focus-visible:ring-2 focus-visible:ring-ring/50 rounded-sm"
          >
            Back to sign in
          </Link>
        </>
      }
      panel={{
        headline: "Reconcile. Investigate. Resolve.",
        text: "Bring your financial records together and review reconciliation exceptions with clear evidence.",
        points: [
          "Automated reconciliation",
          "Exception investigation",
          "Human review",
        ],
      }}
    >
      <ForgotPasswordForm />
    </AuthShell>
  );
}
