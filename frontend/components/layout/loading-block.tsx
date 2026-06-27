interface LoadingBlockProps {
  message: string;
}

export function LoadingBlock({ message }: LoadingBlockProps) {
  return (
    <p className="text-sm text-[var(--color-foreground-muted)]" role="status" aria-live="polite">
      {message}
    </p>
  );
}
