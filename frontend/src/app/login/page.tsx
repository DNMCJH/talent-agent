"use client";

import { signIn, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { Loader2 } from "lucide-react";

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
      } else {
        await login(email, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">{t.login.title}</CardTitle>
          <CardDescription>{t.login.subtitle}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-3">
            <Input
              type="email"
              placeholder={locale === "zh" ? "邮箱" : "Email"}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              type="password"
              placeholder={locale === "zh" ? "密码（至少6位）" : "Password (min 6 chars)"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button className="w-full" type="submit" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {mode === "login"
                ? (locale === "zh" ? "登录" : "Sign In")
                : (locale === "zh" ? "注册" : "Sign Up")}
            </Button>
          </form>

          <div className="text-center">
            <button
              type="button"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              {mode === "login"
                ? (locale === "zh" ? "没有账号？注册" : "No account? Register")
                : (locale === "zh" ? "已有账号？登录" : "Have an account? Sign in")}
            </button>
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                {locale === "zh" ? "或" : "OR"}
              </span>
            </div>
          </div>

          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => signIn("github", { callbackUrl: "/projects" })}
          >
            {t.login.signIn} (GitHub)
          </Button>
          <p className="text-xs text-center text-muted-foreground">
            {locale === "zh"
              ? "连接 GitHub 账号可导入私有仓库"
              : "Link GitHub to import private repos"}
          </p>

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
