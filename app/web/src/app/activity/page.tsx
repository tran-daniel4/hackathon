"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Dashboard } from "@/app/pages/dashboard";
import { useAuth } from "@/components/AuthProvider";

export default function ActivityPage() {
  const router = useRouter();
  const { loading, session } = useAuth();

  useEffect(() => {
    if (!loading && !session) {
      router.replace("/");
    }
  }, [loading, router, session]);

  if (loading || !session) {
    return null;
  }

  return <Dashboard />;
}
