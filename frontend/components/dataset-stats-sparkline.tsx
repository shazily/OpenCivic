"use client";

interface EngagementPoint {
  date: string;
  views: number;
  downloads: number;
  total: number;
}

interface DatasetStatsSparklineProps {
  points: EngagementPoint[];
  label: string;
}

export function DatasetStatsSparkline({ points, label }: DatasetStatsSparklineProps) {
  if (points.length === 0) {
    return null;
  }

  const values = points.map((point) => point.total);
  const max = Math.max(...values, 1);
  const width = 240;
  const height = 48;
  const step = width / Math.max(points.length - 1, 1);

  const polyline = points
    .map((point, index) => {
      const x = index * step;
      const y = height - (point.total / max) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="rounded-lg border border-[var(--color-border)] p-3">
      <p className="mb-2 text-xs font-medium text-[var(--color-foreground-muted)]">{label}</p>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-12 w-full max-w-xs text-[var(--color-primary)]"
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
      <div className="mt-2 flex justify-between text-[10px] text-[var(--color-foreground-muted)]">
        <span>{points[0]?.date}</span>
        <span>{points[points.length - 1]?.date}</span>
      </div>
    </div>
  );
}
