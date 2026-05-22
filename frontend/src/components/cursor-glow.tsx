"use client";

import { useEffect, useRef } from "react";

/** A soft light that trails the cursor. It paints in the gaps between the
 *  opaque content cards, giving empty space depth without adding decoration.
 *  Desktop only — touch devices have no cursor and gain nothing from it. */
export function CursorGlow() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    function onMove(e: MouseEvent) {
      // Coalesce moves to one paint per frame — mousemove fires far faster.
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        el!.style.setProperty("--x", `${e.clientX}px`);
        el!.style.setProperty("--y", `${e.clientY}px`);
      });
    }
    window.addEventListener("mousemove", onMove);
    return () => {
      window.removeEventListener("mousemove", onMove);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div
      ref={ref}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 hidden lg:block"
      style={{
        background:
          "radial-gradient(440px circle at var(--x, 50%) var(--y, -10%), hsl(var(--foreground) / 0.06), transparent 72%)",
      }}
    />
  );
}
