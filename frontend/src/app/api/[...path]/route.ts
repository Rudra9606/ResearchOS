import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const backend = (process.env.BACKEND_URL || "http://localhost:8000").replace(/\/$/, "");

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const endpoint = path.join("/");
  const isLogin = endpoint === "auth/login";
  const isRegister = endpoint === "auth/register";
  const jar = await cookies();
  const token = jar.get("researchos_session")?.value;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (token) headers.set("authorization", `Bearer ${token}`);
  const response = await fetch(`${backend}/api/v1/${endpoint}${request.nextUrl.search}`, {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
    cache: "no-store",
  }).catch(() => null);
  if (!response) return NextResponse.json({ detail: "ResearchOS API is unavailable. Check the backend service." }, { status: 502 });

  const type = response.headers.get("content-type") || "application/json";
  const payload = response.status === 204 ? null : await response.arrayBuffer();
  let output: BodyInit | null = payload;
  let sessionToken: string | null = null;
  if ((isLogin || isRegister) && response.ok) {
    const data = JSON.parse(new TextDecoder().decode(payload ?? new ArrayBuffer(0)));
    sessionToken = data.token.access_token;
    output = new TextEncoder().encode(JSON.stringify({ message: data.message, user: data.user }));
  }
  const result = new NextResponse(output, { status: response.status, headers: { "content-type": sessionToken ? "application/json" : type } });
  if (sessionToken) result.cookies.set("researchos_session", sessionToken, {
    httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 60 * 60 * 12,
  });
  const disposition = response.headers.get("content-disposition");
  if (disposition) result.headers.set("content-disposition", disposition);
  if (response.status === 401 && token) result.cookies.set("researchos_session", "", {
    httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0,
  });
  return result;
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
