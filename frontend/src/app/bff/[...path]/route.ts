import { NextResponse, type NextRequest } from "next/server";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);
const CACHEABLE_CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=300";
const NO_STORE_CACHE_CONTROL = "no-store";

function resolveBffOrigin(): string | null {
  const origin = process.env.FOOTBALL_BFF_ORIGIN?.trim() ?? process.env.BFF_ORIGIN?.trim();
  return origin && /^https?:\/\//i.test(origin) ? origin : null;
}

function buildTargetUrl(origin: string, pathSegments: string[], search: string): string {
  const baseUrl = origin.endsWith("/") ? origin : `${origin}/`;
  const relativePath = pathSegments.map((segment) => encodeURIComponent(segment)).join("/");
  const targetUrl = new URL(relativePath, baseUrl);
  targetUrl.search = search;
  return targetUrl.toString();
}

function buildProxyHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  return headers;
}

function isCacheableRequest(request: NextRequest, pathSegments: string[]): boolean {
  const method = request.method.toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    return false;
  }

  if (request.headers.has("authorization") || request.headers.has("cookie")) {
    return false;
  }

  return pathSegments[0] === "api" && pathSegments[1] === "v1";
}

function buildResponseHeaders(response: Response, cacheControl: string): Headers {
  const headers = new Headers();
  response.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  headers.set("Cache-Control", cacheControl);
  return headers;
}

async function proxyBffRequest(
  request: NextRequest,
  context: { params: Promise<{ path?: string[] }> },
) {
  const origin = resolveBffOrigin();
  if (!origin) {
    return NextResponse.json({ message: "BFF origin não configurado." }, { status: 500 });
  }

  const { path = [] } = await context.params;
  const targetUrl = buildTargetUrl(origin, path, request.nextUrl.search);
  const method = request.method.toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer();
  const cacheable = isCacheableRequest(request, path);
  const fetchOptions: RequestInit = {
    method,
    headers: buildProxyHeaders(request),
    body,
    redirect: "manual",
    cache: "no-store",
  };

  const upstreamResponse = await fetch(targetUrl, fetchOptions);
  const cacheControl =
    cacheable && upstreamResponse.ok ? CACHEABLE_CACHE_CONTROL : NO_STORE_CACHE_CONTROL;

  return new NextResponse(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: buildResponseHeaders(upstreamResponse, cacheControl),
  });
}

export const GET = proxyBffRequest;
export const HEAD = proxyBffRequest;
export const POST = proxyBffRequest;
export const PUT = proxyBffRequest;
export const PATCH = proxyBffRequest;
export const DELETE = proxyBffRequest;
