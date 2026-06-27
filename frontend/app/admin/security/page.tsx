import { getSecurityEventsServer } from "@/lib/api/admin";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

export default async function AdminSecurityPage() {
  let events: Awaited<ReturnType<typeof getSecurityEventsServer>>["data"] = [];
  let error: string | null = null;

  try {
    const response = await getSecurityEventsServer();
    events = response.data;
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load security events";
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Security events</h1>
      <p className="text-sm text-[var(--color-foreground-secondary)]">
        Recent governance workflow events from the append-only event store.
      </p>
      {error ? (
        <p className="text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      {events.length === 0 ? (
        <p className="text-sm text-[var(--color-foreground-muted)]">No events recorded yet.</p>
      ) : (
        <ul className="space-y-2">
          {events.map((event) => (
            <li
              key={event.id}
              className="rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-4 py-3 text-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="info">{event.event_type}</Badge>
                <span className="text-[var(--color-foreground-muted)]">
                  {new Date(event.created_at).toLocaleString()}
                </span>
              </div>
              <p className="mt-1 text-[var(--color-foreground-secondary)]">
                {event.aggregate_type} {event.aggregate_id.slice(0, 8)}…
                {event.actor_id ? ` · actor ${event.actor_id.slice(0, 8)}…` : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
