"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { LoaderCircle, Mail, CheckCircle, AlertCircle } from "lucide-react";

import { Button } from "@/components/ui/button";

function AcceptInvitationContent() {
  const { token } = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [state, setState] = useState(() => (token ? "loading" : "error"));
  const [message, setMessage] = useState(() => (token ? "" : "Invalid invitation link."));
  const [context, setContext] = useState(null);
  const [sessionEmail, setSessionEmail] = useState(null);

  useEffect(() => {
    if (!token) return;

    let cancelled = false;

    async function run() {
      try {
        const res = await fetch("/api/invitations/accept", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });

        if (cancelled) return;

        const data = await res.json();

        if (!res.ok) {
          setState("error");
          setMessage(data.detail || "This invitation is no longer valid.");
          return;
        }

        if (data.status === "requires_login" || data.status === "requires_signup") {
          setContext(data);
          setState(data.status);
          return;
        }

        if (data.status === "wrong_account") {
          setMessage("signed in with a different email");
          setContext(data);
          setSessionEmail(data.sessionEmail);
          setState("wrong_account");
          return;
        }

        if (data.status === "ok") {
          setContext(data);
          setState("success");
          setTimeout(() => {
            router.push("/dashboard");
          }, 1500);
        }
      } catch {
        if (!cancelled) {
          setState("error");
          setMessage("Something went wrong. Please try again.");
        }
      }
    }

    run();
    return () => { cancelled = true; };
  }, [token, router]);

  const invitationToken = searchParams.get("invitation") || token;

  if (state === "loading") {
    return (
      <Centered>
        <div className="flex flex-col items-center gap-4">
          <LoaderCircle className="size-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Checking your invitation...</p>
        </div>
      </Centered>
    );
  }

  if (state === "error") {
    return (
      <Centered>
        <div className="space-y-4 text-center">
          <IconWrap variant="destructive">
            <AlertCircle className="size-6 text-destructive" />
          </IconWrap>
          <h1 className="text-lg font-semibold text-foreground">Invitation unavailable</h1>
          <p className="text-sm text-muted-foreground">{message}</p>
          <Button variant="outline" onClick={() => router.push("/")}>
            Go to homepage
          </Button>
        </div>
      </Centered>
    );
  }

  if (state === "success") {
    return (
      <Centered>
        <div className="space-y-4 text-center">
          <IconWrap variant="success">
            <CheckCircle className="size-6 text-green-600" />
          </IconWrap>
          <h1 className="text-lg font-semibold text-foreground">
            You&apos;re in{context?.workspaceName ? ` ${context.workspaceName}` : ""}!
          </h1>
          <p className="text-sm text-muted-foreground">
            You&apos;ve been added to the workspace. Redirecting to your dashboard...
          </p>
        </div>
      </Centered>
    );
  }

  if (state === "requires_login" || state === "requires_signup") {
    return (
      <Centered>
        <div className="mx-auto max-w-md space-y-6 px-4 text-center">
          <IconWrap>
            <Mail className="size-6 text-primary" />
          </IconWrap>
          <div className="space-y-2">
            <h1 className="text-lg font-semibold text-foreground">
              You&apos;ve been invited to {context?.workspaceName ?? "a LedgerLens workspace"}
            </h1>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {context?.invitedBy ? (
                <>
                  <strong>{context.invitedBy}</strong> invited you to collaborate.{" "}
                </>
              ) : null}
              {context?.invitedEmail ? (
                <>
                  The invitation was sent to <strong>{context.invitedEmail}</strong>.
                </>
              ) : null}
            </p>
            <p className="text-xs text-muted-foreground">
              {state === "requires_login"
                ? "Sign in to accept this invitation."
                : "Create an account to accept this invitation. It only takes a minute."}
            </p>
          </div>
          <div className="flex flex-col gap-3">
            {state === "requires_signup" ? (
              <Button onClick={() => router.push(`/signup?invitation=${invitationToken}`)}>
                Create account
              </Button>
            ) : (
              <Button onClick={() => router.push(`/login?invitation=${invitationToken}`)}>
                Sign in to accept
              </Button>
            )}
            <Button
              variant="outline"
              onClick={() => router.push(state === "requires_login" ? `/login?invitation=${invitationToken}` : `/signup?invitation=${invitationToken}`)}
            >
              {state === "requires_login" ? "Create an account instead" : "Sign in instead"}
            </Button>
          </div>
        </div>
      </Centered>
    );
  }

  if (state === "wrong_account") {
    return (
      <Centered>
        <div className="mx-auto max-w-md space-y-4 px-4 text-center">
          <IconWrap variant="destructive">
            <AlertCircle className="size-6 text-destructive" />
          </IconWrap>
          <h1 className="text-lg font-semibold text-foreground">Signed in with a different account</h1>
          <p className="text-sm leading-relaxed text-muted-foreground">
            This invitation is for <strong>{context?.invitedEmail}</strong>, but you&apos;re signed
            in as <strong>{sessionEmail}</strong>. Sign out and sign in with the invited email, or
            open this link in the account that matches.
          </p>
          <Button variant="outline" onClick={async () => {
            await fetch("/api/auth/signout", { method: "POST" });
            router.push(`/login?invitation=${invitationToken}`);
          }}>
            Sign in with another account
          </Button>
        </div>
      </Centered>
    );
  }

  return null;
}

function Centered({ children }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="mx-auto max-w-md px-4">{children}</div>
    </div>
  );
}

function IconWrap({ children, variant }) {
  const bg =
    variant === "destructive"
      ? "bg-destructive/10"
      : variant === "success"
        ? "bg-green-500/10"
        : "bg-primary/10";
  return (
    <div className="flex justify-center">
      <div className={`flex size-12 items-center justify-center rounded-full ${bg}`}>
        {children}
      </div>
    </div>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-background">
          <LoaderCircle className="size-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <AcceptInvitationContent />
    </Suspense>
  );
}