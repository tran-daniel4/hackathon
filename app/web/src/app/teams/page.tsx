"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Dashboard } from "@/app/pages/dashboard";

function getValidToken(key: string): string | null {
  const token = localStorage.getItem(key);
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.exp * 1000 > Date.now() ? token : null;
  } catch {
    return null;
  }
}

export default function TeamsPage() {
  const router = useRouter();
  const { status } = useSession();

  useEffect(() => {
    if (status === "loading") return;
    if (status === "authenticated") return;
    if (getValidToken("access_token") || localStorage.getItem("refresh_token")) return;
    router.replace("/");
  }, [status, router]);

  return <Dashboard />;
}
