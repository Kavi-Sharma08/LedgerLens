import { NextResponse } from "next/server";

import { apiConfig } from "@/config/site";
import { auth } from "@/lib/auth";

/**
 * Authenticated browser -> FastAPI boundary.
 *
 * The browser never authenticates to FastAPI directly. Every protected API
 * request goes through this same-origin route, where Auth.js validates the
 * HttpOnly session cookie first. Only then is the request forwarded to the
 * backend with trusted identity headers plus the internal shared secret:
 *
 *   X-LL-User-Id       stable MongoDB user id (from the Auth.js token)
 *   X-LL-User-Email    user email (URI-encoded)
 *   X-LL-Internal-Sec  INTERNAL_API_SECRET proving Next.js originated the call
 *
 * Client-supplied copies of these headers are always stripped first, so a
 * browser can never forge an identity. FastAPI's get_current_user trusts only
 * this combination (see server/app/api/deps.py and docs/authentication.md).
 */

const INTERNAL_SECRET_HEADER = "X-LL-Internal-Secret";

function requireInternalSecret() {
  const secret = process.env.INTERNAL_API_SECRET;
  if (!secret) {
    throw new Error("INTERNAL_API_SECRET is not set. Add it to client/.env.local.");
  }
  return secret;
}

async function forward(request, context, method) {
  const secret = requireInternalSecret();
  const session = await auth();

  if (!session?.user?.id) {
    return NextResponse.json(
      { detail: "Your session has expired or is invalid. Please sign in again." },
      { status: 401 }
    );
  }

  const { path } = await context.params;
  const targetPath = `/${Array.isArray(path) ? path.join("/") : path}`;
  const search = new URL(request.url).search;
  const target = `${apiConfig.baseUrl}${targetPath}${search}`;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  headers.set("Accept", "application/json");
  headers.set("X-LL-User-Id", String(session.user.id));
  headers.set("X-LL-User-Email", encodeURIComponent(String(session.user.email ?? "")));
  headers.set(INTERNAL_SECRET_HEADER, secret);

  let upstream;
  try {
    upstream = await fetch(target, {
      method,
      headers,
      body: method === "GET" || method === "HEAD" ? undefined : await request.text(),
      cache: "no-store",
    });
  } catch (error) {
    console.error("[backend-proxy] unreachable:", error);
    return NextResponse.json(
      { detail: "LedgerLens services are temporarily unavailable. Please try again shortly." },
      { status: 502 }
    );
  }

  const responseHeaders = new Headers();
  const upstreamContentType = upstream.headers.get("content-type");
  if (upstreamContentType) responseHeaders.set("Content-Type", upstreamContentType);

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export async function GET(request, context) {
  return forward(request, context, "GET");
}

export async function POST(request, context) {
  return forward(request, context, "POST");
}

export async function PATCH(request, context) {
  return forward(request, context, "PATCH");
}

export async function PUT(request, context) {
  return forward(request, context, "PUT");
}

export async function DELETE(request, context) {
  return forward(request, context, "DELETE");
}
