"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/context";
import { Loader2, CheckCircle2 } from "lucide-react";

export default function ForgotPasswordPage() {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await fetch("/api/backend/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      setSent(true);
    } catch {
      // Backend is intentionally always 200 to avoid leaking which emails exist,
      // so treat network errors the same way visually.
      setSent(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 px-3 py-6">
      <Card className="w-full max-w-sm sm:max-w-md">
        <CardHeader className="text-center space-y-1">
          <CardTitle className="text-xl sm:text-2xl">{t.forgot.title}</CardTitle>
          <CardDescription className="text-xs sm:text-sm">{t.forgot.subtitle}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 px-4 sm:px-6">
          {sent ? (
            <div className="space-y-3">
              <div className="flex items-start gap-2 p-3 rounded-md bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-900">
                <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0 mt-0.5" />
                <p className="text-xs sm:text-sm text-green-900 dark:text-green-200">{t.forgot.sent}</p>
              </div>
              <Link href="/login" className="block">
                <Button variant="outline" className="w-full">{t.forgot.back}</Button>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-3">
              <Input
                type="email"
                placeholder={t.login.emailLabel}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
              <Button className="w-full" type="submit" disabled={loading || !email}>
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {loading ? t.forgot.sending : t.forgot.submit}
              </Button>
              <Link href="/login" className="block text-center text-xs text-muted-foreground hover:text-foreground">
                {t.forgot.back}
              </Link>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
