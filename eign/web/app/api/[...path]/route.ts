import { NextResponse, type NextRequest } from "next/server";

import { identityHeaders, resolveIdentity } from "@/lib/identity";

const DEFAULT_API_URL = "http://localhost:8080";

function apiBaseUrl(): string {
  return (process.env.EIGN_API_URL ?? DEFAULT_API_URL).replace(/\/+$/, "");
}

/**
 * Same-origin proxy for the Eign API.
 *
 * In production nginx routes `/api/*` straight to the backend; this handler is
 * the equivalent for `next dev`, where no nginx terminates mTLS. It only ever
 * forwards to `EIGN_API_URL`, so the path cannot be used to reach another host.
 */
async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path?: string[] }> },
): Promise<NextResponse> {
  const identity = await resolveIdentity();
  if (!identity) {
    return NextResponse.json(
      { detail: "A verified client certificate is required" },
      { status: 401 },
    );
  }

  const { path } = await context.params;
  const target = new URL(`${apiBaseUrl()}/${(path ?? []).join("/")}`);
  target.search = request.nextUrl.search;

  const headers = new Headers(identityHeaders(identity));
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);

  const method = request.method.toUpperCase();
  const rawBody = method === "GET" || method === "HEAD" ? "" : await request.text();

  const upstream = await fetch(target, {
    method,
    headers,
    body: rawBody === "" ? undefined : rawBody,
    cache: "no-store",
  });

  const payload = await upstream.text();
  return new NextResponse(payload === "" ? null : payload, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
    },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
