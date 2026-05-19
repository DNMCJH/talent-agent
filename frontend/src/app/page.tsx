"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/context";

export default function LandingPage() {
  const { status } = useSession();
  const router = useRouter();
  const { t, locale, toggleLocale } = useI18n();

  useEffect(() => {
    if (status === "authenticated") router.replace("/projects");
  }, [status, router]);

  if (status === "authenticated") return null;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b">
        <div className="container max-w-7xl mx-auto flex h-14 items-center justify-between px-6">
          <span className="font-semibold">Talent Agent</span>
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={toggleLocale} className="text-xs px-2">
              {locale === "en" ? "中文" : "EN"}
            </Button>
            <Link href="/login">
              <Button size="sm">{t.login.signIn}</Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="container max-w-7xl mx-auto px-6 py-24 text-center">
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight">
            {t.landing.hero}
          </h1>
          <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
            {t.landing.heroSub}
          </p>
          <div className="mt-8">
            <Link href="/login">
              <Button size="lg">{t.landing.getStarted}</Button>
            </Link>
          </div>
        </section>

        {/* Features */}
        <section className="border-t bg-muted/30">
          <div className="container max-w-7xl mx-auto px-6 py-16">
            <h2 className="text-2xl font-semibold text-center mb-12">
              {t.landing.features}
            </h2>
            <div className="grid sm:grid-cols-3 gap-8">
              <FeatureCard
                title={t.landing.feature1Title}
                desc={t.landing.feature1Desc}
              />
              <FeatureCard
                title={t.landing.feature2Title}
                desc={t.landing.feature2Desc}
              />
              <FeatureCard
                title={t.landing.feature3Title}
                desc={t.landing.feature3Desc}
              />
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t py-6 text-center text-sm text-muted-foreground">
        Built with Next.js, FastAPI, DeepSeek & Qdrant
      </footer>
    </div>
  );
}

function FeatureCard({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="rounded-lg border bg-background p-6">
      <h3 className="font-medium mb-2">{title}</h3>
      <p className="text-sm text-muted-foreground">{desc}</p>
    </div>
  );
}
