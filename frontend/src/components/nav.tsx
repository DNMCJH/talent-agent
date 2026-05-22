"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

export function Nav() {
  const pathname = usePathname();
  const { data: session } = useSession();
  const { token, logout } = useAuth();
  const { t, locale, toggleLocale } = useI18n();

  const links = [
    { href: "/projects", label: t.nav.projects },
    { href: "/match", label: t.nav.match },
    { href: "/interview", label: t.nav.interview },
    { href: "/resume-upload", label: t.nav.resumeUpload },
    { href: "/quiz", label: t.nav.quiz },
  ];

  function handleSignOut() {
    if (token) {
      logout();
      window.location.href = "/login";
    } else {
      signOut({ callbackUrl: "/login" });
    }
  }

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
                  pathname?.startsWith(l.href)
                    ? "font-medium text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 text-sm shrink-0">
          <button
            type="button"
            onClick={toggleLocale}
            className="px-2 py-1 font-mono text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {locale === "en" ? "中文" : "EN"}
          </button>
          {session?.githubLogin && (
            <span className="hidden sm:inline font-mono text-xs text-muted-foreground">
              @{session.githubLogin}
            </span>
          )}
          <button
            type="button"
            onClick={handleSignOut}
            className="px-2 py-1 text-xs sm:text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            {t.nav.signOut}
          </button>
        </div>
      </div>
    </header>
  );
}
