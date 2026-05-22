"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ExternalLink, Loader2, Plus, Trash2 } from "lucide-react";
import { useApi, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { useI18n } from "@/i18n/context";

type Application = {
  id: number;
  company: string;
  role: string;
  status: string;
  link: string | null;
  notes: string;
};

const STATUSES = ["saved", "applied", "interviewing", "offer", "rejected"] as const;

export default function ApplicationsPage() {
  const api = useApi();
  const { t, locale } = useI18n();
  const [items, setItems] = useState<Application[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [link, setLink] = useState("");
  const [notes, setNotes] = useState("");

  const statusLabel = useCallback(
    (s: string) => (t.applications.status as Record<string, string>)[s] ?? s,
    [t],
  );

  const load = useCallback(async () => {
    if (!api.token) return;
    try {
      const rows = await api.get<Application[]>("/applications");
      setItems(rows);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(msg);
      setItems([]);
    }
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  async function onAdd() {
    if (!company.trim() || !role.trim()) return;
    setAdding(true);
    try {
      await api.post<Application>("/applications", {
        company: company.trim(),
        role: role.trim(),
        link: link.trim() || null,
        notes: notes.trim(),
        status: "saved",
      });
      setCompany("");
      setRole("");
      setLink("");
      setNotes("");
      await load();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error(msg);
    } finally {
      setAdding(false);
    }
  }

  async function onStatusChange(id: number, status: string) {
    // Optimistic: reflect the new status immediately, roll back on failure.
    setItems((prev) =>
      prev ? prev.map((a) => (a.id === id ? { ...a, status } : a)) : prev,
    );
    try {
      await api.patch<Application>(`/applications/${id}`, { status });
    } catch {
      toast.error(locale === "zh" ? "更新失败，请重试" : "Update failed, please retry");
      await load();
    }
  }

  async function onDelete(id: number) {
    setItems((prev) => (prev ? prev.filter((a) => a.id !== id) : prev));
    try {
      await api.del(`/applications/${id}`);
    } catch {
      toast.error(locale === "zh" ? "删除失败，请重试" : "Delete failed, please retry");
      await load();
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
          {t.applications.eyebrow}
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          {t.applications.title}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">{t.applications.subtitle}</p>
      </div>

      {/* Add form */}
      <details className="group overflow-hidden rounded-xl bg-card ring-1 ring-foreground/10">
        <summary className="flex cursor-pointer items-center justify-between px-5 py-4 text-sm font-medium">
          <span className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            {t.applications.addTitle}
          </span>
          <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" />
        </summary>
        <div className="space-y-3 border-t px-5 py-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              className="rounded-md border bg-background p-2 text-sm"
              placeholder={t.applications.company}
              value={company}
              onChange={(e) => setCompany(e.target.value)}
            />
            <input
              className="rounded-md border bg-background p-2 text-sm"
              placeholder={t.applications.role}
              value={role}
              onChange={(e) => setRole(e.target.value)}
            />
          </div>
          <input
            className="w-full rounded-md border bg-background p-2 text-sm"
            placeholder={t.applications.link}
            value={link}
            onChange={(e) => setLink(e.target.value)}
          />
          <Textarea
            placeholder={t.applications.notes}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
          />
          <Button
            size="sm"
            onClick={onAdd}
            disabled={adding || !company.trim() || !role.trim()}
          >
            {adding && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {t.applications.add}
          </Button>
        </div>
      </details>

      {/* List */}
      {items === null ? (
        <p className="py-12 text-center text-sm text-muted-foreground">
          {t.applications.loading}
        </p>
      ) : items.length === 0 ? (
        <div className="flex min-h-[160px] items-center justify-center rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          {t.applications.empty}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border bg-card">
          {items.map((a) => (
            <div
              key={a.id}
              className="grid grid-cols-12 items-start gap-3 border-b px-5 py-4 last:border-b-0"
            >
              <div className="col-span-12 sm:col-span-6">
                <div className="flex items-center gap-1.5">
                  <h3 className="text-sm font-medium tracking-tight">{a.company}</h3>
                  {a.link && (
                    <a
                      href={a.link}
                      target="_blank"
                      rel="noreferrer"
                      aria-label="open link"
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">{a.role}</p>
                {a.notes && (
                  <p className="mt-1 text-xs text-muted-foreground">{a.notes}</p>
                )}
              </div>
              <div className="col-span-8 sm:col-span-4">
                <select
                  aria-label="status"
                  className="w-full rounded-md border bg-background p-1.5 text-xs"
                  value={a.status}
                  onChange={(e) => onStatusChange(a.id, e.target.value)}
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {statusLabel(s)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-span-4 flex justify-end sm:col-span-2">
                <button
                  type="button"
                  onClick={() => onDelete(a.id)}
                  aria-label="delete"
                  className="text-muted-foreground transition-colors hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
