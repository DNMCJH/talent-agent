"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Nav } from "@/components/nav";
import { EmailVerifyBanner } from "@/components/email-verify-banner";
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

  return (
    <div className="min-h-screen flex flex-col">
      <Nav />
      <EmailVerifyBanner />
      <main className="flex-1 container max-w-7xl mx-auto px-4 sm:px-6 py-6">{children}</main>
    </div>
  );
}
