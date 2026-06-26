/** Client-side auth session — access token in memory only; role in localStorage. */

export type StaffRole = "publisher" | "steward" | "admin" | "developer";

const TOKEN_KEY = "opencivic_access_token";
const ROLE_KEY = "opencivic_role";

let memoryAccessToken: string | null = null;

function purgeLegacyTokenStorage(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(TOKEN_KEY);
}

export function getAccessToken(): string | null {
  return memoryAccessToken;
}

export function setAccessToken(token: string): void {
  memoryAccessToken = token;
  purgeLegacyTokenStorage();
}

export function getStaffRole(): StaffRole | null {
  if (typeof window === "undefined") {
    return null;
  }
  const role = window.localStorage.getItem(ROLE_KEY);
  if (
    role === "publisher" ||
    role === "steward" ||
    role === "admin" ||
    role === "developer"
  ) {
    return role;
  }
  return null;
}

export function setSession(token: string, role: StaffRole): void {
  setAccessToken(token);
  window.localStorage.setItem(ROLE_KEY, role);
  document.cookie = `opencivic_role=${role}; path=/; max-age=604800; samesite=strict`;
}

export function clearSession(): void {
  memoryAccessToken = null;
  purgeLegacyTokenStorage();
  window.localStorage.removeItem(ROLE_KEY);
  document.cookie = "opencivic_role=; path=/; max-age=0";
}

export function staffDestinationForRole(role: StaffRole): string {
  switch (role) {
    case "publisher":
      return "/portal/dashboard";
    case "steward":
      return "/portal/review";
    case "admin":
      return "/admin";
    case "developer":
      return "/developer";
    default: {
      const _exhaustive: never = role;
      return _exhaustive;
    }
  }
}

export function roleAllowsPath(role: StaffRole, pathname: string): boolean {
  if (pathname.startsWith("/admin")) {
    return role === "admin";
  }
  if (pathname.startsWith("/developer")) {
    return role === "developer" || role === "admin";
  }
  if (pathname.startsWith("/portal/review")) {
    return role === "steward" || role === "admin";
  }
  if (pathname.startsWith("/portal/approval")) {
    return role === "admin";
  }
  if (pathname.startsWith("/portal/publish")) {
    return role === "publisher" || role === "steward" || role === "admin";
  }
  if (pathname.startsWith("/portal/dashboard")) {
    return role === "publisher" || role === "steward" || role === "admin";
  }
  return true;
}
