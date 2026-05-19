"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";

type Status = "pending" | "ok" | "error";

function VerifyEmailInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<Status>("pending");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) {
      setStatus("error");
      setMessage("Missing verification token / 验证链接缺少 token");
      return;
    }
    fetch(`/api/backend/auth/verify-email?token=${encodeURIComponent(token)}`)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          setStatus("ok");
          setMessage(body.email ? `Verified ${body.email}` : "Verified");
        } else {
          setStatus("error");
          setMessage(body.detail || `Verification failed (${res.status})`);
        }
      })
      .catch(() => {
        setStatus("error");
        setMessage("Network error / 网络错误");
      });
  }, [searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {status === "pending" && <Loader2 className="h-5 w-5 animate-spin" />}
            {status === "ok" && <CheckCircle2 className="h-5 w-5 text-green-600" />}
            {status === "error" && <XCircle className="h-5 w-5 text-red-600" />}
            Email verification / 邮箱验证
          </CardTitle>
          <CardDescription className="text-sm pt-2">{message}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => router.push("/")} className="w-full">
            {status === "ok" ? "Continue / 继续" : "Back / 返回"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <VerifyEmailInner />
    </Suspense>
  );
}
