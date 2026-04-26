"use client";

import { isAxiosError } from "axios";
import { Download, FileText, Loader2, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { listKnowledgeBases, type KnowledgeBase } from "../../../lib/knowledge-bases";
import {
  type SlideProject,
  deleteSlideProject,
  downloadSlideProject,
  generateSlides,
  listSlideProjects,
} from "../../../lib/slides";

function detailMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return err instanceof Error ? err.message : "Failed";
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function SlidesPage() {
  const [projects, setProjects] = useState<SlideProject[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);

  // Form state
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [useRag, setUseRag] = useState(false);
  const [selectedKbIds, setSelectedKbIds] = useState<number[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setProjects(await listSlideProjects());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    (async () => {
      const [pList, kList] = await Promise.all([
        listSlideProjects().catch(() => []),
        listKnowledgeBases().catch(() => []),
      ]);
      setProjects(pList);
      setKnowledgeBases(kList);
      setLoading(false);
    })();
  }, []);

  // Close KB picker on outside click.
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (!pickerRef.current?.contains(e.target as Node)) setPickerOpen(false);
    }
    if (pickerOpen) document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [pickerOpen]);

  function toggleKb(id: number) {
    setSelectedKbIds((cur) =>
      cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id],
    );
  }

  const kbLabel =
    selectedKbIds.length === 0
      ? "All KBs"
      : selectedKbIds.length === 1
        ? knowledgeBases.find((k) => k.id === selectedKbIds[0])?.name ?? "1 KB"
        : `${selectedKbIds.length} KBs`;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!prompt.trim()) return;
    setError(null);
    setGenerating(true);
    try {
      await generateSlides({
        prompt: prompt.trim(),
        title: title.trim() || undefined,
        use_rag: useRag,
        kb_ids: selectedKbIds.length === 0 ? null : selectedKbIds,
      });
      setPrompt("");
      setTitle("");
      await refresh();
    } catch (err) {
      setError(detailMessage(err));
    } finally {
      setGenerating(false);
    }
  }

  async function handleDelete(p: SlideProject) {
    if (!window.confirm(`Delete "${p.title}"?`)) return;
    await deleteSlideProject(p.id);
    setProjects((cur) => cur.filter((x) => x.id !== p.id));
  }

  async function handleDownload(p: SlideProject) {
    try {
      await downloadSlideProject(p.id, p.title);
    } catch (err) {
      setError(detailMessage(err));
    }
  }

  return (
    <section className="h-full overflow-auto px-6 py-6">
      <div className="mx-auto max-w-3xl space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Slides</h1>
          <span className="text-xs text-muted-foreground">
            Mock outline — Presenton-rendered PPTX in a future release
          </span>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-3 rounded-lg border border-border bg-white p-4"
        >
          <div className="space-y-1">
            <label htmlFor="slide-title" className="block text-sm">
              Title (optional)
            </label>
            <input
              id="slide-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              placeholder="Auto-derived from the prompt if blank"
              className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="slide-prompt" className="block text-sm">
              Prompt
            </label>
            <textarea
              id="slide-prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              maxLength={2000}
              rows={4}
              placeholder="e.g. 5-slide intro to React hooks for backend developers"
              className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={useRag}
                  onChange={(e) => setUseRag(e.target.checked)}
                  className="h-3.5 w-3.5"
                />
                Use RAG
              </label>
              <div className="relative" ref={pickerRef}>
                <button
                  type="button"
                  onClick={() => setPickerOpen((o) => !o)}
                  disabled={!useRag || knowledgeBases.length === 0}
                  className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted disabled:opacity-40"
                >
                  {kbLabel} ▾
                </button>
                {pickerOpen ? (
                  <div className="absolute bottom-full mb-1 w-56 max-h-64 overflow-auto rounded-md border border-border bg-white p-2 shadow-lg">
                    {knowledgeBases.length === 0 ? (
                      <div className="px-2 py-1 text-xs text-muted-foreground">
                        No knowledge bases yet
                      </div>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() => setSelectedKbIds([])}
                          className="block w-full rounded px-2 py-1 text-left text-xs hover:bg-muted"
                        >
                          All KBs (clear selection)
                        </button>
                        <div className="my-1 border-t border-border" />
                        {knowledgeBases.map((kb) => (
                          <label
                            key={kb.id}
                            className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs hover:bg-muted"
                          >
                            <input
                              type="checkbox"
                              checked={selectedKbIds.includes(kb.id)}
                              onChange={() => toggleKb(kb.id)}
                              className="h-3.5 w-3.5"
                            />
                            <span className="truncate">{kb.name}</span>
                          </label>
                        ))}
                      </>
                    )}
                  </div>
                ) : null}
              </div>
            </div>
            <button
              type="submit"
              disabled={generating || !prompt.trim()}
              className="flex items-center gap-1 rounded-md bg-foreground px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {generating ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Generating…
                </>
              ) : (
                "Generate"
              )}
            </button>
          </div>
          {error ? (
            <div className="text-xs text-red-600">{error}</div>
          ) : null}
        </form>

        <h2 className="pt-2 text-sm font-medium text-muted-foreground">
          Past projects
        </h2>

        {loading ? (
          <div className="text-sm text-muted-foreground">Loading…</div>
        ) : projects.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-white p-10 text-center text-sm text-muted-foreground">
            No projects yet. Generate one above.
          </div>
        ) : (
          <ul className="space-y-2">
            {projects.map((p) => (
              <li
                key={p.id}
                className="flex items-start gap-3 rounded-lg border border-border bg-white px-4 py-3"
              >
                <FileText className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium" title={p.title}>
                    {p.title}
                  </div>
                  <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                    {p.prompt}
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
                    <span>{formatTime(p.created_at)}</span>
                    {p.use_rag ? (
                      <span className="rounded bg-muted px-1.5 py-0.5">RAG</span>
                    ) : null}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleDownload(p)}
                  aria-label={`Download ${p.title}`}
                  className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted"
                >
                  <Download className="h-3.5 w-3.5" /> Download
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(p)}
                  aria-label={`Delete ${p.title}`}
                  className="rounded-md border border-border px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
