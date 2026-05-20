"use client";

import { signIn, useSession } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { Loader2, CheckCircle2 } from "lucide-react";

export default function LoginPage() {
  const { status } = useSession();
  const { token, login, register } = useAuth();
  const router = useRouter();
  const { t, locale, toggleLocale } = useI18n();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [sentEmail, setSentEmail] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated" || token) router.replace("/projects");
  }, [status, token, router]);

  useEffect(() => {
    fetch("/api/auth/csrf").catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "register") {
        await register(email, password);
        setSentEmail(email);
      } else {
        await login(email, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  if (sentEmail) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/30 px-3 py-6">
        <Card className="w-full max-w-sm sm:max-w-md">
          <CardHeader className="text-center space-y-2">
            <CheckCircle2 className="h-12 w-12 text-green-600 mx-auto" />
            <CardTitle className="text-xl sm:text-2xl">{t.login.registerSentTitle}</CardTitle>
            <CardDescription className="text-sm break-words">
              {t.login.registerSentBody.replace("{email}", sentEmail)}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full" onClick={() => router.replace("/projects")}>
              {locale === "zh" ? "继续使用" : "Continue"}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 px-3 py-6">
      <Card className="w-full max-w-sm sm:max-w-md">
        <CardHeader className="text-center space-y-1">
          <CardTitle className="text-xl sm:text-2xl">{t.login.title}</CardTitle>
          <CardDescription className="text-xs sm:text-sm">{t.login.subtitle}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 px-4 sm:px-6">
          <form onSubmit={handleSubmit} className="space-y-3">
            <Input
              type="email"
              placeholder={t.login.emailLabel}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
            <Input
              type="password"
              placeholder={t.login.passwordLabel}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
            />
            {error && (
              <p className="text-xs sm:text-sm text-destructive break-words">{error}</p>
            )}
            <Button className="w-full" type="submit" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {mode === "login" ? t.login.signInBtn : t.login.signUpBtn}
            </Button>
          </form>

          <div className="flex items-center justify-between text-xs">
            <button
              type="button"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
              className="text-muted-foreground hover:text-foreground"
            >
              {mode === "login" ? t.login.noAccount : t.login.hasAccount}
            </button>
            {mode === "login" && (
              <Link
                href="/forgot-password"
                className="text-muted-foreground hover:text-foreground"
              >
                {t.login.forgot}
              </Link>
            )}
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">{t.login.or}</span>
            </div>
          </div>

          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => signIn("github", { callbackUrl: "/projects" })}
          >
            {t.login.github}
          </Button>
          <p className="text-xs text-center text-muted-foreground">{t.login.githubHint}</p>

          <div className="text-center">
            <button
              type="button"
              onClick={toggleLocale}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              {locale === "en" ? "中文" : "English"}
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
