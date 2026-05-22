"use client";

import { useState, useRef, useEffect } from "react";
import { signOut, useSession } from "next-auth/react";
import { useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/i18n/context";

/** Avatar — the GitHub profile picture when signed in via GitHub, otherwise a
 *  monogram square in the app's mono palette. */
function Avatar({
  image,
  initial,
  size = "sm",
}: {
  image?: string | null;
  initial: string;
  size?: "sm" | "lg";
}) {
  const dim = size === "lg" ? "h-9 w-9" : "h-7 w-7";
  if (image) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={image}
        alt=""
        className={`${dim} rounded border object-cover`}
      />
    );
  }
  return (
    <span
      className={`${dim} grid place-items-center rounded bg-foreground font-mono text-xs font-medium text-background`}
    >
      {initial}
    </span>
  );
}

/** Top-right account control: a clickable avatar that opens a small menu
 *  showing the signed-in identity and a sign-out action. */
export function UserMenu() {
  const { data: session } = useSession();
  const { token, logout } = useAuth();
  const api = useApi();
  const { t } = useI18n();
  const [email, setEmail] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!token) return;
    api
      .get<{ email: string | null }>("/auth/me")
      .then((m) => setEmail(m.email))
      .catch(() => {});
  }, [token, api]);

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const githubLogin = session?.githubLogin;
  const image = session?.user?.image;
  const displayName = githubLogin || email || "User";
  const initial = displayName.charAt(0).toUpperCase();

  function handleSignOut() {
    if (token) {
      logout();
      window.location.href = "/login";
    } else {
      signOut({ callbackUrl: "/login" });
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center transition-opacity hover:opacity-80"
        aria-label="Account menu"
      >
        <Avatar image={image} initial={initial} />
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-56 border bg-background shadow-lg">
          <div className="flex items-center gap-2.5 border-b px-3 py-3">
            <Avatar image={image} initial={initial} size="lg" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium tracking-tight">
                {displayName}
              </p>
              <p className="truncate font-mono text-xs text-muted-foreground">
                {githubLogin ? "GitHub" : email || ""}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleSignOut}
            className="w-full px-3 py-2.5 text-left text-sm text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
          >
            {t.nav.signOut}
          </button>
        </div>
      )}
    </div>
  );
}
