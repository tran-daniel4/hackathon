"use client"

import { useSession } from "next-auth/react"
import { useEffect } from "react"
import { useRouter } from "next/navigation"

export default function AuthCallback() {
  const { data: session, status } = useSession()
  const router = useRouter()

  useEffect(() => {
    if (status === "loading") return

    const s = session as (typeof session & { backendAccessToken?: string; backendRefreshToken?: string }) | null
    if (s?.backendAccessToken) {
      localStorage.setItem("access_token", s.backendAccessToken)
      localStorage.setItem("refresh_token", s.backendRefreshToken ?? "")
    }
    router.replace("/")
  }, [session, status, router])

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
      <div className="text-white/50 text-[11px] uppercase tracking-[0.2em]">
        Completing sign in…
      </div>
    </div>
  )
}
