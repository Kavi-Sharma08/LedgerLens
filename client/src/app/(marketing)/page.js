import Link from "next/link";

import {
  ArrowLeftRight,
  ArrowRight,
  BrainCircuit,
  FileText,
  Layers,
  Plug,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { siteConfig } from "@/config/site";

const steps = [
  {
    icon: Plug,
    step: "01",
    title: "Connect your financial sources",
    description:
      "Bring in ledgers from your bank, payment processors, and ERP. LedgerLens normalizes every record into one consistent format.",
  },
  {
    icon: ArrowLeftRight,
    step: "02",
    title: "Reconcile automatically",
    description:
      "Transactions are matched across systems, so discrepancies surface immediately and balances are always explained.",
  },
  {
    icon: BrainCircuit,
    step: "03",
    title: "Investigate exceptions with AI",
    description:
      "When something doesn't match, LedgerLens investigates the exception, gathers evidence, and prepares it for a human decision.",
  },
];

const features = [
  {
    icon: Layers,
    title: "Unified transaction records",
    description:
      "Every source is mapped to a single transaction schema, so comparisons are always apples-to-apples.",
  },
  {
    icon: TriangleAlert,
    title: "Exception-first workflow",
    description:
      "Only unmatched records reach your team, ranked by materiality instead of date order.",
  },
  {
    icon: BrainCircuit,
    title: "AI-powered analysis",
    description:
      "Agents trace each exception through your data, propose a likely cause, and attach the evidence.",
  },
  {
    icon: FileText,
    title: "Audit trail built in",
    description:
      "Every match, override, and resolution is recorded with who, what, and when — ready for review.",
  },
  {
    icon: ShieldCheck,
    title: "Human-in-the-loop control",
    description:
      "AI recommends, people decide. Approve, adjust, or escalate with full context at hand.",
  },
  {
    icon: ArrowLeftRight,
    title: "Continuous reconciliation",
    description:
      "No more month-end fire drills. Ledgers stay reconciled as transactions arrive.",
  },
];

function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[480px] bg-gradient-to-b from-accent/70 to-transparent"
      />
      <div className="mx-auto max-w-6xl px-4 pb-16 pt-16 sm:px-6 sm:pt-24">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl sm:leading-[1.15]">
            Financial reconciliation,
            <br />
            without the manual investigation.
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            {siteConfig.description}
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button size="lg" render={<Link href="/signup" />} className="w-full sm:w-auto">
              Get started
              <ArrowRight aria-hidden="true" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              render={<Link href="/#how-it-works" />}
              className="w-full sm:w-auto"
            >
              How it works
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-14 border-t border-border/70">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="max-w-2xl">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            How LedgerLens works
          </h2>
          <p className="mt-3 text-base leading-relaxed text-muted-foreground">
            From raw financial data to resolved exceptions, in three steps.
          </p>
        </div>
        <ol className="mt-10 grid gap-6 md:grid-cols-3">
          {steps.map((step) => (
            <li key={step.step} className="rounded-xl border border-border bg-card p-6 shadow-xs">
              <div className="flex items-center gap-3">
                <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10">
                  <step.icon className="size-4.5 text-primary" aria-hidden="true" />
                </span>
                <span className="font-mono text-xs font-medium text-muted-foreground">
                  {step.step}
                </span>
              </div>
              <h3 className="mt-4 text-base font-semibold text-foreground">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {step.description}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Features() {
  return (
    <section id="features" className="scroll-mt-14 border-t border-border/70 bg-muted/40">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="max-w-2xl">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Built for teams that close the books
          </h2>
          <p className="mt-3 text-base leading-relaxed text-muted-foreground">
            Everything you need to trust your numbers — and nothing that slows you down.
          </p>
        </div>
        <div className="mt-10 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <div key={feature.title}>
              <span className="flex size-9 items-center justify-center rounded-lg border border-border bg-card shadow-xs">
                <feature.icon className="size-4.5 text-primary" aria-hidden="true" />
              </span>
              <h3 className="mt-4 text-[15px] font-semibold text-foreground">{feature.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="scroll-mt-14">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="rounded-2xl bg-navy px-6 py-14 text-center sm:px-12">
          <h2 className="mx-auto max-w-xl text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            Ready to reconcile your financial records?
          </h2>
          <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-slate-400 sm:text-base">
            Set up your workspace and see your reconciliation status in minutes.
          </p>
          <div className="mt-7 flex justify-center">
            <Button size="lg" render={<Link href="/signup" />}>
              Get started
              <ArrowRight aria-hidden="true" />
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function LandingPage() {
  return (
    <>
      <Hero />
      <HowItWorks />
      <Features />
      <FinalCta />
    </>
  );
}
