import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}

/** Standard empty / zero-data state — avoids one-off muted paragraphs. */
export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div
      className="rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-background)] px-6 py-12 text-center"
      role="status"
    >
      <p className="text-base font-medium text-[var(--color-foreground)]">{title}</p>
      {description ? (
        <div className="mx-auto mt-2 max-w-md text-sm text-[var(--color-foreground-muted)]">
          {description}
        </div>
      ) : null}
      {action ? <div className="mt-6 flex justify-center">{action}</div> : null}
    </div>
  );
}
