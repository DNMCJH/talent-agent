"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/context";
import { UserMenu } from "@/components/user-menu";

export function Nav() {
  const pathname = usePathname();
  const { t, locale, toggleLocale } = useI18n();

  const links = [
    { href: "/", label: t.nav.home },
    { href: "/projects", label: t.nav.projects },
    { href: "/match", label: t.nav.match },
    { href: "/interview", label: t.nav.interview },
    { href: "/resume-upload", label: t.nav.resumeUpload },
    { href: "/quiz", label: t.nav.quiz },
    { href: "/applications", label: t.nav.applications },
  ];

  return (
    <header className="sticky top-0 z-10 border-b bg-background">
      <div className="container max-w-7xl mx-auto flex h-14 items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-4 sm:gap-8 min-w-0">
          <Link href="/" className="flex items-center gap-2 shrink-0">
            <span className="grid h-6 w-6 place-items-center bg-foreground text-background font-mono text-xs font-bold">
              TA
            </span>
            <span className="hidden sm:inline text-sm font-medium tracking-tight">
              Talent Agent
            </span>
          </Link>
          <nav className="flex gap-0.5 sm:gap-1 overflow-x-auto">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "px-2 sm:px-3 py-1.5 rounded-none text-xs sm:text-sm whitespace-nowrap transition-colors",
                  (l.href === "/" ? pathname === "/" : pathname?.startsWith(l.href))
                    ? "font-medium text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm shrink-0">
          <button
            type="button"
            onClick={toggleLocale}
            className="px-1 py-1 font-mono text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {locale === "en" ? "中文" : "EN"}
          </button>
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
