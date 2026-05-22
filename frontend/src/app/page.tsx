"use client";

import { useSession } from "next-auth/react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { AppShell } from "@/components/app-shell";
import { HomeWorkbench } from "@/components/home-workbench";
import { CursorGlow } from "@/components/cursor-glow";
import { useI18n } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

export default function RootPage() {
  const { status } = useSession();
  const { token, loading: authLoading } = useAuth();
  const { t, locale, toggleLocale } = useI18n();

  const isLoading = status === "loading" || authLoading;
  const isAuthed = status === "authenticated" || !!token;

  // Hold render until auth resolves so a signed-in user never flashes the
  // marketing page (and vice versa).
  if (isLoading) return null;

  // Signed in: the homepage is the workbench, not the landing page.
  if (isAuthed) {
    return (
      <AppShell>
        <HomeWorkbench />
      </AppShell>
    );
  }

  const features = [
    { title: t.landing.feature1Title, desc: t.landing.feature1Desc },
    { title: t.landing.feature2Title, desc: t.landing.feature2Desc },
    { title: t.landing.feature3Title, desc: t.landing.feature3Desc },
  ];

  // A static, illustrative match result — shows what the product does
  // instead of leaving the right fold as empty decoration.
  const demoRows = [
    { rank: "01", name: "rag-pipeline", score: 92 },
    { rank: "02", name: "cv-detector", score: 74 },
    { rank: "03", name: "data-dashboard", score: 58 },
  ];

  return (
    <div className="relative min-h-screen flex flex-col">
      <CursorGlow />
      {/* Header — full-bleed border, content aligned to a 1200px column */}
      <header className="relative z-[1] border-b">
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

      <main className="relative z-[1] flex-1">
        {/* Hero — left-aligned, editorial. Content is vertically centered so
            the fold reads as a balanced composition, not a top-heavy block. */}
        <section className="border-b">
          <div className="mx-auto grid max-w-[1200px] grid-cols-1 lg:grid-cols-12">
            <div className="col-span-1 flex flex-col justify-center px-6 py-20 lg:col-span-7 lg:border-r lg:py-28">
              <p className="mb-6 font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
                {locale === "en" ? "AI Career Agent" : "AI 求职助手"}
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

            {/* Right fold — a static product demo, not decoration:
                a mock JD-to-ranking result the way the match page renders it. */}
            <div className="hidden lg:col-span-5 lg:flex lg:items-center lg:justify-center lg:p-12">
              <div className="w-full max-w-sm border bg-background">
                <div className="flex items-center justify-between border-b px-4 py-2.5">
                  <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    {locale === "en" ? "Match preview" : "匹配预览"}
                  </span>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {locale === "en" ? "3 projects" : "3 个项目"}
                  </span>
                </div>
                <div className="border-b px-4 py-3">
                  <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {locale === "en" ? "Target role" : "目标岗位"}
                  </p>
                  <p className="mt-1 text-sm font-medium tracking-tight">
                    {locale === "en"
                      ? "ML Engineer · Intern"
                      : "机器学习工程师 · 实习"}
                  </p>
                </div>
                {demoRows.map((r) => (
                  <div
                    key={r.rank}
                    className="flex items-center gap-3 border-b px-4 py-3 last:border-b-0"
                  >
                    <span className="font-mono text-xs text-muted-foreground">
                      {r.rank}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-mono text-xs">{r.name}</p>
                      <div className="mt-1.5 h-1 w-full bg-muted">
                        <div
                          className="h-1 bg-foreground"
                          style={{ width: `${r.score}%` }}
                        />
                      </div>
                    </div>
                    <span className="font-mono text-xs tabular-nums text-muted-foreground">
                      {r.score}
                    </span>
                  </div>
                ))}
              </div>
            </div>
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
                className="grid grid-cols-1 gap-2 border-b px-6 py-9 transition-colors hover:bg-muted/40 sm:grid-cols-12 sm:gap-6"
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

        {/* Closing CTA band — gives the page a deliberate ending instead of
            trailing off into the footer. */}
        <section className="border-b">
          <div className="mx-auto flex max-w-[1200px] flex-col items-start gap-6 px-6 py-16 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
                {t.landing.ctaEyebrow}
              </p>
              <h2 className="mt-2 max-w-md text-2xl font-semibold tracking-tight sm:text-3xl">
                {t.landing.ctaTitle}
              </h2>
            </div>
            <Link href="/login">
              <Button size="lg" className="h-11 rounded-none px-7">
                {t.landing.getStarted}
              </Button>
            </Link>
          </div>
        </section>
      </main>

      <footer className="relative z-[1] border-t">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-2 px-6 py-8 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-sm text-muted-foreground">Talent Agent</span>
          <span className="font-mono text-xs text-muted-foreground">
            Next.js · FastAPI · DeepSeek · Qdrant
          </span>
        </div>
      </footer>
    </div>
  );
}
