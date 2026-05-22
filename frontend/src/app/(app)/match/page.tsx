"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useApi, ApiError, API_BASE } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Loader2, MessageSquare, FileText, Copy, Check, Download, Wrench, X } from "lucide-react";
import { useI18n } from "@/i18n/context";
import { copyToClipboard } from "@/lib/clipboard";

type Skill = { name: string; level: string };
type ParsedJD = {
  company: string;
  role: string;
  must_skills: Skill[];
  plus_skills: Skill[];
  responsibilities: string[];
};
type Match = {
  project: { name: string; stack: string[] };
  project_id: number | null;
  coverage: number;
  plus_coverage: number;
  weighted_score: number;
  matched_skills: string[];
  missing_skills: string[];
  matched_plus_skills: string[];
  match_reason: string;
};
type MatchResult = { jd: ParsedJD; matches: Match[]; overall_best: Match };
type ResumeData = {
  project_title: string;
  stack_line: string;
  star_bullets: string[];
  tailored_for_role: string;
};
type ImprovementTask = {
  title: string;
  addresses_gaps: string[];
  effort_days: number;
  deliverables: string[];
  implementation_hints: string;
  resume_impact: string;
};
type ImprovementPlan = { project_name: string; tasks: ImprovementTask[] };

export default function MatchPage() {
  const api = useApi();
  const router = useRouter();
  const { t, locale } = useI18n();
  const [jd, setJd] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MatchResult | null>(null);

  // Restore JD + last result from sessionStorage so navigating away and back keeps state.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("talent-agent.match.v1");
      if (raw) {
        const parsed = JSON.parse(raw) as { jd?: string; result?: MatchResult };
        if (parsed.jd) setJd(parsed.jd);
        if (parsed.result) setResult(parsed.result);
      }
    } catch {
      // ignore malformed cache
    }
  }, []);

  // Persist JD as user types so a hot reload / accidental navigation does not lose work.
  useEffect(() => {
    if (!jd && !result) return;
    try {
      sessionStorage.setItem(
        "talent-agent.match.v1",
        JSON.stringify({ jd, result }),
      );
    } catch {
      // quota exceeded — ignore
    }
  }, [jd, result]);
  const [resumeLoading, setResumeLoading] = useState<number | null>(null);
  const [resumeData, setResumeData] = useState<ResumeData | null>(null);
  const [resumeOpen, setResumeOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [planLoading, setPlanLoading] = useState(false);
  const [planData, setPlanData] = useState<ImprovementPlan | null>(null);

  // Project ids of the ranked matches — shared by the header's mock-interview
  // and full-resume actions.
  function matchedProjectIds(): number[] {
    if (!result) return [];
    return result.matches
      .map((m) => m.project_id)
      .filter((id): id is number => typeof id === "number")
      .slice(0, 5);
  }

  function startInterviewFromMatches() {
    const ids = matchedProjectIds();
    if (ids.length === 0) return;
    router.push(
      `/interview?${new URLSearchParams({ project_ids: ids.join(","), jd }).toString()}`,
    );
  }

  async function onMatch() {
    if (!jd.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const r = await api.post<MatchResult>("/match", { raw_jd: jd, top_k: 5, language: locale }, 120_000);
      setResult(r);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(`Match failed: ${msg}`);
    } finally {
      setLoading(false);
    }
  }

  async function onGenerateResume(projectId: number) {
    setResumeLoading(projectId);
    try {
      const res = await api.post<ResumeData>("/resume", {
        project_id: projectId,
        raw_jd: jd,
        language: locale,
      }, 90_000);
      setResumeData(res);
      setResumeOpen(true);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(msg);
    } finally {
      setResumeLoading(null);
    }
  }

  async function onGeneratePlan() {
    if (!jd.trim()) return;
    setPlanLoading(true);
    try {
      const p = await api.post<ImprovementPlan>(
        "/match/improvement",
        { raw_jd: jd, top_k: 5, language: locale },
        120_000,
      );
      setPlanData(p);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(msg);
    } finally {
      setPlanLoading(false);
    }
  }

  async function downloadResumeDocx() {
    if (!resumeData) return;
    setDownloading(true);
    try {
      const res = await fetch(`${API_BASE}/resume/export/docx`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(api.token ? { Authorization: `Bearer ${api.token}` } : {}),
        },
        body: JSON.stringify({
          name: resumeData.project_title,
          sections: [
            {
              title: locale === "zh" ? "技术栈" : "Tech Stack",
              content: resumeData.stack_line,
            },
            {
              title: locale === "zh" ? "项目要点" : "Highlights",
              content: resumeData.star_bullets.map((b) => `- ${b}`).join("\n"),
            },
          ],
        }),
      });
      if (!res.ok) throw new Error(String(res.status));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${resumeData.project_title.replace(/\s+/g, "_")}_resume.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error(locale === "zh" ? "导出失败，请重试" : "Export failed, please retry");
    } finally {
      setDownloading(false);
    }
  }

  async function copyResume() {
    if (!resumeData) return;
    const text = `${resumeData.project_title}\n${resumeData.stack_line}\n\n${resumeData.star_bullets.map((b) => `• ${b}`).join("\n")}`;
    const ok = await copyToClipboard(text);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } else {
      toast.error(locale === "zh" ? "复制失败，请手动选中复制" : "Copy failed, please select and copy manually");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t.match.title}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t.match.subtitle}</p>
      </div>

      {/* PC: JD input on the left, results on the right. Mobile: stacked. */}
      <div className="lg:grid lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)] lg:gap-6 lg:items-start">
      <div className="lg:sticky lg:top-20">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t.match.jdTitle}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            placeholder={t.match.placeholder}
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            rows={10}
            disabled={loading}
          />
          <div className="flex gap-2">
            <Button onClick={onMatch} disabled={loading || !jd.trim()}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t.match.run}
            </Button>
            {(jd || result) && (
              <Button
                variant="outline"
                onClick={() => {
                  setJd("");
                  setResult(null);
                  try {
                    sessionStorage.removeItem("talent-agent.match.v1");
                  } catch {
                    // ignore
                  }
                }}
                disabled={loading}
              >
                {t.match.clear}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
      </div>

      <div className="mt-6 space-y-4 lg:mt-0">
      {!result && !loading && (
        <div className="flex min-h-[240px] items-center justify-center rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          {t.match.emptyResults}
        </div>
      )}
      {result && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {result.jd.company} — {result.jd.role}
              </CardTitle>
            <CardDescription>{t.match.parsed}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex flex-wrap gap-1">
                <span className="text-muted-foreground mr-2">{t.match.must}</span>
                {result.jd.must_skills.map((s) => (
                  <Badge key={s.name}>{s.name}</Badge>
                ))}
              </div>
              <div className="flex flex-wrap gap-1">
                <span className="text-muted-foreground mr-2">{t.match.plus}</span>
                {result.jd.plus_skills.map((s) => (
                  <Badge key={s.name} variant="secondary">{s.name}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Ranked-list header. The portfolio-level actions — mock interview
              across all matches, improvement plan, full resume — live here;
              per-project actions stay on each card. */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-medium text-muted-foreground">{t.match.ranked}</h2>
            <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={matchedProjectIds().length === 0}
              onClick={startInterviewFromMatches}
            >
              <MessageSquare className="mr-1.5 h-3.5 w-3.5" />
              {t.match.mockInterview}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={planLoading}
              onClick={onGeneratePlan}
            >
              {planLoading ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Wrench className="mr-1.5 h-3.5 w-3.5" />
              )}
              {t.match.improvementPlan}
            </Button>
            <Button
              size="sm"
              variant="default"
              onClick={() => {
                const ids = matchedProjectIds();
                if (ids.length === 0) return;
                const params = new URLSearchParams({
                  project_ids: ids.join(","),
                  jd,
                });
                router.push(`/resume?${params.toString()}`);
              }}
            >
              <FileText className="mr-1.5 h-3.5 w-3.5" />
              {t.match.generateFull}
            </Button>
            </div>
          </div>

          {/* Improvement plan — rendered inline in the results flow, so it
              reads as part of the analysis rather than a detached dialog. */}
          {planData && (
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <CardTitle className="text-base">{t.match.planTitle}</CardTitle>
                    <CardDescription>{planData.project_name}</CardDescription>
                  </div>
                  <button
                    type="button"
                    onClick={() => setPlanData(null)}
                    aria-label={t.match.close}
                    className="text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {planData.tasks.length === 0 && (
                  <p className="text-sm text-muted-foreground">{t.match.planEmpty}</p>
                )}
                {planData.tasks.map((task, i) => (
                  <div key={i} className="space-y-1.5 border-l-2 pl-3">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-sm font-medium leading-snug">
                        {i + 1}. {task.title}
                      </h3>
                      <Badge variant="outline" className="shrink-0 font-mono text-xs">
                        {task.effort_days}
                        {t.match.planEffort}
                      </Badge>
                    </div>
                    {task.addresses_gaps.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1">
                        <span className="mr-1 text-xs text-muted-foreground">
                          {t.match.planGaps}
                        </span>
                        {task.addresses_gaps.map((g) => (
                          <Badge key={g} variant="secondary" className="text-xs font-normal">
                            {g}
                          </Badge>
                        ))}
                      </div>
                    )}
                    {task.deliverables.length > 0 && (
                      <div className="text-xs">
                        <span className="text-muted-foreground">{t.match.planDeliverables}</span>
                        <ul className="mt-0.5 space-y-0.5">
                          {task.deliverables.map((d, j) => (
                            <li
                              key={j}
                              className="relative pl-3 before:absolute before:left-0 before:text-muted-foreground before:content-['–']"
                            >
                              {d}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {task.implementation_hints && (
                      <p className="text-xs text-muted-foreground">
                        <span className="font-medium">{t.match.planHints}: </span>
                        {task.implementation_hints}
                      </p>
                    )}
                    {task.resume_impact && (
                      <p className="text-xs italic text-muted-foreground">
                        <span className="font-medium not-italic">{t.match.planImpact}: </span>
                        {task.resume_impact}
                      </p>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
          {result.matches.map((m, idx) => (
            <Card key={idx}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{m.project.name}</CardTitle>
                  <Badge variant="outline">
                    {t.match.score} {m.weighted_score.toFixed(2)}
                  </Badge>
                </div>
                <CardDescription>
                  {t.match.coverage} {(m.coverage * 100).toFixed(0)}% · {t.match.plusCoverage} {(m.plus_coverage * 100).toFixed(0)}%
                </CardDescription>
                {m.project.stack && m.project.stack.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {m.project.stack.map((tech) => (
                      <Badge key={tech} variant="outline" className="text-xs font-normal">{tech}</Badge>
                    ))}
                  </div>
                )}
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {m.matched_skills.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    <span className="text-muted-foreground mr-2">{t.match.matched}</span>
                    {m.matched_skills.map((s) => (
                      <Badge key={s} variant="default">{s}</Badge>
                    ))}
                  </div>
                )}
                {m.missing_skills.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    <span className="text-muted-foreground mr-2">{t.match.missing}</span>
                    {m.missing_skills.map((s) => (
                      <Badge key={s} variant="destructive">{s}</Badge>
                    ))}
                  </div>
                )}
                {m.match_reason && (
                  <p className="text-muted-foreground italic pt-1">{m.match_reason}</p>
                )}
                {m.project_id && (
                  <div className="mt-3 flex gap-2 border-t pt-3">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={resumeLoading === m.project_id}
                      onClick={() => onGenerateResume(m.project_id!)}
                    >
                      {resumeLoading === m.project_id ? (
                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <FileText className="mr-1.5 h-3.5 w-3.5" />
                      )}
                      {t.match.generateResume}
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      </div>
      </div>

      {/* Resume Dialog */}
      <Dialog open={resumeOpen} onOpenChange={setResumeOpen}>
        <DialogContent className="sm:max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t.match.resumeTitle}</DialogTitle>
          </DialogHeader>
          {resumeData && (
            <div className="space-y-4">
              <div>
                <h3 className="font-semibold text-base">{resumeData.project_title}</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {t.match.resumeStack}: {resumeData.stack_line}
                </p>
                {resumeData.tailored_for_role && (
                  <p className="text-xs text-muted-foreground mt-0.5">
                    → {resumeData.tailored_for_role}
                  </p>
                )}
              </div>
              <ul className="space-y-2">
                {resumeData.star_bullets.map((bullet, i) => (
                  <li key={i} className="text-sm pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-muted-foreground">
                    {bullet}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <DialogFooter className="flex gap-2">
            <Button variant="outline" size="sm" onClick={copyResume}>
              {copied ? <Check className="mr-1.5 h-3.5 w-3.5" /> : <Copy className="mr-1.5 h-3.5 w-3.5" />}
              {copied ? t.match.copied : t.match.copy}
            </Button>
            <Button variant="outline" size="sm" disabled={downloading} onClick={downloadResumeDocx}>
              {downloading ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Download className="mr-1.5 h-3.5 w-3.5" />
              )}
              {downloading ? t.match.downloading : t.match.download}
            </Button>
            <Button size="sm" onClick={() => setResumeOpen(false)}>
              {t.match.close}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
