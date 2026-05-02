import NextAuth from "next-auth"
import GitHub from "next-auth/providers/github"

export const { handlers, auth, signIn, signOut } = NextAuth({
  secret: process.env.NEXTAUTH_SECRET,
  trustHost: true,
  providers: [
    GitHub({
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
      authorization: { params: { scope: "read:user user:email public_repo" } },
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      if (account?.access_token) {
        token.githubAccessToken = account.access_token
        try {
          const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
          const res = await fetch(`${apiUrl}/auth/github`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ access_token: account.access_token }),
          })
          if (res.ok) {
            const data = await res.json()
            token.backendAccessToken = data.access_token
            token.backendRefreshToken = data.refresh_token
          }
        } catch {
          // backend unavailable — OAuth succeeds but tokens won't be set
        }
      }
      return token
    },
    async session({ session, token }) {
      return {
        ...session,
        backendAccessToken: token.backendAccessToken as string | undefined,
        backendRefreshToken: token.backendRefreshToken as string | undefined,
        githubAccessToken: token.githubAccessToken as string | undefined,
      }
    },
  },
})
