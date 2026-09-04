import { Suspense } from "react";
import Link from "next/link";

import { AuthShell } from "@/components/auth/auth-shell";
import { LoginForm } from "@/components/auth/login-form";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata = { title: "Sign in" };

function LoginFallback() {
  return (
    <div className="space-y-4" aria-hidden="true">
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-px w-full" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
    </div>
  );
}

export default function LoginPage() {
  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your workspace to continue."
      footer={
        <>
          New to LedgerLens?{" "}
          <Link
            href="/signup"
            className="font-medium text-primary underline-offset-4 hover:underline outline-none focus-visible:ring-2 focus-visible:ring-ring/50 rounded-sm"
          >
            Create a workspace
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
      <Suspense fallback={<LoginFallback />}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
