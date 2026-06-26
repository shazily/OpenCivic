import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-[var(--color-background-secondary)] text-[var(--color-foreground)]",
        success:
          "border-transparent bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
        warning:
          "border-transparent bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
        danger:
          "border-transparent bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
        info: "border-transparent bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200",
        outline: "border-[var(--color-border)] text-[var(--color-foreground-secondary)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
