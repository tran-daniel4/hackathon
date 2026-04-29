import "next-auth"
import "next-auth/jwt"

declare module "next-auth" {
  interface Session {
    backendAccessToken?: string
    backendRefreshToken?: string
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    backendAccessToken?: string
    backendRefreshToken?: string
  }
}
