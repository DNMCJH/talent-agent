"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/context";
import { cn } from "@/lib/utils";

type Project = { id: number; name: string };

/** State-aware homepage for signed-in users: a new-user guide when the
 *  account has no projects, otherwise a workbench of the four modules. */
export function HomeWorkbench() {
  const api = useApi();
  const { t } = useI18n();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .get<Project[]>("/projects")
      .then((p) => active && setProjects(p))
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, [api]);

  if (projects === null && !failed) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        {t.home.loading}
      </div>
    );
  }

  // On a failed fetch, fall back to the workbench (the entry hub) rather than
  // the new-user guide — an existing user must not be told to "import first".
  if (failed) return <Workbench count={null} />;
  return projects!.length === 0 ? (
    <NewUserGuide />
  ) : (
    <Workbench count={projects!.length} />
  );
}

function NewUserGuide() {
  const { t } = useI18n();
  const steps = [
    {
      n: "01",
      title: t.home.step1,
      desc: t.home.step1Desc,
      href: "/projects",
      cta: t.home.step1Cta,
      active: true,
    },
    { n: "02", title: t.home.step2, desc: t.home.step2Desc, active: false },
    { n: "03", title: t.home.step3, desc: t.home.step3Desc, active: false },
  ];
  return (
    <div className="mx-auto max-w-3xl">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
        {t.home.getStarted}
      </p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">
        {t.home.guideTitle}
      </h1>
      <div className="mt-6 border">
        {steps.map((s) => (
          <div
            key={s.n}
            className={cn(
              "grid grid-cols-12 items-center gap-4 border-b px-5 py-6 last:border-b-0",
              !s.active && "opacity-55",
            )}
          >
            <span className="col-span-1 font-mono text-sm text-muted-foreground">
              {s.n}
            </span>
            <div className="col-span-8">
              <h3 className="text-base font-medium tracking-tight">{s.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{s.desc}</p>
            </div>
            <div className="col-span-3 flex justify-end">
              {s.active && s.href && (
                <Link href={s.href}>
                  <Button size="sm" className="rounded-none">
                    {s.cta}
                    <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                  </Button>
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Workbench({ count }: { count: number | null }) {
  const { t } = useI18n();
  const rows = [
    {
      n: "01",
      title: t.home.interviewRow,
      desc: t.home.interviewRowDesc,
      href: "/interview",
    },
    { n: "02", title: t.home.quizRow, desc: t.home.quizRowDesc, href: "/quiz" },
    {
      n: "03",
      title: t.home.projectsRow,
      desc: t.home.projectsRowDesc,
      href: "/projects",
    },
  ];
  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
          {t.home.workbench}
        </span>
        {count !== null && (
          <span className="font-mono text-xs text-muted-foreground">
            {t.home.projectCount.replace("{n}", String(count))}
          </span>
        )}
      </div>

      {/* Primary action — matching is the high-frequency action, so it gets
          a solid block instead of sharing a row with the rest. */}
      <Link
        href="/match"
        className="mt-3 block border bg-foreground p-6 text-background transition-opacity hover:opacity-90 sm:p-8"
      >
        <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
          {t.home.matchTitle}
        </h2>
        <p className="mt-2 max-w-md text-sm text-background/70">
          {t.home.matchDesc}
        </p>
        <span className="mt-5 inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider">
          {t.home.matchCta}
          <ArrowRight className="h-3.5 w-3.5" />
        </span>
      </Link>

      {/* Secondary modules — numbered rows, same language as the landing. */}
      <p className="mt-7 mb-2 font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
        {t.home.continue}
      </p>
      <div className="border">
        {rows.map((r) => (
          <Link
            key={r.n}
            href={r.href}
            className="group grid grid-cols-12 items-center gap-4 border-b px-5 py-5 transition-colors last:border-b-0 hover:bg-muted/40"
          >
            <span className="col-span-1 font-mono text-sm text-muted-foreground">
              {r.n}
            </span>
            <div className="col-span-9">
              <h3 className="text-sm font-medium tracking-tight">{r.title}</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">{r.desc}</p>
            </div>
            <div className="col-span-2 flex justify-end">
              <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
