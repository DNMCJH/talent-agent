"use client";

import { useEffect, useRef } from "react";

/** Spacing of the dot grid — matches the CSS fallback grid in globals.css. */
const SPACING = 24;
/** How far the spotlight reaches, in px. */
const RADIUS = 190;
/** Max parallax shift of the whole grid, in px. */
const PARALLAX = 7;

/** An interactive dot field: a soft spotlight follows the cursor, lighting
 *  up dots within its radius (brighter, slightly larger), while the whole
 *  grid drifts opposite to the cursor for a subtle sense of depth. The dots
 *  themselves never move from the grid — restrained, "lit" rather than
 *  distorted.
 *
 *  Canvas-based because the parallax offset and per-dot lighting can't be
 *  done with a static CSS background. Only runs on fine-pointer desktops;
 *  touch devices keep the static CSS grid. */
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

    // Two theme colors: dots rest at the faint CSS-grid color (--border) and
    // brighten toward --muted-foreground inside the spotlight.
    function parseHsl(v: string): [number, number, number] {
      const m = v
        .trim()
        .match(/([\d.]+)\s+([\d.]+)%\s+([\d.]+)%/);
      return m ? [+m[1], +m[2], +m[3]] : [0, 0, 50];
    }
    const rootStyle = getComputedStyle(document.documentElement);
    const restColor = parseHsl(rootStyle.getPropertyValue("--border"));
    const litColor = parseHsl(rootStyle.getPropertyValue("--muted-foreground"));

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let w = 0;
    let h = 0;
    // Cursor target (-9999 = off-screen) and its eased position; the spotlight
    // and parallax both trail this eased point so the field moves smoothly.
    let cx = -9999;
    let cy = -9999;
    let ex = cx;
    let ey = cy;
    // Eased parallax offset of the whole grid.
    let ox = 0;
    let oy = 0;
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
      const lit = ex > -9000;
      for (let x = SPACING / 2; x < w; x += SPACING) {
        for (let y = SPACING / 2; y < h; y += SPACING) {
          // Parallax: the dot is drawn shifted; the spotlight test uses the
          // drawn position so light tracks what the eye sees.
          const px = x + ox;
          const py = y + oy;
          let r = 1;
          let t = 0; // 0 = resting color, 1 = fully lit
          if (lit) {
            const dist = Math.hypot(ex - px, ey - py);
            if (dist < RADIUS) {
              const f = 1 - dist / RADIUS;
              const ease = f * f; // soft circular falloff
              r = 1 + ease * 1.1;
              t = ease;
            }
          }
          const hh = restColor[0] + (litColor[0] - restColor[0]) * t;
          const ss = restColor[1] + (litColor[1] - restColor[1]) * t;
          const ll = restColor[2] + (litColor[2] - restColor[2]) * t;
          ctx!.fillStyle = `hsl(${hh} ${ss}% ${ll}%)`;
          ctx!.beginPath();
          ctx!.arc(px, py, r, 0, Math.PI * 2);
          ctx!.fill();
        }
      }
    }

    function loop() {
      ex += (cx - ex) * 0.12;
      ey += (cy - ey) * 0.12;
      // Parallax target: cursor offset from viewport center, inverted. Off
      // screen → ease back to a centered (zero) offset.
      const targetOx = cx < -9000 ? 0 : -((cx / w) - 0.5) * 2 * PARALLAX;
      const targetOy = cy < -9000 ? 0 : -((cy / h) - 0.5) * 2 * PARALLAX;
      ox += (targetOx - ox) * 0.08;
      oy += (targetOy - oy) * 0.08;
      render();
      const settled =
        Math.abs(cx - ex) < 0.4 &&
        Math.abs(cy - ey) < 0.4 &&
        Math.abs(targetOx - ox) < 0.1 &&
        Math.abs(targetOy - oy) < 0.1;
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
      // Send the cursor off-screen so the spotlight fades and the grid
      // eases back to its centered, un-parallaxed rest position.
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
