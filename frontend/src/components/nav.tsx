"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
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
    <header className="border-b bg-background sticky top-0 z-10">
      <div className="container max-w-7xl mx-auto flex h-16 items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <Link href="/" className="text-lg font-bold tracking-tight">
            Talent Agent
          </Link>
          <nav className="flex gap-5 text-sm font-medium">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "text-muted-foreground transition-colors hover:text-foreground",
                  pathname?.startsWith(l.href) && "text-foreground font-medium",
                )}
              >
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleLocale}
            className="text-xs px-2"
          >
            {locale === "en" ? "中文" : "EN"}
          </Button>
          {session?.githubLogin && (
            <span className="text-muted-foreground">@{session.githubLogin}</span>
          )}
          <Button variant="ghost" size="sm" onClick={() => signOut({ callbackUrl: "/login" })}>
            {t.nav.signOut}
          </Button>
        </div>
      </div>
    </header>
  );
}
