"use client";

import { SessionProvider } from "next-auth/react";
import { Toaster } from "@/components/ui/sonner";
import { I18nProvider } from "@/i18n/context";
import { AuthProvider } from "@/lib/auth-context";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <AuthProvider>
        <I18nProvider>
          {children}
          <Toaster />
        </I18nProvider>
      </AuthProvider>
    </SessionProvider>
  );
}
