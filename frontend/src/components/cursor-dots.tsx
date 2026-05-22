"use client";

import { useEffect, useRef } from "react";

/** Spacing of the dot grid — matches the CSS fallback grid in globals.css. */
const SPACING = 24;
/** How far the cursor's pull reaches, in px. */
const RADIUS = 170;
/** Max fraction of the way a dot slides toward the cursor. */
const PULL = 0.34;

/** An interactive dot field: the background grid gathers toward the cursor.
 *  Each dot within RADIUS slides toward the pointer, grows, and darkens, with
 *  an ease-in falloff so the pull concentrates into a focal cluster.
 *
 *  Canvas-based because CSS background dots are fixed and cannot move. Only
 *  runs on fine-pointer desktops; touch devices keep the static CSS grid. */
export function CursorDots() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Skip on touch / coarse pointers and when the user prefers reduced
    // motion — the static CSS dot grid stays as the fallback.
    const desktop = window.matchMedia("(min-width: 1024px) and (pointer: fine)");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!desktop.matches || reduced.matches) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // This canvas replaces the CSS dot grid — suppress it to avoid doubling.
    document.documentElement.classList.add("cursor-dots");

    const muted = `hsl(${getComputedStyle(document.documentElement)
      .getPropertyValue("--muted-foreground")
      .trim()})`;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let w = 0;
    let h = 0;
    // Cursor target + eased position (eased so the field trails smoothly).
    let cx = -9999;
    let cy = -9999;
    let ex = cx;
    let ey = cy;
    let lastMove = 0;
    let raf = 0;
    let running = false;

    function resize() {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas!.width = w * dpr;
      canvas!.height = h * dpr;
      canvas!.style.width = `${w}px`;
      canvas!.style.height = `${h}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      render();
    }

    function render() {
      ctx!.clearRect(0, 0, w, h);
      ctx!.fillStyle = muted;
      for (let x = SPACING / 2; x < w; x += SPACING) {
        for (let y = SPACING / 2; y < h; y += SPACING) {
          const dx = ex - x;
          const dy = ey - y;
          const dist = Math.hypot(dx, dy);
          let px = x;
          let py = y;
          let r = 1;
          let alpha = 0.2;
          if (dist < RADIUS) {
            const f = 1 - dist / RADIUS;
            const ease = f * f; // concentrate the pull near the cursor
            px = x + dx * PULL * ease;
            py = y + dy * PULL * ease;
            r = 1 + ease * 1.7;
            alpha = 0.2 + 0.65 * f;
          }
          ctx!.globalAlpha = alpha;
          ctx!.beginPath();
          ctx!.arc(px, py, r, 0, Math.PI * 2);
          ctx!.fill();
        }
      }
      ctx!.globalAlpha = 1;
    }

    function loop() {
      ex += (cx - ex) * 0.15;
      ey += (cy - ey) * 0.15;
      render();
      const settled =
        Math.abs(cx - ex) < 0.4 && Math.abs(cy - ey) < 0.4;
      // Idle once the field has caught up and the cursor has paused —
      // restarts on the next move so we don't paint a static frame forever.
      if (settled && performance.now() - lastMove > 140) {
        running = false;
        return;
      }
      raf = requestAnimationFrame(loop);
    }

    function start() {
      if (running) return;
      running = true;
      raf = requestAnimationFrame(loop);
    }

    function onMove(e: MouseEvent) {
      cx = e.clientX;
      cy = e.clientY;
      lastMove = performance.now();
      start();
    }
    function onLeave() {
      // Send the cursor off-screen so dots ease back to rest.
      cx = -9999;
      cy = -9999;
      lastMove = performance.now();
      start();
    }

    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", onMove);
    document.addEventListener("mouseleave", onLeave);

    return () => {
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseleave", onLeave);
      if (raf) cancelAnimationFrame(raf);
      document.documentElement.classList.remove("cursor-dots");
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0"
    />
  );
}
