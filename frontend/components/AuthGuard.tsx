"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { api } from "../lib/api";
import { useAuthStore } from "../lib/auth-store";

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const setSession = useAuthStore((s) => s.setSession);
  const clearSession = useAuthStore((s) => s.clearSession);
  const [hydrated, setHydrated] = useState(() => useAuthStore.persist.hasHydrated());
  const [verified, setVerified] = useState(false);

  // Wait for Zustand persist to finish reading from localStorage on first mount.
  useEffect(() => {
    if (hydrated) return;
    const unsub = useAuthStore.persist.onFinishHydration(() => setHydrated(true));
    return unsub;
  }, [hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    let cancelled = false;
    api
      .get("/auth/me")
      .then((res) => {
        if (cancelled) return;
        setSession(token, { id: res.data.id, username: res.data.username });
        setVerified(true);
      })
      .catch(() => {
        if (cancelled) return;
        clearSession();
        router.replace("/login");
      });
    return () => {
      cancelled = true;
    };
  }, [hydrated, token, router, setSession, clearSession]);

  if (!hydrated || !verified) return null;
  return <>{children}</>;
}
