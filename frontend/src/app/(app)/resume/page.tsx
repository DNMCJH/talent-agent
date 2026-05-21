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
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Loader2, Copy, Check, ArrowLeft, Pencil, Trash2, Plus, RotateCcw } from "lucide-react";
import { copyToClipboard } from "@/lib/clipboard";

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
  originalBundle?: ResumeBundle | null; // snapshot for reset
  edited?: boolean;
};

const STORAGE_KEY = "talent-agent.resume.v1";

type SavedState = {
  jd: string;
  selectedIds: number[];
  items: ProgressItem[];
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
    // Priority: URL params -> saved resume state -> match-page JD.
    const urlJd = searchParams.get("jd");
    const urlIds = searchParams.get("project_ids");
    if (urlIds) {
      setSelectedIds(urlIds.split(",").map(Number).filter((n) => !isNaN(n)));
    }
    if (urlJd) {
      setJd(urlJd);
    }
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved) as SavedState;
        if (parsed.items?.length) setItems(parsed.items);
        if (!urlIds && parsed.selectedIds?.length) setSelectedIds(parsed.selectedIds);
        if (!urlJd && parsed.jd) {
          setJd(parsed.jd);
          return;
        }
      }
    } catch {
      // ignore corrupted storage
    }
    if (urlJd) return;
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

  // Persist resume state (items + jd + selectedIds) to sessionStorage.
  // Only persist completed bundles to avoid restoring half-streamed state.
  useEffect(() => {
    if (items.length === 0) return;
    const allDone = items.every((it) => it.bundle !== null);
    if (!allDone) return;
    try {
      const payload: SavedState = { jd, selectedIds, items };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch {
      // quota or serialization errors are non-fatal
    }
  }, [items, jd, selectedIds]);

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
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }

    sseCloseRef.current?.();
    sseCloseRef.current = openSSE(
      "/resume/multi/stream/prepare",
      "/resume/multi/stream",
      api.token,
      {
        project_ids: selectedIds,
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
                originalBundle: structuredClone(ev.bundle),
                edited: false,
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

  function updateBundle(index: number, patch: Partial<ResumeBundle>) {
    setItems((prev) => {
      const next = [...prev];
      const it = next[index];
      if (!it?.bundle) return prev;
      next[index] = {
        ...it,
        bundle: { ...it.bundle, ...patch },
        edited: true,
      };
      return next;
    });
  }

  function updateBullet(index: number, bulletIdx: number, value: string) {
    setItems((prev) => {
      const next = [...prev];
      const it = next[index];
      if (!it?.bundle) return prev;
      const bullets = [...it.bundle.star_bullets];
      bullets[bulletIdx] = value;
      next[index] = {
        ...it,
        bundle: { ...it.bundle, star_bullets: bullets },
        edited: true,
      };
      return next;
    });
  }

  function deleteBullet(index: number, bulletIdx: number) {
    if (!confirm(t.resume.deleteBulletConfirm)) return;
    setItems((prev) => {
      const next = [...prev];
      const it = next[index];
      if (!it?.bundle) return prev;
      const bullets = it.bundle.star_bullets.filter((_, i) => i !== bulletIdx);
      next[index] = {
        ...it,
        bundle: { ...it.bundle, star_bullets: bullets },
        edited: true,
      };
      return next;
    });
  }

  function addBullet(index: number) {
    setItems((prev) => {
      const next = [...prev];
      const it = next[index];
      if (!it?.bundle) return prev;
      next[index] = {
        ...it,
        bundle: { ...it.bundle, star_bullets: [...it.bundle.star_bullets, ""] },
        edited: true,
      };
      return next;
    });
  }

  function resetBundle(index: number) {
    if (!confirm(t.resume.resetConfirm)) return;
    setItems((prev) => {
      const next = [...prev];
      const it = next[index];
      if (!it?.originalBundle) return prev;
      next[index] = {
        ...it,
        bundle: structuredClone(it.originalBundle),
        edited: false,
      };
      return next;
    });
  }

  async function copyAll() {
    const text = items
      .filter((it) => it.bundle)
      .map((it) => {
        const b = it.bundle!;
        return `${b.project_title}\n${b.stack_line}\n${b.star_bullets.map((x) => `• ${x}`).join("\n")}`;
      })
      .join("\n\n---\n\n");
    if (!text) return;
    const ok = await copyToClipboard(text);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } else {
      toast.error(locale === "zh" ? "复制失败，请手动选中复制" : "Copy failed, please select and copy manually");
    }
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
          <EditableBundleCard
            key={`${it.index}-${it.project_name}`}
            item={it}
            stackLabel={t.match.resumeStack}
            generating={locale === "zh" ? "AI 正在生成…" : "AI is generating…"}
            onUpdateBundle={(patch) => updateBundle(it.index, patch)}
            onUpdateBullet={(bulletIdx, value) => updateBullet(it.index, bulletIdx, value)}
            onDeleteBullet={(bulletIdx) => deleteBullet(it.index, bulletIdx)}
            onAddBullet={() => addBullet(it.index)}
            onReset={() => resetBundle(it.index)}
          />
        ))}
      </div>
    </div>
  );
}

type EditableBundleCardProps = {
  item: ProgressItem;
  stackLabel: string;
  generating: string;
  onUpdateBundle: (patch: Partial<ResumeBundle>) => void;
  onUpdateBullet: (bulletIdx: number, value: string) => void;
  onDeleteBullet: (bulletIdx: number) => void;
  onAddBullet: () => void;
  onReset: () => void;
};

function EditableBundleCard({
  item,
  stackLabel,
  generating,
  onUpdateBundle,
  onUpdateBullet,
  onDeleteBullet,
  onAddBullet,
  onReset,
}: EditableBundleCardProps) {
  const { t } = useI18n();
  const [editingTitle, setEditingTitle] = useState(false);
  const [editingStack, setEditingStack] = useState(false);
  const [editingBullet, setEditingBullet] = useState<number | null>(null);

  const bundle = item.bundle;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base flex items-center gap-2 flex-1 min-w-0">
            <Badge variant="outline" className="text-xs shrink-0">{item.index + 1}</Badge>
            {bundle ? (
              editingTitle ? (
                <Input
                  autoFocus
                  defaultValue={bundle.project_title}
                  onBlur={(e) => {
                    onUpdateBundle({ project_title: e.target.value });
                    setEditingTitle(false);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      onUpdateBundle({ project_title: e.currentTarget.value });
                      setEditingTitle(false);
                    } else if (e.key === "Escape") {
                      setEditingTitle(false);
                    }
                  }}
                  className="h-8 text-base"
                />
              ) : (
                <button
                  type="button"
                  onClick={() => setEditingTitle(true)}
                  className="text-left hover:bg-muted/50 rounded px-1 py-0.5 -mx-1 truncate"
                  title={t.resume.editTitle}
                >
                  {bundle.project_title || item.project_name}
                </button>
              )
            ) : (
              <span className="truncate">{item.project_name}</span>
            )}
          </CardTitle>
          {bundle && item.edited && (
            <div className="flex items-center gap-1.5 shrink-0">
              <Badge variant="secondary" className="text-xs">{t.resume.edited}</Badge>
              <Button size="sm" variant="ghost" onClick={onReset} title={t.resume.reset}>
                <RotateCcw className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
        </div>
        {bundle && (
          <CardDescription className="text-xs">
            <span className="font-medium">{stackLabel}: </span>
            {editingStack ? (
              <Input
                autoFocus
                defaultValue={bundle.stack_line}
                onBlur={(e) => {
                  onUpdateBundle({ stack_line: e.target.value });
                  setEditingStack(false);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    onUpdateBundle({ stack_line: e.currentTarget.value });
                    setEditingStack(false);
                  } else if (e.key === "Escape") {
                    setEditingStack(false);
                  }
                }}
                className="h-7 text-xs inline-block w-auto min-w-[200px]"
              />
            ) : (
              <button
                type="button"
                onClick={() => setEditingStack(true)}
                className="hover:bg-muted/50 rounded px-1 -mx-1"
                title={t.resume.editStack}
              >
                {bundle.stack_line}
              </button>
            )}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        {bundle ? (
          <>
            <ul className="space-y-2">
              {bundle.star_bullets.map((b, i) => (
                <li key={i} className="group flex items-start gap-2">
                  <span className="text-muted-foreground select-none pt-1">•</span>
                  {editingBullet === i ? (
                    <Textarea
                      autoFocus
                      defaultValue={b}
                      rows={3}
                      onBlur={(e) => {
                        onUpdateBullet(i, e.target.value);
                        setEditingBullet(null);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Escape") setEditingBullet(null);
                      }}
                      className="text-sm flex-1"
                    />
                  ) : (
                    <button
                      type="button"
                      onClick={() => setEditingBullet(i)}
                      className="text-sm text-left flex-1 hover:bg-muted/50 rounded px-1 py-0.5 -mx-1"
                      title={t.resume.edit}
                    >
                      {b || <span className="italic text-muted-foreground">{t.resume.edit}…</span>}
                    </button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="opacity-0 group-hover:opacity-100 transition-opacity h-7 w-7 p-0 shrink-0"
                    onClick={() => setEditingBullet(i)}
                    title={t.resume.edit}
                  >
                    <Pencil className="h-3 w-3" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="opacity-0 group-hover:opacity-100 transition-opacity h-7 w-7 p-0 shrink-0 text-destructive hover:text-destructive"
                    onClick={() => onDeleteBullet(i)}
                    title={t.resume.delete}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </li>
              ))}
            </ul>
            <Button
              size="sm"
              variant="ghost"
              onClick={onAddBullet}
              className="mt-2 text-xs text-muted-foreground hover:text-foreground"
            >
              <Plus className="h-3 w-3 mr-1" />
              {t.resume.addBullet}
            </Button>
          </>
        ) : (
          <p className="text-sm text-muted-foreground italic flex items-center gap-2">
            <Loader2 className="h-3 w-3 animate-spin" />
            {generating}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
