"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Session, SupabaseClient, User } from "@supabase/supabase-js";

import { createClient } from "@/lib/supabase/client";

const GITHUB_TOKEN_KEY = "sb_github_token";

type AuthContextValue = {
  loading: boolean;
  session: Session | null;
  supabase: SupabaseClient | null;
  user: User | null;
  githubToken: string | null;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [supabase, setSupabase] = useState<SupabaseClient | null>(null);
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<Session | null>(null);
  const [githubToken, setGithubToken] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return sessionStorage.getItem(GITHUB_TOKEN_KEY);
  });

  useEffect(() => {
    const client = createClient();
    if (!client) {
      Promise.resolve().then(() => {
        setLoading(false);
      });
      return;
    }

    Promise.resolve().then(() => {
      setSupabase(client);
    });

    let isMounted = true;

    client.auth.getSession().then(({ data, error }) => {
      if (!isMounted) return;

      if (error) {
        setSession(null);
        setLoading(false);
        return;
      }

      setSession(data.session);
      if (data.session?.provider_token) {
        sessionStorage.setItem(GITHUB_TOKEN_KEY, data.session.provider_token);
        setGithubToken(data.session.provider_token);
      }
      setLoading(false);
    });

    const {
      data: { subscription },
    } = client.auth.onAuthStateChange((event, nextSession) => {
      if (!isMounted) return;

      setSession(nextSession);
      setLoading(false);

      if (nextSession?.provider_token) {
        sessionStorage.setItem(GITHUB_TOKEN_KEY, nextSession.provider_token);
        setGithubToken(nextSession.provider_token);
      } else if (event === "SIGNED_OUT") {
        sessionStorage.removeItem(GITHUB_TOKEN_KEY);
        setGithubToken(null);
      }
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      loading,
      session,
      supabase,
      user: session?.user ?? null,
      githubToken,
    }),
    [loading, session, supabase, githubToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}
