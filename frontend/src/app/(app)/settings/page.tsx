"use client";

import { useEffect, useState } from "react";
import { signOut, useSession } from "next-auth/react";
import { useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/i18n/context";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Loader2, Check, Mail } from "lucide-react";

type Me = {
  id: number;
  github_login: string | null;
  email: string | null;
  avatar_url: string | null;
  email_verified: boolean;
};

/** A labelled key/value row inside a settings card. */
function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b py-3 last:border-b-0">
      <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <div className="flex items-center gap-2 text-sm">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const api = useApi();
  const { data: session } = useSession();
  const { token: emailToken, logout } = useAuth();
  const { t, locale, toggleLocale } = useI18n();

  const [me, setMe] = useState<Me | null>(null);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const [pwSending, setPwSending] = useState(false);
  const [pwSent, setPwSent] = useState(false);

  useEffect(() => {
    if (!api.token) return;
    api.get<Me>("/auth/me").then(setMe).catch(() => {});
  }, [api]);

  const isGithub = !!me?.github_login || !!session?.githubLogin;
  const displayName = me?.github_login || me?.email || "—";
  const avatar = me?.avatar_url || session?.user?.image || null;
  const initial = displayName.charAt(0).toUpperCase();

  async function handleResend() {
    setResending(true);
    try {
      const res = await api.post<{ status: string }>(
        "/auth/resend-verification",
        {},
      );
      if (res.status === "already_verified") {
        setMe((m) => (m ? { ...m, email_verified: true } : m));
      } else {
        setResent(true);
      }
    } catch {
      toast.error(locale === "zh" ? "发送失败，请稍后重试" : "Failed to send");
    } finally {
      setResending(false);
    }
  }

  async function handlePasswordReset() {
    if (!me?.email) return;
    setPwSending(true);
    try {
      await api.post("/auth/forgot-password", { email: me.email });
      setPwSent(true);
    } catch {
      toast.error(locale === "zh" ? "发送失败，请稍后重试" : "Failed to send");
    } finally {
      setPwSending(false);
    }
  }

  function handleSignOut() {
    // Email and GitHub sessions are torn down differently.
    if (emailToken) {
      logout();
      window.location.href = "/login";
    } else {
      signOut({ callbackUrl: "/login" });
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t.settings.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {t.settings.subtitle}
        </p>
      </div>

      {/* Account */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t.settings.account}</CardTitle>
          <CardDescription>{t.settings.accountDesc}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3 border-b pb-4">
            {avatar ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={avatar}
                alt=""
                className="h-11 w-11 rounded border object-cover"
              />
            ) : (
              <span className="grid h-11 w-11 place-items-center rounded bg-foreground font-mono text-sm font-medium text-background">
                {initial}
              </span>
            )}
            <div className="min-w-0">
              <p className="truncate text-sm font-medium tracking-tight">
                {displayName}
              </p>
              <p className="font-mono text-xs text-muted-foreground">
                ID {me?.id ?? "—"}
              </p>
            </div>
          </div>
          <Row label={t.settings.authMethod}>
            {isGithub ? (
              <Badge variant="secondary">{t.settings.authGithub}</Badge>
            ) : (
              <Badge variant="secondary" className="gap-1">
                <Mail className="h-3 w-3" />
                {t.settings.authEmail}
              </Badge>
            )}
          </Row>
          {me?.email && (
            <Row label={t.settings.emailLabel}>
              <span className="text-muted-foreground">{me.email}</span>
              {me.email_verified ? (
                <Badge variant="outline" className="gap-1">
                  <Check className="h-3 w-3" />
                  {t.settings.verified}
                </Badge>
              ) : resent ? (
                <span className="font-mono text-xs text-green-700">
                  {t.banner.resent}
                </span>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={resending}
                  onClick={handleResend}
                >
                  {resending && (
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  )}
                  {t.settings.resend}
                </Button>
              )}
            </Row>
          )}
        </CardContent>
      </Card>

      {/* Security */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t.settings.security}</CardTitle>
          <CardDescription>{t.settings.securityDesc}</CardDescription>
        </CardHeader>
        <CardContent>
          <Row label={t.settings.password}>
            {isGithub ? (
              <span className="text-muted-foreground">
                {t.settings.passwordGithub}
              </span>
            ) : pwSent ? (
              <span className="font-mono text-xs text-green-700">
                {t.settings.passwordResetSent}
              </span>
            ) : (
              <Button
                size="sm"
                variant="outline"
                disabled={pwSending || !me?.email}
                onClick={handlePasswordReset}
              >
                {pwSending && (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                )}
                {t.settings.passwordReset}
              </Button>
            )}
          </Row>
        </CardContent>
      </Card>

      {/* Preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t.settings.preferences}</CardTitle>
        </CardHeader>
        <CardContent>
          <Row label={t.settings.language}>
            <Button size="sm" variant="outline" onClick={toggleLocale}>
              {locale === "zh" ? "中文" : "English"}
            </Button>
          </Row>
        </CardContent>
      </Card>

      {/* Sign out */}
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
          <div>
            <p className="text-sm font-medium">{t.settings.signOutTitle}</p>
            <p className="text-xs text-muted-foreground">
              {t.settings.signOutDesc}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={handleSignOut}>
            {t.nav.signOut}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
