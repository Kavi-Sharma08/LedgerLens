import { apiConfig } from "@/config/site";

/**
 * HTTP helpers for talking to the LedgerLens API (FastAPI).
 *
 * - `api` — browser calls. Always routed through the same-origin Next.js
 *   boundary (/api/backend/*), which validates the Auth.js session and injects
 *   trusted identity headers. Browsers never authenticate to FastAPI directly.
 * - `serverApi` — React Server Components. Calls FastAPI server-to-server with
 *   the same trusted headers derived from an already-validated Auth.js session.
 *
 * Both convert transport/server failures into `ApiError` instances carrying
 * human-readable messages that screens can render directly.
 */

export class ApiError extends Error {
  constructor(message, { status = 0, code = "unknown" } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const NETWORK_ERROR_MESSAGE =
  "We couldn't reach the LedgerLens servers. Check your internet connection and try again.";

const SERVER_ERROR_MESSAGE =
  "LedgerLens is having trouble right now. Please try again in a few moments.";

function extractDetail(data) {
  if (!data) return null;
  // FastAPI request-validation errors arrive as a list of issue objects.
  if (Array.isArray(data.detail) && data.detail.length > 0) {
    const first = data.detail[0];
    return typeof first.msg === "string" ? first.msg : null;
  }
  if (typeof data.detail === "string") return data.detail;
  return null;
}

function friendlyMessageForStatus(status, detail, code) {
  switch (status) {
    case 400:
      return detail || "The request was invalid. Please check your input and try again.";
    case 401:
      return (
        detail ||
        "Your session has expired or is invalid. Please sign in again to continue."
      );
    case 403:
      return detail || "You don't have permission to do that.";
    case 404:
      return detail || "We couldn't find what you were looking for.";
    case 409:
      return detail || "That record already exists.";
    case 422:
      return detail || "Some of the information you entered isn't valid.";
    case 502:
    case 503:
      return (
        detail ||
        "LedgerLens services are temporarily unavailable. Please try again shortly."
      );
    default: {
      if (code === "invalid_credentials") {
        return "We couldn't sign you in. Check your email and password and try again.";
      }
      if (status >= 500) return SERVER_ERROR_MESSAGE;
      return detail || SERVER_ERROR_MESSAGE;
    }
  }
}

async function parseJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

const BACKEND_PROXY_PREFIX = "/api/backend";

async function request(path, { method = "GET", body, signal } = {}) {
  let response;
  try {
    response = await fetch(`${BACKEND_PROXY_PREFIX}${path}`, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new ApiError(NETWORK_ERROR_MESSAGE, { status: 0, code: "network_error" });
  }

  const data = await parseJson(response);

  if (!response.ok) {
    throw new ApiError(friendlyMessageForStatus(response.status, extractDetail(data), data?.code), {
      status: response.status,
      code: data?.code ?? "unknown",
    });
  }

  return data;
}

export const api = {
  get: (path, options) => request(path, options),
  post: (path, body, options) => request(path, { ...options, method: "POST", body }),
  patch: (path, body, options) => request(path, { ...options, method: "PATCH", body }),
  put: (path, body, options) => request(path, { ...options, method: "PUT", body }),
  delete: (path, options) => request(path, { ...options, method: "DELETE" }),
};

/**
 * Trusted identity headers for server-to-server calls into FastAPI.
 * Mirrors src/app/api/backend/[...path]/route.js — keep both in sync.
 */
export function trustedBackendHeaders(session, { workspaceId } = {}) {
  const secret = process.env.INTERNAL_API_SECRET;
  if (!secret || !session?.user?.id) return null;

  const headers = {
    Accept: "application/json",
    "X-LL-User-Id": String(session.user.id),
    "X-LL-User-Email": encodeURIComponent(String(session.user.email ?? "")),
    "X-LL-Internal-Secret": secret,
  };
  if (workspaceId && /^[a-fA-F0-9]{24}$/.test(workspaceId)) {
    headers["X-LL-Workspace-Id"] = workspaceId;
  }
  return headers;
}

/**
 * Server-side helper for React Server Components. Requires an already
 * validated Auth.js session; returns parsed JSON or throws ApiError.
 * Pass the active workspace id (from the ll-active-workspace cookie) as
 * `workspaceId` so workspace-scoped calls resolve the right tenant.
 */
async function serverRequest(path, { session, method = "GET", body, workspaceId }) {
  const headers = trustedBackendHeaders(session, { workspaceId });
  if (!headers) {
    throw new ApiError("Authentication required.", { status: 401, code: "unauthorized" });
  }

  let response;
  try {
    response = await fetch(`${apiConfig.baseUrl}${path}`, {
      method,
      headers: body !== undefined ? { ...headers, "Content-Type": "application/json" } : headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(NETWORK_ERROR_MESSAGE, { status: 0, code: "network_error" });
  }

  const data = await parseJson(response);
  if (!response.ok) {
    throw new ApiError(
      friendlyMessageForStatus(response.status, extractDetail(data), data?.code),
      { status: response.status, code: data?.code ?? "unknown" }
    );
  }
  return data;
}

export const serverApi = {
  get: (path, options) => serverRequest(path, options),
};
