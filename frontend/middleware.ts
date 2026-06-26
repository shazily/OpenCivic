import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PREFIXES = ["/admin", "/developer", "/portal/publish", "/portal/review", "/portal/dashboard", "/portal/approval"];

function requiredRole(pathname: string): string | null {
  if (pathname.startsWith("/admin")) {
    return "admin";
  }
  if (pathname.startsWith("/developer")) {
    return "developer";
  }
  if (pathname.startsWith("/portal/review")) {
    return "steward";
  }
  if (pathname.startsWith("/portal/approval")) {
    return "admin";
  }
  if (pathname.startsWith("/portal/publish")) {
    return "publisher";
  }
  if (pathname.startsWith("/portal/dashboard")) {
    return "publisher";
  }
  return null;
}

function roleCanAccess(cookieRole: string, pathname: string): boolean {
  if (cookieRole === "admin") {
    return true;
  }
  if (pathname.startsWith("/admin")) {
    return false;
  }
  if (pathname.startsWith("/developer")) {
    return cookieRole === "developer";
  }
  if (pathname.startsWith("/portal/review")) {
    return cookieRole === "steward";
  }
  if (pathname.startsWith("/portal/approval")) {
    return cookieRole === "admin";
  }
  if (pathname.startsWith("/portal/publish")) {
    return cookieRole === "publisher" || cookieRole === "steward";
  }
  if (pathname.startsWith("/portal/dashboard")) {
    return cookieRole === "publisher" || cookieRole === "steward";
  }
  return true;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const needsAuth = PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
  if (!needsAuth) {
    return NextResponse.next();
  }

  const role = request.cookies.get("opencivic_role")?.value;
  if (!role || !roleCanAccess(role, pathname)) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("next", pathname);
    const required = requiredRole(pathname);
    if (required) {
      loginUrl.searchParams.set("role", required);
    }
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*", "/developer/:path*", "/portal/publish", "/portal/review", "/portal/dashboard", "/portal/approval"],
};
