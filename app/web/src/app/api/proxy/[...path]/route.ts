import { NextRequest, NextResponse } from "next/server";

const BACKEND_API_BASE =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

function buildBackendUrl(request: NextRequest, path: string[]): URL {
  const incoming = new URL(request.url);
  const target = new URL(BACKEND_API_BASE);
  const backendPath = path.join("/");

  target.pathname = `${target.pathname.replace(/\/$/, "")}/${backendPath}`.replace(/\/{2,}/g, "/");
  target.search = incoming.search;
  return target;
}

function filterHeaders(headers: Headers): Headers {
  const forwarded = new Headers();
  headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      forwarded.set(key, value);
    }
  });
  return forwarded;
}

async function forward(request: NextRequest, path: string[]) {
  const target = buildBackendUrl(request, path);
  const method = request.method.toUpperCase();
  const headers = filterHeaders(request.headers);

  const init: RequestInit = {
    method,
    headers,
    redirect: "manual",
  };

  if (!["GET", "HEAD"].includes(method)) {
    init.body = await request.arrayBuffer();
  }

  const upstream = await fetch(target, init);
  const responseHeaders = filterHeaders(upstream.headers);

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return forward(request, path);
}

export async function POST(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return forward(request, path);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return forward(request, path);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return forward(request, path);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return forward(request, path);
}

export async function OPTIONS(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return forward(request, path);
}
