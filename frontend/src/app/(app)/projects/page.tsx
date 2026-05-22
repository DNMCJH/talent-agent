"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import useSWR, { mutate } from "swr";
import { useApi, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Trash2,
  Loader2,
  GitFork,
  Search,
  CheckSquare,
  Square,
  Upload,
  PencilLine,
  ChevronDown,
} from "lucide-react";
import { useI18n } from "@/i18n/context";

type Project = {
  id: number;
  name: string;
  source: string;
  github_url: string | null;
  analysis_depth: string;
};

type GHRepo = {
  full_name: string;
  html_url: string;
  description: string | null;
  language: string | null;
  stargazers_count: number;
  pushed_at: string;
};

type ImportStatus = {
  url: string;
  name: string;
  state: "pending" | "importing" | "done" | "error";
  error?: string;
};

function RepoBrowser({
  open,
  onOpenChange,
  onImportSelected,
  importedUrls,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onImportSelected: (repos: GHRepo[]) => void;
  importedUrls: Set<string>;
}) {
  const { data: session } = useSession();
  const api = useApi();
  const { t, locale } = useI18n();
  const ghToken = session?.githubAccessToken;
  const [repos, setRepos] = useState<GHRepo[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [username, setUsername] = useState("");

  const fetchRepos = useCallback(async () => {
    if (!ghToken) return;
    setLoading(true);
    try {
      const res = await fetch(
        "https://api.github.com/user/repos?sort=pushed&per_page=100&type=owner",
        { headers: { Authorization: `Bearer ${ghToken}` } },
      );
      if (!res.ok) throw new Error(`GitHub API ${res.status}`);
      const data: GHRepo[] = await res.json();
      setRepos(data);
    } catch (e) {
      toast.error(`Failed to fetch repos: ${e}`);
    } finally {
      setLoading(false);
    }
  }, [ghToken]);

  async function fetchByUsername() {
    if (!username.trim()) return;
    setLoading(true);
    try {
      const data = await api.post<GHRepo[]>("/projects/repos/github-user", {
        username: username.trim(),
        github_token: ghToken,
      });
      setRepos(data);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (open && ghToken && repos.length === 0) fetchRepos();
  }, [open, fetchRepos, ghToken, repos.length]);

  const filtered = repos.filter(
    (r) =>
      r.full_name.toLowerCase().includes(search.toLowerCase()) ||
      (r.description ?? "").toLowerCase().includes(search.toLowerCase()),
  );

  function toggle(url: string) {
    if (importedUrls.has(url)) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  }

  function onConfirm() {
    const chosen = repos.filter((r) => selected.has(r.html_url));
    onImportSelected(chosen);
    onOpenChange(false);
    setSelected(new Set());
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>{t.repoBrowser.title}</DialogTitle>
          <DialogDescription>{t.repoBrowser.desc}</DialogDescription>
        </DialogHeader>
        {!ghToken && repos.length === 0 && (
          <div className="flex gap-2">
            <Input
              placeholder={locale === "zh" ? "输入 GitHub 用户名" : "GitHub username"}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && fetchByUsername()}
            />
            <Button type="button" onClick={fetchByUsername} disabled={loading || !username.trim()}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            </Button>
          </div>
        )}
        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t.repoBrowser.filter}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
        <div className="flex-1 overflow-y-auto space-y-1 min-h-0 max-h-[50vh]">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          )}
          {!loading && filtered.length === 0 && (
            <p className="text-sm text-muted-foreground py-4 text-center">
              {t.repoBrowser.noRepos}
            </p>
          )}
          {filtered.map((r) => {
            const alreadyImported = importedUrls.has(r.html_url);
            return (
              <div
                key={r.html_url}
                className={`flex items-center gap-3 p-2 rounded ${
                  alreadyImported
                    ? "opacity-50 cursor-default"
                    : "hover:bg-muted cursor-pointer"
                }`}
                onClick={() => toggle(r.html_url)}
              >
                {alreadyImported ? (
                  <CheckSquare className="h-4 w-4 text-muted-foreground shrink-0" />
                ) : selected.has(r.html_url) ? (
                  <CheckSquare className="h-4 w-4 text-primary shrink-0" />
                ) : (
                  <Square className="h-4 w-4 text-muted-foreground shrink-0" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">
                      {r.full_name}
                    </span>
                    {alreadyImported && (
                      <Badge variant="outline" className="text-xs shrink-0">
                        {t.repoBrowser.imported}
                      </Badge>
                    )}
                    {r.language && (
                      <Badge variant="secondary" className="text-xs shrink-0">
                        {r.language}
                      </Badge>
                    )}
                    {r.stargazers_count > 0 && (
                      <span className="text-xs text-muted-foreground shrink-0">
                        ★ {r.stargazers_count}
                      </span>
                    )}
                  </div>
                  {r.description && (
                    <p className="text-xs text-muted-foreground truncate">
                      {r.description}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <DialogFooter>
          <Button
            onClick={onConfirm}
            disabled={selected.size === 0}
          >
            {t.repoBrowser.importN.replace("{n}", String(selected.size))}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ProjectsPage() {
  const api = useApi();
  const { t } = useI18n();
  const { data: session } = useSession();
  const ghToken = session?.githubAccessToken;
  const [url, setUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [browseOpen, setBrowseOpen] = useState(false);
  const [batchStatus, setBatchStatus] = useState<ImportStatus[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data, error, isLoading } = useSWR<Project[]>(
    api.token ? "/projects" : null,
    () => api.get<Project[]>("/projects"),
  );

  async function onImportSingle() {
    if (!url.trim()) return;
    setImporting(true);
    try {
      await api.post("/projects/import/github", {
        github_url: url.trim(),
        github_token: ghToken,
      });
      toast.success(t.projects.imported);
      setUrl("");
      mutate("/projects");
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(msg);
    } finally {
      setImporting(false);
    }
  }

  async function onBatchImport(repos: GHRepo[]) {
    const statuses: ImportStatus[] = repos.map((r) => ({
      url: r.html_url,
      name: r.full_name,
      state: "pending" as const,
    }));
    setBatchStatus([...statuses]);

    for (let i = 0; i < statuses.length; i++) {
      statuses[i].state = "importing";
      setBatchStatus([...statuses]);
      try {
        await api.post("/projects/import/github", {
          github_url: statuses[i].url,
          github_token: ghToken,
        });
        statuses[i].state = "done";
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) {
          statuses[i].state = "done";
        } else {
          statuses[i].state = "error";
          statuses[i].error =
            e instanceof ApiError ? e.message : String(e);
        }
      }
      setBatchStatus([...statuses]);
      mutate("/projects");
    }

    const ok = statuses.filter((s) => s.state === "done").length;
    const fail = statuses.filter((s) => s.state === "error").length;
    if (ok > 0) toast.success(`Imported ${ok} project${ok > 1 ? "s" : ""}`);
    if (fail > 0) toast.error(`${fail} failed — try again later`);
    mutate("/projects");
  }

  async function onDelete(id: number) {
    if (!confirm(t.projects.deleteConfirm)) return;
    try {
      await api.del(`/projects/${id}`);
      toast.success(t.projects.deleted);
      mutate("/projects");
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(msg);
    }
  }

  async function onUploadFile(file: File) {
    if (!file.name.endsWith(".zip")) {
      toast.error("Only .zip files are supported");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      toast.error("File too large (max 50MB)");
      return;
    }
    setUploading(true);
    try {
      await api.upload("/projects/import/upload", file, 120000);
      toast.success(t.projects.uploadSuccess);
      mutate("/projects");
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(msg);
    } finally {
      setUploading(false);
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t.projects.title}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {t.projects.subtitle}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t.projects.importTitle}</CardTitle>
          <CardDescription>{t.projects.importDesc}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button
            variant="default"
            onClick={() => setBrowseOpen(true)}
            className="w-full"
          >
            <GitFork className="mr-2 h-4 w-4" />
            {t.projects.browse}
          </Button>
          <details className="text-sm">
            <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
              {t.projects.browseByUrl}
            </summary>
            <div className="flex gap-2 mt-2">
              <Input
                placeholder={t.projects.placeholder}
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={importing}
              />
              <Button
                onClick={onImportSingle}
                disabled={importing || !url.trim()}
                size="sm"
              >
                {importing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {t.projects.import}
              </Button>
            </div>
          </details>
        </CardContent>
      </Card>

      {/* Secondary import paths — zip upload and manual entry are lower
          frequency, so they collapse by default and let GitHub import lead. */}
      <details className="group overflow-hidden rounded-xl bg-card ring-1 ring-foreground/10">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-4 [&::-webkit-details-marker]:hidden">
          <div className="min-w-0">
            <p className="text-base font-medium leading-snug">{t.projects.uploadTitle}</p>
            <p className="text-sm text-muted-foreground">{t.projects.uploadDesc}</p>
          </div>
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
        </summary>
        <div className="px-4 pb-4">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              dragOver ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/50"
            }`}
          >
            {uploading ? (
              <div className="flex flex-col items-center gap-2">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">{t.projects.uploading}</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <Upload className="h-8 w-8 text-muted-foreground" />
                <p className="text-sm font-medium">{t.projects.uploadDrop}</p>
                <p className="text-xs text-muted-foreground">{t.projects.uploadBrowse}</p>
                <p className="text-xs text-muted-foreground">{t.projects.uploadHint}</p>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              className="hidden"
              onChange={onFileSelect}
              aria-label="Upload project zip file"
            />
          </div>
        </div>
      </details>

      <details className="group overflow-hidden rounded-xl bg-card ring-1 ring-foreground/10">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-4 [&::-webkit-details-marker]:hidden">
          <div className="min-w-0">
            <p className="text-base font-medium leading-snug">{t.manual.title}</p>
            <p className="text-sm text-muted-foreground">{t.manual.subtitle}</p>
          </div>
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
        </summary>
        <div className="px-4 pb-4">
          <Link
            href="/projects/manual"
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
          >
            <PencilLine className="h-4 w-4" />
            {t.manual.submit}
          </Link>
        </div>
      </details>

      {/* Batch import progress */}
      {batchStatus.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t.projects.progress}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {batchStatus.map((s) => (
              <div key={s.url} className="flex items-center gap-2 text-sm">
                {s.state === "pending" && (
                  <Square className="h-3 w-3 text-muted-foreground" />
                )}
                {s.state === "importing" && (
                  <Loader2 className="h-3 w-3 animate-spin text-primary" />
                )}
                {s.state === "done" && (
                  <CheckSquare className="h-3 w-3 text-green-600" />
                )}
                {s.state === "error" && (
                  <span className="h-3 w-3 text-destructive font-bold">✗</span>
                )}
                <span className={s.state === "error" ? "text-destructive" : ""}>
                  {s.name}
                </span>
                {s.error && (
                  <span className="text-xs text-muted-foreground ml-auto truncate max-w-[200px]">
                    {s.error}
                  </span>
                )}
              </div>
            ))}
            {batchStatus.every(
              (s) => s.state === "done" || s.state === "error",
            ) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setBatchStatus([])}
                className="mt-2"
              >
                OK
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {/* Project list */}
      <div className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t.projects.yourProjects}
        </h2>
        {isLoading && (
          <p className="text-sm text-muted-foreground">{t.projects.loading}</p>
        )}
        {error && (
          <p className="text-sm text-destructive">
            Failed to load: {String(error)}
          </p>
        )}
        {data && data.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {t.projects.none}
          </p>
        )}
        {data?.map((p) => (
          <Card key={p.id}>
            <CardContent className="flex items-center justify-between py-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{p.name}</span>
                  <Badge variant="secondary">{p.source}</Badge>
                  <Badge variant="outline">{p.analysis_depth}</Badge>
                </div>
                {p.github_url && (
                  <a
                    href={p.github_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-muted-foreground hover:underline"
                  >
                    {p.github_url}
                  </a>
                )}
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onDelete(p.id)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      <RepoBrowser
        open={browseOpen}
        onOpenChange={setBrowseOpen}
        onImportSelected={onBatchImport}
        importedUrls={new Set(data?.map((p) => p.github_url).filter(Boolean) as string[])}
      />
    </div>
  );
}
