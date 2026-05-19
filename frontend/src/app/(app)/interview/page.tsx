"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { useApi, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Loader2, Send } from "lucide-react";
import { useI18n } from "@/i18n/context";

type Project = { id: number; name: string };
type Critique = { score?: number; weakness_topics?: string[]; severity?: string; next_focus?: string | null };
type TurnResponse = {
  session_id: string;
  interviewer_message: string;
  turn_count: number;
  critique?: Critique;
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
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    const pid = searchParams.get("project_id");
    const jdParam = searchParams.get("jd");
    if (pid) setSelectedIds([Number(pid)]);
    if (jdParam) setJd(jdParam);
  }, [searchParams]);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

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

  async function onStart() {
    if (interviewType === "targeted" && (selectedIds.length === 0 || !jd.trim())) return;
    setStarting(true);
    try {
      const r = await api.post<TurnResponse>("/interview/start", {
        project_ids: interviewType === "targeted" ? selectedIds : [],
        interview_type: interviewType,
        mode: interviewType === "targeted" ? mode : "comprehensive",
        raw_jd: jd,
        language,
      }, 120_000);
      setSessionId(r.session_id);
      setMessages([{ role: "interviewer", content: r.interviewer_message }]);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(msg);
    } finally {
      setStarting(false);
    }
  }

  async function onSend() {
    if (!sessionId || !input.trim()) return;
    const msg = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "candidate", content: msg }]);
    setSending(true);
    try {
      const r = await api.post<TurnResponse>("/interview/turn", {
        session_id: sessionId,
        candidate_message: msg,
      }, 90_000);
      setMessages((m) => [
        ...m.slice(0, -1),
        { ...m[m.length - 1], critique: r.critique },
        { role: "interviewer", content: r.interviewer_message },
      ]);
    } catch (e) {
      const errMsg = e instanceof ApiError ? e.message : String(e);
      toast.error(errMsg);
    } finally {
      setSending(false);
    }
  }

  function onReset() {
    setSessionId(null);
    setMessages([]);
    setInput("");
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
  return (
    <div className="space-y-4 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">{t.interview.inProgress}</h1>
        <Button variant="outline" size="sm" onClick={onReset}>{t.interview.end}</Button>
      </div>

      <div className="space-y-3">
        {messages.map((m, i) => (
          <Card key={i} className={m.role === "candidate" ? "bg-muted/40" : ""}>
            <CardHeader className="pb-2">
              <CardDescription className="text-xs uppercase tracking-wide">
                {m.role}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm whitespace-pre-wrap">{m.content}</p>
              {m.critique && (
                <div className="mt-3 pt-3 border-t flex flex-wrap items-center gap-2 text-xs">
                  <Badge variant="outline">score {m.critique.score ?? "?"}/5</Badge>
                  {m.critique.severity && (
                    <Badge variant="secondary">{m.critique.severity}</Badge>
                  )}
                  {m.critique.weakness_topics?.map((wt) => (
                    <Badge key={wt} variant="destructive">{wt}</Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
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
