import Link from "next/link";

import { Button } from "@/components/ui/button";
import { LogoMark } from "@/components/common/logo";

export const metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 text-center">
      <LogoMark className="size-10 text-white" />
      <p className="mt-6 font-mono text-xs font-medium uppercase tracking-wide text-muted-foreground">
        404 — Page not found
      </p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
        This page doesn&rsquo;t exist
      </h1>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
        The link may be broken, or the page may have moved during development.
      </p>
      <Button className="mt-6" render={<Link href="/" />}>
        Back to LedgerLens
      </Button>
    </div>
  );
}
