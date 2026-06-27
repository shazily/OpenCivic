import type { BadgeProps } from "@/components/ui/badge";

export function statusBadgeVariant(
  status: string,
): NonNullable<BadgeProps["variant"]> {
  switch (status) {
    case "published":
      return "success";
    case "pending_review":
    case "pending_approval":
      return "warning";
    case "rejected":
    case "archived":
      return "danger";
    default:
      return "outline";
  }
}

export function stalenessBadgeVariant(
  state: string,
): NonNullable<BadgeProps["variant"]> {
  switch (state) {
    case "fresh":
      return "success";
    case "possibly_outdated":
      return "warning";
    case "stale":
    case "pending_refresh":
      return "danger";
    default:
      return "outline";
  }
}

export function formatStatusLabel(status: string): string {
  return status.replace(/_/g, " ");
}
