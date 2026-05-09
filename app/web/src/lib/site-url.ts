export function getSiteUrl(): string {
  if (typeof window !== "undefined" && window.location.origin) {
    return `${window.location.origin}/`;
  }

  let url =
    process.env.NEXT_PUBLIC_SITE_URL ??
    process.env.NEXT_PUBLIC_VERCEL_URL ??
    "http://localhost:3000/";

  url = url.startsWith("http") ? url : `https://${url}`;
  url = url.endsWith("/") ? url : `${url}/`;

  return url;
}

export function buildAuthCallbackUrl(): string {
  return new URL("auth/callback", getSiteUrl()).toString();
}
