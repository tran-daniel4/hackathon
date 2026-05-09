const API_PROXY_BASE = "/api/proxy";

export function buildApiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_PROXY_BASE}${normalized}`;
}

