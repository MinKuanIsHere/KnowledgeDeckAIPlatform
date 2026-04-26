"use client";

import { isAxiosError } from "axios";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { useKbStore } from "../../../lib/kb-store";
import { useSlideStore } from "../../../lib/slide-store";
import { generateSlides } from "../../../lib/slides";

function detailMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return err instanceof Error ? err.message : "Failed";
}

export default function SlidesIndexPage() {
  const router = useRouter();

  const knowledgeBases = useKbStore((s) => s.kbs);
  const kbsLoaded = useKbStore((s) => s.loaded);
  const refreshKbs = useKbStore((s) => s.refresh);
  const addProject = useSlideStore((s) => s.add);

  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [useRag, setUseRag] = useState(true);
  const [selectedKbIds, setSelectedKbIds] = useState<number[]>([]);
  const [pickerInitialized, setPickerInitialized] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement | null>(null);

  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!kbsLoaded) refreshKbs();
  }, [kbsLoaded, refreshKbs]);

  // Default to all KBs checked once the list arrives, matching ChatInput.
  useEffect(() => {
    if (pickerInitialized) return;
    if (knowledgeBases.length === 0) return;
    setSelectedKbIds(knowledgeBases.map((k) => k.id));
    setPickerInitialized(true);
  }, [knowledgeBases, pickerInitialized]);

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

  const allSelected =
    knowledgeBases.length > 0 &&
    selectedKbIds.length === knowledgeBases.length;
  const kbLabel =
    selectedKbIds.length === 0 || allSelected
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
      const project = await generateSlides({
        prompt: prompt.trim(),
        title: title.trim() || undefined,
        use_rag: useRag,
        kb_ids: selectedKbIds.length === 0 ? null : selectedKbIds,
      });
      addProject(project);
      // Land the user on the detail page so they can read the outline / download.
      router.push(`/slides/${project.id}`);
    } catch (err) {
      setError(detailMessage(err));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <section className="h-full overflow-auto px-6 py-6">
      <div className="mx-auto max-w-3xl space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Slide Maker</h1>
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
                        <div className="flex gap-1 px-1 pb-1">
                          <button
                            type="button"
                            onClick={() =>
                              setSelectedKbIds(knowledgeBases.map((k) => k.id))
                            }
                            className="flex-1 rounded px-2 py-1 text-xs hover:bg-muted"
                          >
                            Select all
                          </button>
                          <button
                            type="button"
                            onClick={() => setSelectedKbIds([])}
                            className="flex-1 rounded px-2 py-1 text-xs hover:bg-muted"
                          >
                            Clear
                          </button>
                        </div>
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

        <div className="rounded-md border border-dashed border-border bg-white p-4 text-xs text-muted-foreground">
          Past projects appear in the sidebar. Click one to see its outline
          and download.
        </div>
      </div>
    </section>
  );
}
