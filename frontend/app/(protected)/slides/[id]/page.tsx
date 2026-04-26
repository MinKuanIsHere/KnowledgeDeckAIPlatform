"use client";

import { isAxiosError } from "axios";
import { Download, Pencil, Trash2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useSlideStore } from "../../../../lib/slide-store";
import {
  type SlideProjectDetail,
  downloadSlideProject,
  getSlideProject,
} from "../../../../lib/slides";

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

export default function SlideProjectDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  const removeProject = useSlideStore((s) => s.remove);
  const renameProject = useSlideStore((s) => s.rename);
  // Hydrate the slide store so the sidebar list shows up alongside this page.
  const slidesLoaded = useSlideStore((s) => s.loaded);
  const refreshSlides = useSlideStore((s) => s.refresh);

  const [detail, setDetail] = useState<SlideProjectDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!slidesLoaded) refreshSlides();
  }, [slidesLoaded, refreshSlides]);

  useEffect(() => {
    if (!Number.isFinite(projectId)) return;
    let cancelled = false;
    setDetail(null);
    setLoadError(null);
    getSlideProject(projectId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(detailMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  async function handleDelete() {
    if (!detail) return;
    if (!window.confirm(`Delete "${detail.title}"?`)) return;
    await removeProject(detail.id);
    router.push("/slides");
  }

  async function handleRename(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!detail) return;
    const trimmed = draftTitle.trim();
    if (!trimmed) return;
    setSaving(true);
    setRenameError(null);
    try {
      await renameProject(detail.id, trimmed);
      setDetail((d) => (d ? { ...d, title: trimmed } : d));
      setEditing(false);
    } catch (err) {
      setRenameError(detailMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDownload() {
    if (!detail) return;
    try {
      await downloadSlideProject(detail.id, detail.title);
    } catch (err) {
      setLoadError(detailMessage(err));
    }
  }

  if (loadError) {
    return (
      <section className="h-full overflow-auto px-6 py-6">
        <div className="mx-auto max-w-3xl">
          <div className="rounded-lg border border-dashed border-border bg-white p-10 text-center text-sm text-red-600">
            {loadError}
          </div>
        </div>
      </section>
    );
  }
  if (!detail) {
    return (
      <section className="h-full overflow-auto px-6 py-6">
        <div className="mx-auto max-w-3xl text-sm text-muted-foreground">
          Loading…
        </div>
      </section>
    );
  }

  return (
    <section className="h-full overflow-auto px-6 py-6">
      <div className="mx-auto max-w-3xl space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            {editing ? (
              <form onSubmit={handleRename} className="space-y-2">
                <input
                  value={draftTitle}
                  onChange={(e) => setDraftTitle(e.target.value)}
                  maxLength={200}
                  autoFocus
                  className="w-full rounded-md border border-border bg-white px-3 py-2 text-base"
                />
                {renameError ? (
                  <div className="text-xs text-red-600">{renameError}</div>
                ) : null}
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setEditing(false)}
                    className="rounded-md border border-border bg-white px-3 py-1 text-xs hover:bg-muted"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={saving || !draftTitle.trim()}
                    className="rounded-md bg-foreground px-3 py-1 text-xs text-white disabled:opacity-50"
                  >
                    {saving ? "..." : "Save"}
                  </button>
                </div>
              </form>
            ) : (
              <>
                <h1 className="truncate text-xl font-semibold">{detail.title}</h1>
                <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>{formatTime(detail.created_at)}</span>
                  {detail.use_rag ? (
                    <span className="rounded bg-muted px-1.5 py-0.5">RAG</span>
                  ) : null}
                </div>
              </>
            )}
          </div>
          {!editing ? (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setDraftTitle(detail.title);
                  setRenameError(null);
                  setEditing(true);
                }}
                aria-label="Rename"
                className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={handleDownload}
                className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted"
              >
                <Download className="h-3.5 w-3.5" /> Download
              </button>
              <button
                type="button"
                onClick={handleDelete}
                aria-label="Delete"
                className="rounded-md border border-border px-2 py-1 text-xs text-red-600 hover:bg-red-50"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : null}
        </div>

        <div className="rounded-lg border border-border bg-white p-4">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            Prompt
          </div>
          <div className="mt-1 whitespace-pre-wrap text-sm">{detail.prompt}</div>
        </div>

        <div className="rounded-lg border border-border bg-white p-4">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            Outline (preview)
          </div>
          <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-xs text-foreground">
            {detail.outline}
          </pre>
        </div>
      </div>
    </section>
  );
}
