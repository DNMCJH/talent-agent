"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useApi, ApiError } from "@/lib/api";
import { useI18n } from "@/i18n/context";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Loader2, Upload, FileText, RotateCcw, ArrowRight } from "lucide-react";

type ParsedResume = {
  name: string;
  email: string;
  phone: string;
  education: Array<{ school?: string; degree?: string; major?: string; period?: string }>;
  experience: Array<{ company?: string; role?: string; period?: string; description?: string }>;
  skills: string[];
  projects: Array<{ name?: string; description?: string; tech_stack?: string; highlights?: string }>;
  raw_text: string;
};

type ResumeParseOut = {
  filename: string;
  parsed: ParsedResume;
};

type ImportedProject = {
  id: number;
  name: string;
  source: string;
  github_url: string | null;
  analysis_depth: string;
};

type ImportFromResumeOut = {
  imported: ImportedProject[];
  skipped: Array<{ name: string; reason: string }>;
};

export default function ResumeUploadPage() {
  const api = useApi();
  const router = useRouter();
  const { t } = useI18n();
  const [parsing, setParsing] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [result, setResult] = useState<ResumeParseOut | null>(null);
  const [importing, setImporting] = useState(false);
  const [importedIds, setImportedIds] = useState<number[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function onUploadFile(file: File) {
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !["pdf", "docx", "doc", "txt"].includes(ext)) {
      toast.error("Unsupported file type. Use PDF, DOCX, or TXT.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error("File too large (max 10MB)");
      return;
    }
    setParsing(true);
    try {
      const data = await api.upload<ResumeParseOut>("/resume-upload/parse", file, 60000);
      setResult(data);
      toast.success(t.resumeUpload.parsed);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(msg);
    } finally {
      setParsing(false);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onUploadFile(file);
  }

  function onFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onUploadFile(file);
    e.target.value = "";
  }

  function onReset() {
    setResult(null);
    setImportedIds([]);
  }

  async function onImportAll() {
    if (!result || result.parsed.projects.length === 0) return;
    setImporting(true);
    try {
      const out = await api.post<ImportFromResumeOut>("/projects/import/from-resume", {
        projects: result.parsed.projects,
      });
      const okCount = out.imported.length;
      const skipCount = out.skipped.length;
      setImportedIds(out.imported.map((p) => p.id));
      if (okCount > 0 && skipCount === 0) {
        toast.success(t.resumeUpload.importResultOk.replace("{n}", String(okCount)));
      } else if (okCount > 0) {
        toast.message(
          t.resumeUpload.importResultPartial
            .replace("{n}", String(okCount))
            .replace("{m}", String(skipCount)),
        );
      } else {
        toast.error(
          (out.skipped[0]?.reason ?? "no projects imported") + (skipCount > 1 ? ` (+${skipCount - 1})` : ""),
        );
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(msg);
    } finally {
      setImporting(false);
    }
  }

  function buildResumeContext(): string {
    if (!result) return "";
    const p = result.parsed;
    const parts: string[] = [];
    if (p.name) parts.push(`Name: ${p.name}`);
    if (p.education.length > 0) {
      const eduStr = p.education
        .map((e) => [e.school, e.degree, e.major, e.period].filter(Boolean).join(", "))
        .join("; ");
      parts.push(`Education: ${eduStr}`);
    }
    if (p.experience.length > 0) {
      const expStr = p.experience
        .map((e) => [e.role, e.company, e.period].filter(Boolean).join(", "))
        .join("; ");
      parts.push(`Experience: ${expStr}`);
    }
    if (p.skills.length > 0) {
      parts.push(`Skills: ${p.skills.join(", ")}`);
    }
    return parts.join("\n");
  }

  function onStartInterview() {
    if (importedIds.length === 0) return;
    const ids = importedIds.join(",");
    const rc = buildResumeContext();
    sessionStorage.setItem("talent-agent.resume_context", rc);
    router.push(`/interview?project_ids=${ids}`);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t.resumeUpload.title}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t.resumeUpload.subtitle}</p>
      </div>

      {!result ? (
        <Card>
          <CardContent className="pt-6">
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
                dragOver ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/50"
              }`}
            >
              {parsing ? (
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="h-10 w-10 animate-spin text-primary" />
                  <p className="text-sm text-muted-foreground">{t.resumeUpload.parsing}</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <Upload className="h-10 w-10 text-muted-foreground" />
                  <p className="text-sm font-medium">{t.resumeUpload.drop}</p>
                  <p className="text-xs text-muted-foreground">{t.resumeUpload.browse}</p>
                  <p className="text-xs text-muted-foreground">{t.resumeUpload.hint}</p>
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc,.txt"
                className="hidden"
                onChange={onFileSelect}
                aria-label="Upload resume file"
              />
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-primary" />
              <span className="font-medium">{result.filename}</span>
            </div>
            <Button variant="outline" size="sm" onClick={onReset}>
              <RotateCcw className="h-4 w-4 mr-1" />
              {t.resumeUpload.reupload}
            </Button>
          </div>

          {result.parsed.name && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">{result.parsed.name}</CardTitle>
                <CardDescription>
                  {[result.parsed.email, result.parsed.phone].filter(Boolean).join(" · ")}
                </CardDescription>
              </CardHeader>
            </Card>
          )}

          {result.parsed.education.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{t.resumeUpload.education}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {result.parsed.education.map((edu, i) => (
                  <div key={i} className="text-sm">
                    <div className="font-medium">{edu.school}</div>
                    <div className="text-muted-foreground">
                      {[edu.degree, edu.major, edu.period].filter(Boolean).join(" · ")}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {result.parsed.experience.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{t.resumeUpload.experience}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {result.parsed.experience.map((exp, i) => (
                  <div key={i} className="text-sm">
                    <div className="font-medium">{exp.role} @ {exp.company}</div>
                    <div className="text-xs text-muted-foreground">{exp.period}</div>
                    {exp.description && <p className="text-muted-foreground mt-1">{exp.description}</p>}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {result.parsed.skills.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{t.resumeUpload.skills}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {result.parsed.skills.map((skill, i) => (
                    <Badge key={i} variant="secondary">{skill}</Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {result.parsed.projects.length > 0 && (
            <Card>
              <CardHeader className="pb-2 flex flex-row items-center justify-between">
                <CardTitle className="text-base">{t.resumeUpload.projects}</CardTitle>
                <div className="flex gap-2">
                  {importedIds.length === 0 ? (
                    <Button size="sm" onClick={onImportAll} disabled={importing}>
                      {importing ? (
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      ) : (
                        <Upload className="h-4 w-4 mr-1" />
                      )}
                      {importing ? t.resumeUpload.importing : t.resumeUpload.importAll}
                    </Button>
                  ) : (
                    <Button size="sm" onClick={onStartInterview}>
                      {t.resumeUpload.startInterview}
                      <ArrowRight className="h-4 w-4 ml-1" />
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {result.parsed.projects.map((proj, i) => (
                  <div key={i} className="text-sm">
                    <div className="font-medium">{proj.name}</div>
                    {proj.tech_stack && (
                      <div className="text-xs text-muted-foreground">{proj.tech_stack}</div>
                    )}
                    {proj.description && <p className="text-muted-foreground mt-1">{proj.description}</p>}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}