"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/i18n/context";
import { Button } from "@/components/ui/button";
import { Loader2, Mail } from "lucide-react";

type MeData = {
  email: string | null;
  email_verified: boolean;
};

export function EmailVerifyBanner() {
  const api = useApi();
  const { token } = useAuth();
  const { t } = useI18n();
  const [me, setMe] = useState<MeData | null>(null);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  useEffect(() => {
    if (!token) return;
    api.get<MeData>("/auth/me").then(setMe).catch(() => {});
  }, [token, api]);

  if (!me || !me.email || me.email_verified) return null;

  async function handleResend() {
    setResending(true);
    try {
      const res = await api.post<{ status: string }>("/auth/resend-verification", {});
      if (res.status === "already_verified") setMe((m) => m ? { ...m, email_verified: true } : m);
      else setResent(true);
    } catch {
      // silent
    } finally {
      setResending(false);
    }
  }

  return (
    <div className="bg-amber-50 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-900 px-4 py-2">
      <div className="container max-w-7xl mx-auto flex flex-wrap items-center gap-2 text-xs sm:text-sm">
        <Mail className="h-4 w-4 text-amber-600 shrink-0" />
        <span className="text-amber-900 dark:text-amber-200">
          {t.banner.unverifiedBody.replace("{email}", me.email)}
        </span>
        {resent ? (
          <span className="text-green-700 dark:text-green-400 font-medium">{t.banner.resent}</span>
        ) : (
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-2 text-xs text-amber-700 hover:text-amber-900"
            onClick={handleResend}
            disabled={resending}
          >
            {resending && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
            {t.banner.resend}
          </Button>
        )}
      </div>
    </div>
  );
}
