"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

export default function LandingPage() {
  const { status } = useSession();
  const { token } = useAuth();
  const router = useRouter();
  const { t, locale, toggleLocale } = useI18n();

  useEffect(() => {
    if (status === "authenticated" || token) router.replace("/projects");
  }, [status, token, router]);

  if (status === "authenticated" || token) return null;

  const features = [
    { title: t.landing.feature1Title, desc: t.landing.feature1Desc },
    { title: t.landing.feature2Title, desc: t.landing.feature2Desc },
    { title: t.landing.feature3Title, desc: t.landing.feature3Desc },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header — full-bleed border, content aligned to a 1200px column */}
      <header className="border-b">
        <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-6">
          <div className="flex items-center gap-2.5">
            <span className="grid h-6 w-6 place-items-center bg-foreground text-background font-mono text-xs font-bold">
              TA
            </span>
            <span className="text-sm font-medium tracking-tight">
              Talent Agent
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleLocale}
              className="h-8 font-mono text-xs text-muted-foreground"
            >
              {locale === "en" ? "中文" : "EN"}
            </Button>
            <Link href="/login">
              <Button size="sm" className="h-8 rounded-none text-xs">
                {t.login.signIn}
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero — left-aligned, editorial. Right column carries a quiet
            blueprint grid so the fold isn't dead whitespace. */}
        <section className="border-b">
          <div className="mx-auto grid max-w-[1200px] grid-cols-1 lg:grid-cols-12">
            <div className="col-span-1 px-6 py-20 lg:col-span-7 lg:border-r lg:py-32">
              <p className="mb-6 font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
                {locale === "en"
                  ? "AI Career Agent"
                  : "AI 求职助手"}
              </p>
              <h1 className="max-w-xl text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl">
                {t.landing.hero}
              </h1>
              <p className="mt-6 max-w-md text-base leading-relaxed text-muted-foreground">
                {t.landing.heroSub}
              </p>
              <div className="mt-10 flex items-center gap-4">
                <Link href="/login">
                  <Button size="lg" className="h-11 rounded-none px-7">
                    {t.landing.getStarted}
                  </Button>
                </Link>
                <span className="font-mono text-xs text-muted-foreground">
                  {locale === "en"
                    ? "Free · GitHub or email"
                    : "免费 · GitHub 或邮箱登录"}
                </span>
              </div>
            </div>
            <div className="hidden lg:col-span-5 lg:block grid-lines" />
          </div>
        </section>

        {/* Features — numbered rows, not a deck of identical cards.
            Each row is divided by a hairline, vercel.com/design style. */}
        <section>
          <div className="mx-auto max-w-[1200px]">
            <div className="border-b px-6 py-5">
              <h2 className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
                {t.landing.features}
              </h2>
            </div>
            {features.map((f, i) => (
              <div
                key={f.title}
                className="grid grid-cols-1 gap-2 border-b px-6 py-10 transition-colors hover:bg-muted/40 sm:grid-cols-12 sm:gap-6"
              >
                <span className="font-mono text-sm text-muted-foreground sm:col-span-1">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h3 className="text-lg font-medium tracking-tight sm:col-span-4">
                  {f.title}
                </h3>
                <p className="max-w-md text-sm leading-relaxed text-muted-foreground sm:col-span-7">
                  {f.desc}
                </p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-2 px-6 py-8 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-sm text-muted-foreground">
            Talent Agent
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            Next.js · FastAPI · DeepSeek · Qdrant
          </span>
        </div>
      </footer>
    </div>
  );
}
