"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/lib/auth-context";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
  const { token, loading } = useAuth();
  const router = useRouter();

  const isAuthed = status === "authenticated" || !!token;
  const isLoading = status === "loading" || loading;

  useEffect(() => {
    if (!isLoading && !isAuthed) router.replace("/login");
  }, [isLoading, isAuthed, router]);

  if (!isAuthed) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Loading…
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}
