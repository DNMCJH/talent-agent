"use client";

// Route-level error boundary — catches render/data errors in any page segment
// so an exception shows a recoverable screen instead of a blank white page.

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 px-6 text-center">
      <h2 className="text-lg font-semibold">出了点问题</h2>
      <p className="text-sm text-muted-foreground">
        页面加载失败，请重试。如果问题持续，请稍后再来。
      </p>
      <button
        onClick={reset}
        className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground"
      >
        重试
      </button>
    </div>
  );
}
