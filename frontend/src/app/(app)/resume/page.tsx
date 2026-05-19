"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { useApi } from "@/lib/api";
import { openSSE } from "@/lib/sse";
import { useI18n } from "@/i18n/context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Loader2, Copy, Check, ArrowLeft } from "lucide-react";

type Project = { id: number; name: string };

type ResumeBundle = {
  project_title: string;
  stack_line: string;
  star_bullets: string[];
  tailored_for_role: string;
};

type ProgressItem = {
  index: number;
  total: number;
  project_name: string;
  bundle: ResumeBundle | null; // null while generating
};

export default function FullResumePage() {
  const api = useApi();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t, locale } = useI18n();
  const sseCloseRef = useRef<(() => void) | null>(null);

  const { data: allProjects } = useSWR<Project[]>(
    api.token ? "/projects" : null,
    () => api.get<Project[]>("/projects"),
  );

  // JD comes from sessionStorage (saved on the match page) or URL.
  const [jd, setJd] = useState("");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [items, setItems] = useState<ProgressItem[]>([]);
  const [running, setRunning] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const urlJd = searchParams.get("jd");
    const urlIds = searchParams.get("project_ids");
    if (urlIds) {
      setSelectedIds(urlIds.split(",").map(Number).filter((n) => !isNaN(n)));
    }
    if (urlJd) {
      setJd(urlJd);
      return;
    }
    try {
      const raw = sessionStorage.getItem("talent-agent.match.v1");
      if (raw) {
        const parsed = JSON.parse(raw) as { jd?: string };
        if (parsed.jd) setJd(parsed.jd);
      }
    } catch {
      // ignore
    }
  }, [searchParams]);

  useEffect(() => {
    return () => sseCloseRef.current?.();
  }, []);

  function toggleProject(id: number) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  function selectAll() {
    if (!allProjects) return;
    setSelectedIds(
      selectedIds.length === allProjects.length ? [] : allProjects.map((p) => p.id),
    );
  }

  function start() {
    if (!api.token || !jd.trim() || selectedIds.length === 0) return;
    setRunning(true);
    setItems([]);

    sseCloseRef.current?.();
    sseCloseRef.current = openSSE(
      "/resume/multi/stream",
      api.token,
      {
        project_ids: selectedIds.join(","),
        raw_jd: jd,
        language: locale,
      },
      {
        onEvent: (e) => {
          if (e.type === "delta") return;
          if (e.type === "error") {
            toast.error(e.message);
            setRunning(false);
            return;
          }
          // Custom events for this stream:
          const ev = e as unknown as
            | { type: "progress"; index: number; total: number; project_name: string }
            | { type: "bundle"; index: number; project_name: string; bundle: ResumeBundle }
            | { type: "done"; total: number };
          if (ev.type === "progress") {
            setItems((prev) => {
              const next = [...prev];
              next[ev.index] = {
                index: ev.index,
                total: ev.total,
                project_name: ev.project_name,
                bundle: null,
              };
              return next;
            });
          } else if (ev.type === "bundle") {
            setItems((prev) => {
              const next = [...prev];
              const existing = next[ev.index];
              next[ev.index] = {
                index: ev.index,
                total: existing?.total ?? 0,
                project_name: ev.project_name,
                bundle: ev.bundle,
              };
              return next;
            });
          } else if (ev.type === "done") {
            setRunning(false);
          }
        },
        onNetworkError: () => {
          toast.error(locale === "zh" ? "连接中断，请重试" : "Connection lost, please retry");
          setRunning(false);
        },
      },
    );
  }

  function copyAll() {
    const text = items
      .filter((it) => it.bundle)
      .map((it) => {
        const b = it.bundle!;
        return `${b.project_title}\n${b.stack_line}\n${b.star_bullets.map((x) => `• ${x}`).join("\n")}`;
      })
      .join("\n\n---\n\n");
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const hint = locale === "zh"
    ? "为选中的多个项目按顺序生成简历要点。生成期间你可以滚动查看已生成的部分。"
    : "Generate resume bullets for selected projects in order. You can scroll the already-generated bundles while the rest is still streaming.";

  const finishedCount = items.filter((it) => it.bundle).length;
  const totalCount = items.length > 0 ? items[0]?.total ?? items.length : 0;

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => router.push("/match")}>
          <ArrowLeft className="h-4 w-4 mr-1" />
          {locale === "zh" ? "返回匹配" : "Back to match"}
        </Button>
      </div>

      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {locale === "zh" ? "完整简历生成" : "Full resume generation"}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">{hint}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {locale === "zh" ? "选择项目" : "Select projects"}
          </CardTitle>
          <CardDescription className="text-xs">
            {locale === "zh"
              ? `JD 长度：${jd.length} 字符${jd.trim() ? "" : "（请先在匹配页填 JD）"}`
              : `JD: ${jd.length} chars${jd.trim() ? "" : " (set JD on match page first)"}`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {!allProjects || allProjects.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {locale === "zh" ? "暂无项目" : "No projects yet"}
            </p>
          ) : (
            <>
              <button
                type="button"
                onClick={selectAll}
                className="text-xs text-primary hover:underline"
                disabled={running}
              >
                {locale === "zh" ? "全选" : "Select all"}
                {selectedIds.length === allProjects.length ? " ✓" : ""}
              </button>
              <div className="border rounded-md max-h-48 overflow-y-auto">
                {allProjects.map((p) => (
                  <label
                    key={p.id}
                    className="flex items-center gap-2 px-3 py-2 hover:bg-muted/50 cursor-pointer text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(p.id)}
                      onChange={() => toggleProject(p.id)}
                      disabled={running}
                      className="rounded"
                    />
                    {p.name}
                  </label>
                ))}
              </div>
            </>
          )}
          <Button
            onClick={start}
            disabled={running || !jd.trim() || selectedIds.length === 0}
          >
            {running && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {running
              ? locale === "zh"
                ? `生成中… (${finishedCount}/${totalCount})`
                : `Generating… (${finishedCount}/${totalCount})`
              : locale === "zh"
                ? "开始生成"
                : "Start"}
          </Button>
        </CardContent>
      </Card>

      {items.length > 0 && (
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-muted-foreground">
            {locale === "zh" ? `已生成 ${finishedCount} / ${totalCount}` : `Done ${finishedCount} / ${totalCount}`}
          </h2>
          <Button size="sm" variant="outline" onClick={copyAll} disabled={finishedCount === 0}>
            {copied ? <Check className="mr-1.5 h-3.5 w-3.5" /> : <Copy className="mr-1.5 h-3.5 w-3.5" />}
            {copied ? t.match.copied : (locale === "zh" ? "复制全部" : "Copy all")}
          </Button>
        </div>
      )}

      <div className="space-y-4">
        {items.map((it) => (
          <Card key={`${it.index}-${it.project_name}`}>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Badge variant="outline" className="text-xs">{it.index + 1}</Badge>
                {it.bundle?.project_title || it.project_name}
              </CardTitle>
              {it.bundle && (
                <CardDescription className="text-xs">
                  {t.match.resumeStack}: {it.bundle.stack_line}
                </CardDescription>
              )}
            </CardHeader>
            <CardContent>
              {it.bundle ? (
                <ul className="space-y-2">
                  {it.bundle.star_bullets.map((b, i) => (
                    <li
                      key={i}
                      className="text-sm pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-muted-foreground"
                    >
                      {b}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground italic flex items-center gap-2">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  {locale === "zh" ? "AI 正在生成…" : "AI is generating…"}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
