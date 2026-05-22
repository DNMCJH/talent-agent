"use client";

import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import Markdown from "react-markdown";
import { useApi } from "@/lib/api";
import { openSSE } from "@/lib/sse";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Loader2, Send, ClipboardList, X } from "lucide-react";
import { useI18n } from "@/i18n/context";

type Project = { id: number; name: string };
type DebriefArea = { name: string; score: number; comment: string };
type Debrief = {
  overall_score: number;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  areas: DebriefArea[];
};
type Critique = {
  score?: number;
  weakness_topics?: string[];
  severity?: string;
  next_focus?: string | null;
  feedback?: {
    summary?: string;
    suggestions?: string[];
    corrections?: string[];
  };
};
type ChatMsg = { role: "interviewer" | "candidate"; content: string; critique?: Critique };

export default function InterviewPage() {
  const api = useApi();
  const searchParams = useSearchParams();
  const { t } = useI18n();
  const { data: projects } = useSWR<Project[]>(
    api.token ? "/projects" : null,
    () => api.get<Project[]>("/projects"),
  );

  const [interviewType, setInterviewType] = useState<"targeted" | "comprehensive">("targeted");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [mode, setMode] = useState("tech");
  const [language, setLanguage] = useState("zh");
  const [jd, setJd] = useState("");
  const [resumeContext, setResumeContext] = useState("");
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    const pid = searchParams.get("project_id");
    const pids = searchParams.get("project_ids");
    const jdParam = searchParams.get("jd");
    if (pids) {
      const ids = pids.split(",").map((x) => Number(x.trim())).filter((n) => Number.isFinite(n) && n > 0);
      if (ids.length > 0) setSelectedIds(ids);
    } else if (pid) {
      setSelectedIds([Number(pid)]);
    }
    if (jdParam) {
      setJd(jdParam);
      return;
    }
    // Fallback: pick up the JD the user was last working on in the match page.
    try {
      const raw = sessionStorage.getItem("talent-agent.match.v1");
      if (raw) {
        const parsed = JSON.parse(raw) as { jd?: string };
        if (parsed.jd) setJd(parsed.jd);
      }
    } catch {
      // ignore
    }
    try {
      const rc = sessionStorage.getItem("talent-agent.resume_context");
      if (rc) setResumeContext(rc);
    } catch {
      // ignore
    }
  }, [searchParams]);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [debrief, setDebrief] = useState<Debrief | null>(null);
  const [debriefLoading, setDebriefLoading] = useState(false);
  // Holds the active SSE cleanup so we can cancel on unmount / new turn.
  const sseCloseRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      sseCloseRef.current?.();
    };
  }, []);

  function toggleProject(id: number) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  function selectAll() {
    if (!projects) return;
    if (selectedIds.length === projects.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(projects.map((p) => p.id));
    }
  }

  function onStart() {
    if (interviewType === "targeted" && (selectedIds.length === 0 || !jd.trim())) return;
    if (!api.token) {
      toast.error(t.interview.start);
      return;
    }
    setStarting(true);
    // Seed an empty interviewer bubble that the stream will fill in.
    setMessages([{ role: "interviewer", content: "" }]);

    sseCloseRef.current?.();
    sseCloseRef.current = openSSE(
      "/interview/start/stream/prepare",
      "/interview/start/stream",
      api.token,
      {
        project_ids: interviewType === "targeted" ? selectedIds : [],
        raw_jd: jd,
        mode: interviewType === "targeted" ? mode : "comprehensive",
        interview_type: interviewType,
        language,
        resume_context: resumeContext,
      },
      {
        onEvent: (e) => {
          if (e.type === "delta") {
            setMessages((m) => {
              const last = m[m.length - 1];
              if (!last) return m;
              return [...m.slice(0, -1), { ...last, content: last.content + e.text }];
            });
          } else if (e.type === "done") {
            setSessionId(e.session_id as string);
            setStarting(false);
          } else if (e.type === "error") {
            toast.error(e.message);
            setMessages([]);
            setStarting(false);
          }
        },
        onNetworkError: () => {
          toast.error(language === "zh" ? "连接中断，请重试" : "Connection lost, please retry");
          setMessages([]);
          setStarting(false);
        },
      },
    );
  }

  function onSend() {
    if (!sessionId || !input.trim() || !api.token) return;
    const msg = input.trim();
    setInput("");
    // Append candidate turn, then an empty interviewer turn for streaming.
    setMessages((m) => [
      ...m,
      { role: "candidate", content: msg },
      { role: "interviewer", content: "" },
    ]);
    setSending(true);

    sseCloseRef.current?.();
    sseCloseRef.current = openSSE(
      "/interview/turn/stream/prepare",
      "/interview/turn/stream",
      api.token,
      { session_id: sessionId, candidate_message: msg },
      {
        onEvent: (e) => {
          if (e.type === "delta") {
            setMessages((m) => {
              const last = m[m.length - 1];
              if (!last) return m;
              return [...m.slice(0, -1), { ...last, content: last.content + e.text }];
            });
          } else if (e.type === "done") {
            const critique = e.critique as Critique | undefined;
            // Attach critique to the candidate turn (one before the interviewer turn).
            setMessages((m) => {
              if (m.length < 2) return m;
              const candIdx = m.length - 2;
              const updated = [...m];
              updated[candIdx] = { ...updated[candIdx], critique };
              return updated;
            });
            setSending(false);
          } else if (e.type === "error") {
            toast.error(e.message);
            // Roll back the empty interviewer bubble.
            setMessages((m) => m.slice(0, -1));
            setSending(false);
          }
        },
        onNetworkError: () => {
          toast.error(language === "zh" ? "连接中断，请重试" : "Connection lost, please retry");
          setMessages((m) => m.slice(0, -1));
          setSending(false);
        },
      },
    );
  }

  function onReset() {
    sseCloseRef.current?.();
    setSessionId(null);
    setMessages([]);
    setInput("");
    setDebrief(null);
  }

  async function loadDebrief() {
    if (!sessionId || !api.token) return;
    setDebriefLoading(true);
    try {
      const d = await api.post<Debrief>(
        "/interview/debrief",
        { session_id: sessionId, language },
        120_000,
      );
      setDebrief(d);
    } catch {
      toast.error(language === "zh" ? "复盘生成失败，请重试" : "Debrief failed, please retry");
    } finally {
      setDebriefLoading(false);
    }
  }

  const canStart =
    interviewType === "comprehensive"
      ? (projects?.length ?? 0) > 0
      : selectedIds.length > 0 && jd.trim().length > 0;

  if (!sessionId) {
    return (
      <div className="space-y-6 max-w-4xl mx-auto">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t.interview.title}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t.interview.subtitle}</p>
        </div>

        {/* Interview type tabs */}
        <div className="flex gap-2">
          <button
            onClick={() => setInterviewType("targeted")}
            className={`flex-1 rounded-lg border p-4 text-left transition-colors ${
              interviewType === "targeted" ? "border-primary bg-primary/5" : "hover:bg-muted/50"
            }`}
          >
            <div className="font-medium text-sm">{t.interview.targeted}</div>
            <div className="text-xs text-muted-foreground mt-1">{t.interview.targetedDesc}</div>
          </button>
          <button
            onClick={() => setInterviewType("comprehensive")}
            className={`flex-1 rounded-lg border p-4 text-left transition-colors ${
              interviewType === "comprehensive" ? "border-primary bg-primary/5" : "hover:bg-muted/50"
            }`}
          >
            <div className="font-medium text-sm">{t.interview.comprehensive}</div>
            <div className="text-xs text-muted-foreground mt-1">{t.interview.comprehensiveDesc}</div>
          </button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t.interview.setup}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {interviewType === "targeted" ? (
              <>
                {/* Multi-select projects */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium">{t.interview.projects}</label>
                    {projects && projects.length > 0 && (
                      <button
                        onClick={selectAll}
                        className="text-xs text-primary hover:underline"
                      >
                        {t.interview.selectAll}
                        {selectedIds.length === projects.length ? " ✓" : ""}
                      </button>
                    )}
                  </div>
                  {!projects || projects.length === 0 ? (
                    <p className="text-sm text-muted-foreground">{t.interview.noProjects}</p>
                  ) : (
                    <div className="border rounded-md max-h-48 overflow-y-auto">
                      {projects.map((p) => (
                        <label
                          key={p.id}
                          className="flex items-center gap-2 px-3 py-2 hover:bg-muted/50 cursor-pointer text-sm"
                        >
                          <input
                            type="checkbox"
                            checked={selectedIds.includes(p.id)}
                            onChange={() => toggleProject(p.id)}
                            className="rounded"
                          />
                          {p.name}
                        </label>
                      ))}
                    </div>
                  )}
                </div>
                {/* Style */}
                <div>
                  <label className="text-sm font-medium block mb-2">{t.interview.style}</label>
                  <select
                    aria-label="Interview style"
                    className="w-full border rounded-md p-2 bg-background text-sm"
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                  >
                    <option value="tech">{t.interview.tech}</option>
                    <option value="stress">{t.interview.stress}</option>
                    <option value="behavior">{t.interview.behavior}</option>
                  </select>
                </div>
                {/* Interview language */}
                <div>
                  <label className="text-sm font-medium block mb-2">{t.interview.language}</label>
                  <select
                    aria-label="Interview language"
                    className="w-full border rounded-md p-2 bg-background text-sm"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                  >
                    <option value="zh">{t.interview.langZh}</option>
                    <option value="en">{t.interview.langEn}</option>
                  </select>
                </div>
                {/* JD required */}
                <div>
                  <label className="text-sm font-medium block mb-2">{t.interview.jd}</label>
                  <Textarea
                    placeholder={t.interview.jdPlaceholder}
                    value={jd}
                    onChange={(e) => setJd(e.target.value)}
                    rows={5}
                  />
                </div>
              </>
            ) : (
              <>
                {/* Comprehensive: all projects auto-included */}
                <div className="rounded-md bg-muted/50 p-3">
                  <p className="text-sm text-muted-foreground">{t.interview.allProjectsIncluded}</p>
                  {projects && projects.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {projects.map((p) => (
                        <Badge key={p.id} variant="secondary" className="text-xs">{p.name}</Badge>
                      ))}
                    </div>
                  )}
                  {(!projects || projects.length === 0) && (
                    <p className="text-sm text-destructive mt-1">{t.interview.noProjects}</p>
                  )}
                </div>
                {/* Interview language */}
                <div>
                  <label className="text-sm font-medium block mb-2">{t.interview.language}</label>
                  <select
                    aria-label="Interview language"
                    className="w-full border rounded-md p-2 bg-background text-sm"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                  >
                    <option value="zh">{t.interview.langZh}</option>
                    <option value="en">{t.interview.langEn}</option>
                  </select>
                </div>
                {/* JD optional */}
                <div>
                  <label className="text-sm font-medium block mb-2">{t.interview.jdOptional}</label>
                  <p className="text-xs text-muted-foreground mb-2">{t.interview.jdOptionalHint}</p>
                  <Textarea
                    placeholder={t.interview.jdPlaceholder}
                    value={jd}
                    onChange={(e) => setJd(e.target.value)}
                    rows={4}
                  />
                </div>
              </>
            )}

            <Button onClick={onStart} disabled={starting || !canStart}>
              {starting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {starting ? (language === "zh" ? "AI 正在准备面试…" : "AI preparing interview…") : t.interview.start}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Active interview session
  const answeredCount = messages.filter((m) => m.role === "candidate").length;
  return (
    <div className="space-y-4 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">{t.interview.inProgress}</h1>
        <div className="flex items-center gap-2">
          {answeredCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={loadDebrief}
              disabled={debriefLoading || sending}
            >
              {debriefLoading ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <ClipboardList className="mr-1.5 h-3.5 w-3.5" />
              )}
              {t.interview.debrief}
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={onReset}>{t.interview.end}</Button>
        </div>
      </div>

      {debrief && (
        <DebriefCard debrief={debrief} onClose={() => setDebrief(null)} />
      )}

      <div className="space-y-3">
        {messages.map((m, i) => {
          const isLastCandidate =
            m.role === "candidate" &&
            i === messages.length - 2 &&
            sending &&
            !m.critique;
          const isStreamingInterviewer =
            m.role === "interviewer" &&
            i === messages.length - 1 &&
            (sending || starting) &&
            m.content === "";
          return (
            <Card key={i} className={m.role === "candidate" ? "bg-muted/40" : ""}>
              <CardHeader className="pb-2">
                <CardDescription className="text-xs uppercase tracking-wide">
                  {m.role}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {isStreamingInterviewer ? (
                  <p className="text-sm text-muted-foreground italic flex items-center gap-2">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    {language === "zh" ? "AI 正在思考…" : "AI is thinking…"}
                  </p>
                ) : m.role === "interviewer" ? (
                  <div className="text-sm prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0.5">
                    <Markdown>{m.content}</Markdown>
                  </div>
                ) : (
                  <p className="text-sm whitespace-pre-wrap">{m.content}</p>
                )}
                {m.critique && (
                  <div className="mt-3 pt-3 border-t space-y-2">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <Badge variant="outline">{m.critique.score ?? "?"}/10</Badge>
                      {m.critique.severity && (
                        <Badge variant={m.critique.severity === "严重" ? "destructive" : "secondary"}>
                          {m.critique.severity}
                        </Badge>
                      )}
                      {m.critique.weakness_topics?.map((wt) => (
                        <Badge key={wt} variant="destructive">{wt}</Badge>
                      ))}
                      {m.critique.feedback?.summary && (
                        <span className="text-muted-foreground">{m.critique.feedback.summary}</span>
                      )}
                    </div>
                    {m.critique.feedback && (!!m.critique.feedback.suggestions?.length || !!m.critique.feedback.corrections?.length) && (
                      <details className="text-xs">
                        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                          {language === "zh" ? "展开详细反馈" : "Show detailed feedback"}
                        </summary>
                        <div className="mt-2 space-y-1.5 pl-2 border-l-2 border-muted">
                          {m.critique.feedback.corrections && m.critique.feedback.corrections.length > 0 && (
                            <div>
                              <span className="font-medium text-destructive">{language === "zh" ? "技术纠错：" : "Corrections:"}</span>
                              <ul className="list-disc pl-4 mt-0.5">
                                {m.critique.feedback.corrections.map((c, i) => <li key={i}>{c}</li>)}
                              </ul>
                            </div>
                          )}
                          {m.critique.feedback.suggestions && m.critique.feedback.suggestions.length > 0 && (
                            <div>
                              <span className="font-medium">{language === "zh" ? "修改建议：" : "Suggestions:"}</span>
                              <ul className="list-disc pl-4 mt-0.5">
                                {m.critique.feedback.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                              </ul>
                            </div>
                          )}
                        </div>
                      </details>
                    )}
                  </div>
                )}
                {isLastCandidate && (
                  <div className="mt-3 pt-3 border-t flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    {language === "zh" ? "评分中…" : "Scoring…"}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="sticky bottom-4 bg-background border rounded-lg p-3 flex gap-2">
        <Textarea
          placeholder={t.interview.yourAnswer}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={3}
          disabled={sending}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onSend();
          }}
        />
        <Button onClick={onSend} disabled={sending || !input.trim()}>
          {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}

/** End-of-interview debrief: aggregated score, strengths, gaps, next steps. */
function DebriefCard({
  debrief,
  onClose,
}: {
  debrief: Debrief;
  onClose: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
            {t.interview.debriefTitle}
          </p>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-4xl font-semibold tracking-tight">
              {debrief.overall_score}
            </span>
            <span className="text-sm text-muted-foreground">/ 10</span>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="close"
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <p className="mt-3 text-sm text-muted-foreground">{debrief.summary}</p>

      {debrief.areas.length > 0 && (
        <div className="mt-5 border-t pt-4 space-y-2">
          {debrief.areas.map((a) => (
            <div key={a.name} className="grid grid-cols-12 items-baseline gap-3 text-sm">
              <span className="col-span-3 font-medium">{a.name}</span>
              <span className="col-span-1 font-mono text-muted-foreground">
                {a.score}
              </span>
              <span className="col-span-8 text-muted-foreground">{a.comment}</span>
            </div>
          ))}
        </div>
      )}

      <div className="mt-5 grid gap-5 border-t pt-4 sm:grid-cols-3">
        <DebriefList title={t.interview.debriefStrengths} items={debrief.strengths} />
        <DebriefList title={t.interview.debriefWeaknesses} items={debrief.weaknesses} />
        <DebriefList
          title={t.interview.debriefRecommendations}
          items={debrief.recommendations}
        />
      </div>
    </div>
  );
}

function DebriefList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="font-mono text-xs uppercase tracking-[0.15em] text-muted-foreground">
        {title}
      </p>
      <ul className="mt-2 space-y-1.5 text-sm">
        {items.map((it, i) => (
          <li key={i} className="flex gap-1.5">
            <span className="text-muted-foreground">·</span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
