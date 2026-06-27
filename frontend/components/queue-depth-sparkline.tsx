"use client";

interface QueueDepthSparklineProps {
  points: number[];
  label: string;
}

export function QueueDepthSparkline({ points, label }: QueueDepthSparklineProps) {
  if (points.length === 0) {
    return null;
  }

  const max = Math.max(...points, 1);
  const width = 120;
  const height = 32;
  const step = width / Math.max(points.length - 1, 1);

  const polyline = points
    .map((value, index) => {
      const x = index * step;
      const y = height - (value / max) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="rounded-lg border border-[var(--color-border)] p-2">
      <p className="mb-1 text-[10px] font-medium text-[var(--color-foreground-muted)]">{label}</p>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-8 w-full text-[var(--color-primary)]"
        role="img"
        aria-label={label}
      >
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          points={polyline}
        />
      </svg>
    </div>
  );
}
