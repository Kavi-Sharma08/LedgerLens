import { cn } from "@/lib/utils";

const badgeVariants = {
  default: "border-transparent bg-secondary text-secondary-foreground",
  primary: "border-transparent bg-primary/10 text-primary",
  success: "border-transparent bg-success/10 text-success",
  warning: "border-transparent bg-warning/15 text-warning",
  destructive: "border-transparent bg-destructive/10 text-destructive",
  info: "border-transparent bg-info/10 text-info",
  outline: "text-muted-foreground",
};

function Badge({ className, variant = "default", ...props }) {
  return (
    <span
      data-slot="badge"
      className={cn(
        "inline-flex w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-md border border-border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        badgeVariants[variant],
        className
      )}
      {...props}
    />
  );
}

export { Badge, badgeVariants };
