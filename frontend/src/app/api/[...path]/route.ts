import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const backend = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20_000);
  try {
  const { path } = await context.params;
  const endpoint = path.join("/");
  const collectionEndpoints = new Set([
    "users",
    "projects",
    "conversations",
    "messages",
    "documents",
    "research-runs",
    "research-sources",
    "reports",
    "agent-executions",
    "verified-claims",
    "rag",
    "knowledge-graph",
    "jobs",
    "research",
  ]);
  const backendEndpoint = collectionEndpoints.has(endpoint) ? `${endpoint}/` : endpoint;
  const isLogin = endpoint === "auth/login";
  const isRegister = endpoint === "auth/register";
  const jar = await cookies();
  const token = jar.get("researchos_session")?.value;
  const refreshToken = jar.get("researchos_refresh")?.value;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (token) headers.set("authorization", `Bearer ${token}`);
  const forward = async (accessToken?: string) => fetch(`${backend}/api/v1/${backendEndpoint}${request.nextUrl.search}`, {
    method: request.method,
    headers: accessToken ? (() => { const forwarded = new Headers(headers); forwarded.set("authorization", `Bearer ${accessToken}`); return forwarded; })() : headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
    cache: "no-store",
    signal: controller.signal,
  }).catch(() => null);
  let response = await forward(token);
  let refreshedAccessToken: string | null = null;
  let refreshedRefreshToken: string | null = null;
  if (response?.status === 401 && refreshToken && endpoint !== "auth/refresh") {
    const refreshResponse = await fetch(`${backend}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
      signal: controller.signal,
    }).catch(() => null);
    if (refreshResponse?.ok) {
      const rotated = await refreshResponse.json() as { access_token: string; refresh_token?: string };
      refreshedAccessToken = rotated.access_token;
      refreshedRefreshToken = rotated.refresh_token || refreshToken;
      response = await forward(refreshedAccessToken);
    }
  }
  if (!response) return NextResponse.json({ detail: "ResearchOS API is unavailable. Check the backend service." }, { status: 502 });

  const type = response.headers.get("content-type") || "application/json";
  const payload = response.status === 204 ? null : await response.arrayBuffer();
  let output: BodyInit | null = payload;
  let sessionToken: string | null = null;
  let refreshSessionToken: string | null = null;
  if ((isLogin || isRegister) && response.ok) {
    const data = JSON.parse(new TextDecoder().decode(payload ?? new ArrayBuffer(0)));
    sessionToken = data.token.access_token;
    refreshSessionToken = data.token.refresh_token || null;
    output = new TextEncoder().encode(JSON.stringify({ message: data.message, user: data.user }));
  }
  const result = new NextResponse(output, { status: response.status, headers: { "content-type": sessionToken ? "application/json" : type } });
  if (sessionToken) result.cookies.set("researchos_session", sessionToken, {
    httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 60 * 30,
  });
  if (refreshedAccessToken) result.cookies.set("researchos_session", refreshedAccessToken, {
    httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 60 * 60,
  });
  if (refreshSessionToken) result.cookies.set("researchos_refresh", refreshSessionToken, {
    httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 7,
  });
  if (refreshedRefreshToken) result.cookies.set("researchos_refresh", refreshedRefreshToken, {
    httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 7,
  });
  const disposition = response.headers.get("content-disposition");
  if (disposition) result.headers.set("content-disposition", disposition);
  if (response.status === 401 && (token || refreshToken)) {
    result.cookies.set("researchos_session", "", {
      httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0,
    });
    result.cookies.set("researchos_refresh", "", {
      httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0,
    });
  }
  return result;
  } finally {
    clearTimeout(timeout);
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
