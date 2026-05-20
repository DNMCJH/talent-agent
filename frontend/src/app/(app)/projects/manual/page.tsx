"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApi, ApiError } from "@/lib/api";
import { useI18n } from "@/i18n/context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { toast } from "sonner";
import { Loader2, ArrowLeft } from "lucide-react";

function csvToList(s: string): string[] {
  return s
    .replace(/[、，]/g, ",")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

export default function ManualProjectPage() {
  const api = useApi();
  const router = useRouter();
  const { t } = useI18n();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [stack, setStack] = useState("");
  const [topics, setTopics] = useState("");
  const [highlights, setHighlights] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [hasTests, setHasTests] = useState(false);
  const [hasDocker, setHasDocker] = useState(false);
  const [deployed, setDeployed] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      toast.error(t.manual.nameLabel);
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/projects/import/manual", {
        name: name.trim(),
        description: description.trim(),
        stack: csvToList(stack),
        topics: csvToList(topics),
        highlights: highlights.split("\n").map((s) => s.trim()).filter(Boolean),
        repo_url: repoUrl.trim() || null,
        has_dockerfile: hasDocker,
        has_tests: hasTests,
        deployment_signal: deployed,
      });
      toast.success(t.manual.created);
      router.push("/projects");
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <Button variant="ghost" size="sm" onClick={() => router.push("/projects")} className="mb-2">
          <ArrowLeft className="h-4 w-4 mr-1" />
          {t.manual.openInProjects}
        </Button>
        <h1 className="text-2xl font-bold tracking-tight">{t.manual.title}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t.manual.subtitle}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t.manual.title}</CardTitle>
          <CardDescription>{t.manual.subtitle}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="name">{t.manual.nameLabel} *</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t.manual.namePlaceholder}
                required
                disabled={submitting}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="description">{t.manual.descLabel}</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t.manual.descPlaceholder}
                rows={4}
                disabled={submitting}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="stack">{t.manual.stackLabel}</Label>
                <Input
                  id="stack"
                  value={stack}
                  onChange={(e) => setStack(e.target.value)}
                  placeholder={t.manual.stackPlaceholder}
                  disabled={submitting}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="topics">{t.manual.topicsLabel}</Label>
                <Input
                  id="topics"
                  value={topics}
                  onChange={(e) => setTopics(e.target.value)}
                  placeholder={t.manual.topicsPlaceholder}
                  disabled={submitting}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="highlights">{t.manual.highlightsLabel}</Label>
              <Textarea
                id="highlights"
                value={highlights}
                onChange={(e) => setHighlights(e.target.value)}
                placeholder={t.manual.highlightsPlaceholder}
                rows={4}
                disabled={submitting}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="repoUrl">{t.manual.repoLabel}</Label>
              <Input
                id="repoUrl"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://..."
                disabled={submitting}
              />
            </div>

            <div className="flex flex-wrap gap-4 text-sm">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasTests}
                  onChange={(e) => setHasTests(e.target.checked)}
                  disabled={submitting}
                />
                {t.manual.hasTests}
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasDocker}
                  onChange={(e) => setHasDocker(e.target.checked)}
                  disabled={submitting}
                />
                {t.manual.hasDocker}
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={deployed}
                  onChange={(e) => setDeployed(e.target.checked)}
                  disabled={submitting}
                />
                {t.manual.deployed}
              </label>
            </div>

            <Button type="submit" disabled={submitting || !name.trim()}>
              {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {submitting ? t.manual.submitting : t.manual.submit}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
