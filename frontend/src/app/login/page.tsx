"use client";

import { signIn, useSession } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { Loader2, CheckCircle2, ArrowLeft } from "lucide-react";

/** Left brand panel — fills the other half of the viewport so the auth form
 *  reads as one side of a composition, not a card adrift in white space. */
function BrandPanel() {
  const { t } = useI18n();
  const points = [
    t.landing.feature1Title,
    t.landing.feature2Title,
    t.landing.feature3Title,
  ];
  return (
    <div className="hidden flex-col justify-between bg-foreground p-12 text-background lg:flex">
      <Link
        href="/"
        className="flex items-center gap-2.5 transition-opacity hover:opacity-80"
      >
        <span className="grid h-6 w-6 place-items-center bg-background font-mono text-xs font-bold text-foreground">
          TA
        </span>
        <span className="text-sm font-medium tracking-tight">Talent Agent</span>
      </Link>
      <div>
        <h2 className="max-w-sm text-3xl font-semibold leading-tight tracking-tight">
          {t.landing.hero}
        </h2>
        <p className="mt-4 max-w-sm text-sm leading-relaxed text-background/60">
          {t.landing.heroSub}
        </p>
        <div className="mt-10 border-t border-background/15">
          {points.map((p, i) => (
            <div
              key={p}
              className="flex items-center gap-4 border-b border-background/15 py-3.5"
            >
              <span className="font-mono text-xs text-background/50">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="text-sm">{p}</span>
            </div>
          ))}
        </div>
      </div>
      <span className="font-mono text-xs text-background/40">
        Next.js · FastAPI · DeepSeek · Qdrant
      </span>
    </div>
  );
}

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
    if (status === "authenticated" || token) router.replace("/");
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
      <div className="grid min-h-screen lg:grid-cols-2">
        <BrandPanel />
        <div className="flex flex-col justify-center px-6 py-12 sm:px-12">
          <div className="mx-auto w-full max-w-[360px]">
            <CheckCircle2 className="h-10 w-10 text-foreground" />
            <h1 className="mt-4 text-2xl font-semibold tracking-tight">
              {t.login.registerSentTitle}
            </h1>
            <p className="mt-2 break-words text-sm leading-relaxed text-muted-foreground">
              {t.login.registerSentBody.replace("{email}", sentEmail)}
            </p>
            <Button
              className="mt-6 h-11 w-full rounded-none"
              onClick={() => router.replace("/")}
            >
              {locale === "zh" ? "继续使用" : "Continue"}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <BrandPanel />
      <div className="flex flex-col justify-center px-6 py-12 sm:px-12">
        <div className="mx-auto w-full max-w-[360px]">
          {/* Logo — shown here only on mobile, where the brand panel is
              hidden. Links home so there is a way back from login. */}
          <Link
            href="/"
            className="mb-10 flex items-center gap-2.5 transition-opacity hover:opacity-80 lg:hidden"
          >
            <span className="grid h-6 w-6 place-items-center bg-foreground font-mono text-xs font-bold text-background">
              TA
            </span>
            <span className="text-sm font-medium tracking-tight">
              Talent Agent
            </span>
          </Link>

          {/* Explicit way back to the landing page — on desktop the brand
              panel's logo also links home, but a labelled link is clearer. */}
          <Link
            href="/"
            className="mb-8 hidden items-center gap-1 font-mono text-xs text-muted-foreground transition-colors hover:text-foreground lg:inline-flex"
          >
            <ArrowLeft className="h-3 w-3" />
            {locale === "zh" ? "返回首页" : "Back to home"}
          </Link>

          <h1 className="text-2xl font-semibold tracking-tight">
            {mode === "login" ? t.login.signIn : t.login.signUpBtn}
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            {t.login.subtitle}
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-3">
            <Input
              type="email"
              placeholder={t.login.emailLabel}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="h-11 rounded-none"
            />
            <Input
              type="password"
              placeholder={t.login.passwordLabel}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              className="h-11 rounded-none"
            />
            {error && (
              <p className="break-words text-sm text-destructive">{error}</p>
            )}
            <Button
              className="h-11 w-full rounded-none"
              type="submit"
              disabled={loading}
            >
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {mode === "login" ? t.login.signInBtn : t.login.signUpBtn}
            </Button>
          </form>

          <div className="mt-4 flex items-center justify-between text-xs">
            <button
              type="button"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              {mode === "login" ? t.login.noAccount : t.login.hasAccount}
            </button>
            {mode === "login" && (
              <Link
                href="/forgot-password"
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                {t.login.forgot}
              </Link>
            )}
          </div>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-background px-3 font-mono text-xs uppercase tracking-wider text-muted-foreground">
                {t.login.or}
              </span>
            </div>
          </div>

          <Button
            type="button"
            variant="outline"
            className="h-11 w-full rounded-none"
            onClick={() => signIn("github", { callbackUrl: "/" })}
          >
            {t.login.github}
          </Button>
          <p className="mt-2 text-center text-xs text-muted-foreground">
            {t.login.githubHint}
          </p>

          <div className="mt-8 text-center">
            <button
              type="button"
              onClick={toggleLocale}
              className="font-mono text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              {locale === "en" ? "中文" : "English"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
