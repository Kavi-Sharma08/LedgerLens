import Link from "next/link";

import { siteConfig } from "@/config/site";
import { cn } from "@/lib/utils";

function LogoMark({ className }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="8" className="fill-primary" />
      <path
        d="M8 11h13M8 16h9M8 21h5"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        opacity="0.45"
      />
      <circle cx="20.5" cy="18.5" r="5" stroke="currentColor" strokeWidth="2.4" />
      <path
        d="m24.2 22.2 3 3"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Logo({ className, markClassName, href = "/", children }) {
  return (
    <Link
      href={href}
      aria-label={`${siteConfig.name} home`}
      className={cn(
        "inline-flex items-center gap-2 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
        className
      )}
    >
      <LogoMark className={cn("size-7 text-white", markClassName)} />
      <span className="text-[17px] font-semibold tracking-tight text-foreground">
        {siteConfig.name}
      </span>
      {children}
    </Link>
  );
}

export { Logo, LogoMark };
