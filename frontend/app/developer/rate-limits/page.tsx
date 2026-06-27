import { DeveloperRateLimitsPanel } from "@/components/developer-rate-limits-panel";
import { getRateLimitGaugesServer } from "@/lib/api/developer";

export const dynamic = "force-dynamic";

export default async function DeveloperRateLimitsPage() {
  const gauges = await getRateLimitGaugesServer();
  const tenantLimit =
    typeof gauges.meta.tenant_limit_per_minute === "number"
      ? gauges.meta.tenant_limit_per_minute
      : 1000;

  return (
    <DeveloperRateLimitsPanel gauges={gauges.data} tenantLimitPerMinute={tenantLimit} />
  );
}
