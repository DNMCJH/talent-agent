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
    <header className="sticky top-0 z-10 bg-gradient-to-r from-zinc-900 via-zinc-800 to-zinc-900 text-white shadow-lg">
      <div className="container max-w-7xl mx-auto flex h-14 items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-4 sm:gap-10 min-w-0">
          <Link href="/" className="text-lg sm:text-2xl font-bold tracking-tight shrink-0">
            Talent Agent
          </Link>
          <nav className="flex gap-1 sm:gap-2 overflow-x-auto">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "px-2 sm:px-4 py-1.5 rounded-md text-xs sm:text-[15px] whitespace-nowrap transition-colors",
                  pathname?.startsWith(l.href)
                    ? "bg-white/15 text-white font-semibold"
                    : "text-zinc-300 hover:text-white hover:bg-white/10",
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
            className="px-2 py-1 rounded text-xs text-zinc-300 hover:text-white hover:bg-white/10 transition-colors"
          >
            {locale === "en" ? "中文" : "EN"}
          </button>
          {session?.githubLogin && (
            <span className="hidden sm:inline text-zinc-400">@{session.githubLogin}</span>
          )}
          <button
            type="button"
            onClick={handleSignOut}
            className="px-2 py-1 rounded text-xs sm:text-sm text-zinc-300 hover:text-white hover:bg-white/10 transition-colors"
          >
            {t.nav.signOut}
          </button>
        </div>
      </div>
    </header>
  );
}
