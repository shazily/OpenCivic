/**
 * Keycloak OIDC authentication.
 * Access tokens stored in memory only — never localStorage (XSS prevention).
 * Refresh tokens in httpOnly cookies — set by the API server.
 * Silent refresh handled before token expiry.
 */
import Keycloak from "keycloak-js";

const keycloakConfig = {
  url: process.env.NEXT_PUBLIC_KEYCLOAK_URL || "http://localhost:8080",
  realm: "opencivic-platform", // Overridden per tenant at runtime
  clientId: "opencivic-portal",
};

let _instance: Keycloak | null = null;

export function getKeycloak(): Keycloak {
  if (!_instance) {
    _instance = new Keycloak(keycloakConfig);
  }
  return _instance;
}

export async function initAuth(realm?: string): Promise<boolean> {
  const kc = getKeycloak();
  if (realm) {
    // Override realm for tenant-specific auth
    (kc as any).realm = realm;
  }
  try {
    const authenticated = await kc.init({
      onLoad: "check-sso",
      silentCheckSsoRedirectUri: window.location.origin + "/silent-check-sso.html",
      pkceMethod: "S256", // PKCE — no client secret in browser
      checkLoginIframe: false,
    });
    if (authenticated && kc.token) {
      const { apiClient } = await import("@/lib/api/client");
      apiClient.setToken(kc.token);
      // Schedule silent refresh 2 minutes before expiry
      kc.onTokenExpired = () => {
        kc.updateToken(120).then((refreshed) => {
          if (refreshed && kc.token) apiClient.setToken(kc.token);
        }).catch(() => kc.logout());
      };
    }
    return authenticated;
  } catch {
    return false;
  }
}

export function login() { getKeycloak().login(); }
export function logout() { getKeycloak().logout(); }
export function getToken(): string | undefined { return getKeycloak().token; }
export function getRoles(): string[] { return getKeycloak().realmAccess?.roles || []; }
