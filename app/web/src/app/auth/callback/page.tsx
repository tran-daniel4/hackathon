"use client"

import { useSession } from "next-auth/react"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

type ExtendedSession = {
  backendAccessToken?: string
  backendRefreshToken?: string
  githubAccessToken?: string
}

export default function AuthCallback() {
  const { data: session, status } = useSession()
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (status === "loading") return
    if (status === "unauthenticated") {
      router.replace("/")
      return
    }

    const s = session as (typeof session & ExtendedSession) | null

    async function finishSignIn() {
      let accessToken = s?.backendAccessToken
      let refreshToken = s?.backendRefreshToken

      // Server-side JWT callback succeeded — tokens already in session
      if (accessToken) {
        localStorage.setItem("access_token", accessToken)
        localStorage.setItem("refresh_token", refreshToken ?? "")
        router.replace("/diagrams")
        return
      }

      // Server-side exchange failed silently (backend unreachable during OAuth).
      // Retry client-side using the GitHub token that IS in the session.
      const githubToken = s?.githubAccessToken
      if (!githubToken) {
        setError("Sign-in failed: no GitHub token available. Please try again.")
        return
      }

      try {
        const res = await fetch(`${API_URL}/auth/github`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ access_token: githubToken }),
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          setError(body.detail ?? "Sign-in failed. Please try again.")
          return
        }
        const data = await res.json()
        localStorage.setItem("access_token", data.access_token)
        localStorage.setItem("refresh_token", data.refresh_token ?? "")
        router.replace("/diagrams")
      } catch {
        setError("Could not reach the server. Make sure the API is running and try again.")
      }
    }

    finishSignIn()
  }, [session, status, router])

  if (error) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex flex-col items-center justify-center gap-4">
        <div className="text-red-400 text-[13px]">{error}</div>
        <button
          onClick={() => router.replace("/")}
          className="text-white/40 text-[11px] uppercase tracking-[0.15em] hover:text-white/70 transition-colors"
        >
          Back to home
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
      <div className="text-white/50 text-[11px] uppercase tracking-[0.2em]">
        Completing sign in…
      </div>
    </div>
  )
}
