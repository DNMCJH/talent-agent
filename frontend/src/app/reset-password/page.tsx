"use client";

import { Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { Loader2, CheckCircle2 } from "lucide-react";

function ResetPasswordInner() {
  const { t } = useI18n();
  const { setSession } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [pwd, setPwd] = useState("");
  const [pwd2, setPwd2] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (pwd !== pwd2) {
      setError(t.reset.mismatch);
      return;
    }
    if (pwd.length < 6) {
      setError(t.login.passwordLabel);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/backend/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password: pwd }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (body.detail?.includes("expired")) setError(t.reset.expired);
        else if (body.detail?.includes("invalid")) setError(t.reset.invalid);
        else setError(body.detail || `Error ${res.status}`);
        return;
      }
      setDone(true);
      setSession(body.access_token, body.user_id);
      setTimeout(() => router.replace("/projects"), 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 px-3 py-6">
      <Card className="w-full max-w-sm sm:max-w-md">
        <CardHeader className="text-center space-y-1">
          <CardTitle className="text-xl sm:text-2xl">{t.reset.title}</CardTitle>
          <CardDescription className="text-xs sm:text-sm">{t.reset.subtitle}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 px-4 sm:px-6">
          {done ? (
            <div className="flex items-start gap-2 p-3 rounded-md bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-900">
              <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0 mt-0.5" />
              <p className="text-xs sm:text-sm text-green-900 dark:text-green-200">{t.reset.success}</p>
            </div>
          ) : !token ? (
            <>
              <p className="text-sm text-destructive">{t.reset.invalid}</p>
              <Link href="/forgot-password" className="block">
                <Button variant="outline" className="w-full">{t.forgot.title}</Button>
              </Link>
            </>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-3">
              <Input
                type="password"
                placeholder={t.reset.newPwd}
                value={pwd}
                onChange={(e) => setPwd(e.target.value)}
                required
                minLength={6}
                autoComplete="new-password"
              />
              <Input
                type="password"
                placeholder={t.reset.confirmPwd}
                value={pwd2}
                onChange={(e) => setPwd2(e.target.value)}
                required
                minLength={6}
                autoComplete="new-password"
              />
              {error && <p className="text-xs sm:text-sm text-destructive break-words">{error}</p>}
              <Button className="w-full" type="submit" disabled={loading}>
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {loading ? t.reset.submitting : t.reset.submit}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ResetPasswordInner />
    </Suspense>
  );
}
