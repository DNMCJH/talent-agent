"use client";

import { signIn, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/context";

export default function LoginPage() {
  const { status } = useSession();
  const router = useRouter();
  const { t, locale, toggleLocale } = useI18n();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (status === "authenticated") router.replace("/projects");
  }, [status, router]);

  useEffect(() => {
    fetch("/api/auth/csrf").then(() => setReady(true)).catch(() => setReady(true));
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">{t.login.title}</CardTitle>
          <CardDescription>{t.login.subtitle}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button
            className="w-full"
            disabled={!ready}
            onClick={() => signIn("github", { callbackUrl: "/projects" })}
          >
            {t.login.signIn}
          </Button>
          <div className="text-center">
            <button
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
