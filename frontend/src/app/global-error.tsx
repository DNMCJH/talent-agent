"use client";

// Catches errors thrown in the root layout itself, which a route-level
// error.tsx cannot reach. Must render its own <html>/<body>.

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        <div className="min-h-screen flex flex-col items-center justify-center gap-4 px-6 text-center">
          <h2 className="text-lg font-semibold">应用加载失败</h2>
          <p className="text-sm text-muted-foreground">
            请刷新页面重试。错误代码：{error.digest ?? "unknown"}
          </p>
          <button
            onClick={reset}
            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground"
          >
            重试
          </button>
        </div>
      </body>
    </html>
  );
}
