import { apiConfig } from "@/config/site";
import { ApiError } from "@/lib/api/client";

/**
 * Health is a public endpoint: it is polled by the browser and must not go
 * through the authenticated /api/backend boundary.
 */
async function checkHealth() {
  let response;
  try {
    response = await fetch(`${apiConfig.baseUrl}/api/health`, { cache: "no-store" });
  } catch {
    throw new ApiError(
      "We couldn't reach the LedgerLens servers. Check your internet connection and try again.",
      { status: 0, code: "network_error" }
    );
  }
  if (!response.ok) {
    throw new ApiError("Health check failed.", { status: response.status, code: "unhealthy" });
  }
  return response.json();
}

export const healthApi = { checkHealth };
