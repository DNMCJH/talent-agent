"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/context";

export function Nav() {
  const pathname = usePathname();
  const { data: session } = useSession();
  const { t, locale, toggleLocale } = useI18n();

  const links = [
    { href: "/projects", label: t.nav.projects },
    { href: "/match", label: t.nav.match },
    { href: "/interview", label: t.nav.interview },
  ];

  return (
    <header className="sticky top-0 z-10 bg-gradient-to-r from-zinc-900 via-zinc-800 to-zinc-900 text-white shadow-lg">
      <div className="container max-w-7xl mx-auto flex h-14 items-center justify-between px-6">
        <div className="flex items-center gap-10">
          <Link href="/" className="text-2xl font-bold tracking-tight">
            Talent Agent
          </Link>
          <nav className="flex gap-2">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "px-4 py-1.5 rounded-md text-[15px] transition-colors",
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
        <div className="flex items-center gap-3 text-sm">
          <button
            onClick={toggleLocale}
            className="px-2 py-1 rounded text-xs text-zinc-300 hover:text-white hover:bg-white/10 transition-colors"
          >
            {locale === "en" ? "中文" : "EN"}
          </button>
          {session?.githubLogin && (
            <span className="text-zinc-400">@{session.githubLogin}</span>
          )}
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="px-2 py-1 rounded text-sm text-zinc-300 hover:text-white hover:bg-white/10 transition-colors"
          >
            {t.nav.signOut}
          </button>
        </div>
      </div>
    </header>
  );
}
