import { Suspense } from "react";
import Link from "next/link";

import { AuthShell } from "@/components/auth/auth-shell";
import { SignupForm } from "@/components/auth/signup-form";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata = { title: "Create your workspace" };

function SignupFallback() {
  return (
    <div className="space-y-4" aria-hidden="true">
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-px w-full" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
    </div>
  );
}

export default function SignupPage() {
  return (
    <AuthShell
      title="Create your workspace"
      subtitle="Start reconciling your financial records in minutes. Free while in beta."
      footer={
        <>
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-primary underline-offset-4 hover:underline outline-none focus-visible:ring-2 focus-visible:ring-ring/50 rounded-sm"
          >
            Sign in
          </Link>
        </>
      }
    >
      <Suspense fallback={<SignupFallback />}>
        <SignupForm />
      </Suspense>
    </AuthShell>
  );
}
