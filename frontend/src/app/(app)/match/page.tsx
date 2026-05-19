"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApi, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Loader2, MessageSquare, FileText } from "lucide-react";
import { useI18n } from "@/i18n/context";

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

export default function MatchPage() {
  const api = useApi();
  const router = useRouter();
  const { t } = useI18n();
  const [jd, setJd] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MatchResult | null>(null);
  const [resumeLoading, setResumeLoading] = useState<number | null>(null);

  async function onMatch() {
    if (!jd.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const r = await api.post<MatchResult>("/match", { raw_jd: jd, top_k: 5 });
      setResult(r);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(`Match failed: ${msg}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t.match.title}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t.match.subtitle}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t.match.jdTitle}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            placeholder={t.match.placeholder}
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            rows={8}
            disabled={loading}
          />
          <Button onClick={onMatch} disabled={loading || !jd.trim()}>
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {t.match.run}
          </Button>
        </CardContent>
      </Card>

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

          <h2 className="text-sm font-medium text-muted-foreground">{t.match.ranked}</h2>
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
                  {t.match.coverage} {(m.coverage * 100).toFixed(0)}% · Plus {(m.plus_coverage * 100).toFixed(0)}%
                </CardDescription>
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
                  <div className="flex gap-2 pt-3 border-t mt-3">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        const params = new URLSearchParams({
                          project_id: String(m.project_id),
                          jd: jd,
                        });
                        router.push(`/interview?${params.toString()}`);
                      }}
                    >
                      <MessageSquare className="mr-1.5 h-3.5 w-3.5" />
                      {t.match.mockInterview}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={resumeLoading === m.project_id}
                      onClick={async () => {
                        setResumeLoading(m.project_id);
                        try {
                          const res = await api.post<{ star_bullets: string[]; stack_line: string }>("/resume", {
                            project_id: m.project_id,
                            raw_jd: jd,
                          });
                          toast.success(
                            `Resume bullets:\n${res.star_bullets.join("\n")}`,
                            { duration: 15000 },
                          );
                        } catch (e) {
                          const msg = e instanceof ApiError ? e.message : String(e);
                          toast.error(msg);
                        } finally {
                          setResumeLoading(null);
                        }
                      }}
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
  );
}
