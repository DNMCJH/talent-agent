"use client";

import { useState } from "react";
import { useApi, ApiError } from "@/lib/api";
import { useI18n } from "@/i18n/context";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Loader2, Lightbulb, ChevronRight, Sparkles } from "lucide-react";

type Question = {
  id: string;
  category: string;
  difficulty: string;
  question: string;
  hint?: string;
  company_tags?: string[];
  key_points?: string[];
};

type ScoreResult = {
  score: number;
  summary: string;
  key_points_hit: string[];
  key_points_missed: string[];
  suggestion: string;
};

type Category = { id: string; label_zh: string };

// PLACEHOLDER_CONTINUE

export default function QuizPage() {
  const api = useApi();
  const { t, locale } = useI18n();

  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [difficulty, setDifficulty] = useState<string>("mid");
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  const [question, setQuestion] = useState<Question | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [answer, setAnswer] = useState("");
  const [scoring, setScoring] = useState(false);
  const [result, setResult] = useState<ScoreResult | null>(null);

  // Load categories on first interaction
  async function ensureCategories() {
    if (categories.length > 0) return;
    try {
      const cats = await api.get<Category[]>("/quiz/categories");
      setCategories(cats);
    } catch {
      // silent
    }
  }

  async function drawQuestion() {
    await ensureCategories();
    setLoading(true);
    setQuestion(null);
    setResult(null);
    setAnswer("");
    setShowHint(false);
    try {
      const params = new URLSearchParams({ count: "1" });
      if (selectedCategory) params.set("category", selectedCategory);
      if (difficulty) params.set("difficulty", difficulty);
      const qs = await api.get<Question[]>(`/quiz/questions?${params.toString()}`);
      if (qs.length > 0) setQuestion(qs[0]);
      else toast.error(locale === "zh" ? "该分类暂无题目" : "No questions in this category");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function generateNew() {
    await ensureCategories();
    if (!selectedCategory) {
      toast.error(locale === "zh" ? "请先选择分类" : "Select a category first");
      return;
    }
    setGenerating(true);
    setQuestion(null);
    setResult(null);
    setAnswer("");
    setShowHint(false);
    try {
      const q = await api.post<Question>("/quiz/generate", {
        category: selectedCategory,
        difficulty,
      }, 30_000);
      setQuestion(q);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  }

  async function submitAnswer() {
    if (!question || !answer.trim()) return;
    setScoring(true);
    try {
      const res = await api.post<ScoreResult>("/quiz/score", {
        question_id: question.id,
        answer: answer.trim(),
      }, 30_000);
      setResult(res);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : String(e));
    } finally {
      setScoring(false);
    }
  }

// PLACEHOLDER_RENDER

  const scoreColor = result
    ? result.score >= 7 ? "text-green-600" : result.score >= 5 ? "text-yellow-600" : "text-red-600"
    : "";

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t.quiz.title}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t.quiz.subtitle}</p>
      </div>

      {/* Controls */}
      <Card>
        <CardContent className="pt-6 space-y-4">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="space-y-1">
              <label className="text-xs font-medium">{t.quiz.category}</label>
              <select
                aria-label="Category"
                className="block border rounded-md p-2 bg-background text-sm min-w-[140px]"
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                onFocus={ensureCategories}
              >
                <option value="">{t.quiz.all}</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {locale === "zh" ? c.label_zh : c.id}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">{t.quiz.difficulty}</label>
              <select
                aria-label="Difficulty"
                className="block border rounded-md p-2 bg-background text-sm"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
              >
                <option value="mid">{t.quiz.mid}</option>
                <option value="senior">{t.quiz.senior}</option>
              </select>
            </div>
            <Button onClick={drawQuestion} disabled={loading || generating}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <ChevronRight className="mr-1 h-4 w-4" />
              {t.quiz.draw}
            </Button>
            <Button variant="outline" onClick={generateNew} disabled={loading || generating}>
              {generating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Sparkles className="mr-1 h-4 w-4" />
              {generating ? t.quiz.generating : t.quiz.generate}
            </Button>
          </div>
        </CardContent>
      </Card>

{/* Question card */}
      {question && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="outline">{question.category}</Badge>
              <Badge variant={question.difficulty === "senior" ? "destructive" : "secondary"}>
                {question.difficulty === "senior" ? t.quiz.senior : t.quiz.mid}
              </Badge>
              {question.company_tags?.map((c) => (
                <Badge key={c} variant="secondary" className="text-xs">{c}</Badge>
              ))}
            </div>
            <CardTitle className="text-base mt-2">{question.question}</CardTitle>
            {question.hint && (
              <CardDescription className="pt-1">
                {showHint ? (
                  <span className="flex items-center gap-1">
                    <Lightbulb className="h-3.5 w-3.5 text-yellow-500" />
                    {question.hint}
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowHint(true)}
                    className="text-xs text-primary hover:underline"
                  >
                    {t.quiz.showHint}
                  </button>
                )}
              </CardDescription>
            )}
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              placeholder={t.quiz.yourAnswer}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              rows={6}
              disabled={scoring}
            />
            <div className="flex gap-2">
              <Button onClick={submitAnswer} disabled={scoring || !answer.trim()}>
                {scoring && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {scoring ? t.quiz.scoring : t.quiz.submit}
              </Button>
              <Button variant="outline" onClick={drawQuestion} disabled={loading}>
                {t.quiz.next}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Score result */}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              {t.quiz.score}: <span className={`text-2xl font-bold ${scoreColor}`}>{result.score}/10</span>
            </CardTitle>
            <CardDescription>{result.summary}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {result.key_points_hit.length > 0 && (
              <div>
                <span className="font-medium text-green-700">{t.quiz.hit}:</span>
                <ul className="list-disc pl-5 mt-1 space-y-0.5">
                  {result.key_points_hit.map((p, i) => <li key={i}>{p}</li>)}
                </ul>
              </div>
            )}
            {result.key_points_missed.length > 0 && (
              <div>
                <span className="font-medium text-red-600">{t.quiz.missed}:</span>
                <ul className="list-disc pl-5 mt-1 space-y-0.5">
                  {result.key_points_missed.map((p, i) => <li key={i}>{p}</li>)}
                </ul>
              </div>
            )}
            {result.suggestion && (
              <div className="pt-2 border-t">
                <span className="font-medium">{t.quiz.suggestion}:</span>
                <p className="mt-0.5 text-muted-foreground">{result.suggestion}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

