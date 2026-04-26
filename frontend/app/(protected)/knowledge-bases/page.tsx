"use client";

import { ChevronDown, ChevronRight, Pencil, Trash2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { isAxiosError } from "axios";

import { DropUpload } from "../../../components/DropUpload";
import {
  type KnowledgeBase,
  type KnowledgeFile,
  createKnowledgeBase,
  deleteFile,
  deleteKnowledgeBase,
  listFiles,
  listKnowledgeBases,
  updateKnowledgeBase,
} from "../../../lib/knowledge-bases";

function detailMessage(err: unknown, fallbackMap: Record<string, string>): string {
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") {
      return fallbackMap[detail] ?? detail;
    }
  }
  return err instanceof Error ? err.message : "Unexpected error";
}

export default function KnowledgeBasesPage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [creatingOpen, setCreatingOpen] = useState(false);

  async function refresh() {
    try {
      setKbs(await listKnowledgeBases());
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleDeleteKb(kb: KnowledgeBase) {
    if (!window.confirm(`Delete "${kb.name}" and all its files?`)) return;
    await deleteKnowledgeBase(kb.id);
    setKbs((cur) => cur.filter((k) => k.id !== kb.id));
  }

  return (
    <section className="h-full overflow-auto px-6 py-6">
      <div className="mx-auto max-w-3xl space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Knowledge Bases</h1>
          <button
            type="button"
            onClick={() => setCreatingOpen((o) => !o)}
            className="rounded-md bg-foreground px-3 py-1.5 text-sm text-white"
          >
            + New KB
          </button>
        </div>

        {creatingOpen ? (
          <NewKbForm
            onCancel={() => setCreatingOpen(false)}
            onCreated={async () => {
              setCreatingOpen(false);
              await refresh();
            }}
          />
        ) : null}

        {loading ? (
          <div className="text-sm text-muted-foreground">Loading…</div>
        ) : kbs.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-white p-10 text-center text-sm text-muted-foreground">
            No knowledge bases yet. Click "+ New KB" to create one.
          </div>
        ) : (
          <ul className="space-y-2">
            {kbs.map((kb) => (
              <KbRow key={kb.id} kb={kb} onDelete={() => handleDeleteKb(kb)} />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function NewKbForm({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      await createKnowledgeBase({
        name: name.trim(),
        description: description.trim() || null,
      });
      onCreated();
    } catch (err) {
      setError(
        detailMessage(err, {
          duplicate_kb_name: "A knowledge base with this name already exists",
        }),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3 rounded-lg border border-border bg-white p-4"
    >
      <div className="space-y-1">
        <label htmlFor="kb-name" className="block text-sm">Name</label>
        <input
          id="kb-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={100}
          autoFocus
          className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm"
        />
      </div>
      <div className="space-y-1">
        <label htmlFor="kb-desc" className="block text-sm">Description (optional)</label>
        <textarea
          id="kb-desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={500}
          rows={2}
          className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm"
        />
      </div>
      {error ? (
        <div className="text-sm text-red-600">{error}</div>
      ) : null}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-border bg-white px-3 py-1.5 text-sm hover:bg-muted"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={submitting || !name.trim()}
          className="rounded-md bg-foreground px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {submitting ? "..." : "Create"}
        </button>
      </div>
    </form>
  );
}

function KbRow({ kb, onDelete }: { kb: KnowledgeBase; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [files, setFiles] = useState<KnowledgeFile[] | null>(null);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [fileCount, setFileCount] = useState(kb.file_count);
  // Local copy of name/description so renames are visible without re-fetching
  // the parent list. The pencil button toggles editing.
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(kb.name);
  const [description, setDescription] = useState(kb.description ?? "");
  const [draftName, setDraftName] = useState(kb.name);
  const [draftDesc, setDraftDesc] = useState(kb.description ?? "");
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  async function loadFiles() {
    setLoadingFiles(true);
    try {
      const list = await listFiles(kb.id);
      setFiles(list);
      setFileCount(list.length);
    } finally {
      setLoadingFiles(false);
    }
  }

  function toggle() {
    if (editing) return;
    const next = !expanded;
    setExpanded(next);
    if (next && files === null) loadFiles();
  }

  function startEdit(ev: React.MouseEvent) {
    ev.stopPropagation();
    setDraftName(name);
    setDraftDesc(description);
    setEditError(null);
    setEditing(true);
  }

  function cancelEdit() {
    setEditing(false);
    setEditError(null);
  }

  async function saveEdit() {
    const trimmed = draftName.trim();
    if (!trimmed) return;
    setSaving(true);
    setEditError(null);
    try {
      const updated = await updateKnowledgeBase(kb.id, {
        name: trimmed,
        description: draftDesc.trim(),
      });
      setName(updated.name);
      setDescription(updated.description ?? "");
      setEditing(false);
    } catch (err) {
      setEditError(
        detailMessage(err, {
          duplicate_kb_name: "A knowledge base with this name already exists",
          kb_not_found: "Knowledge base not found",
        }),
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteFile(file: KnowledgeFile) {
    if (!window.confirm(`Delete "${file.filename}"?`)) return;
    await deleteFile(kb.id, file.id);
    await loadFiles();
  }

  return (
    <li className="rounded-lg border border-border bg-white">
      <div className="flex items-center justify-between px-4 py-3">
        <button
          type="button"
          onClick={toggle}
          className="flex flex-1 items-center gap-2 text-left"
          aria-expanded={expanded}
          disabled={editing}
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <div className="min-w-0 flex-1">
            {editing ? (
              <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
                <input
                  value={draftName}
                  onChange={(e) => setDraftName(e.target.value)}
                  maxLength={100}
                  autoFocus
                  className="w-full rounded-md border border-border bg-white px-2 py-1 text-sm"
                />
                <textarea
                  value={draftDesc}
                  onChange={(e) => setDraftDesc(e.target.value)}
                  maxLength={500}
                  rows={2}
                  placeholder="Description (optional)"
                  className="w-full rounded-md border border-border bg-white px-2 py-1 text-xs"
                />
                {editError ? (
                  <div className="text-xs text-red-600">{editError}</div>
                ) : null}
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={cancelEdit}
                    className="rounded-md border border-border bg-white px-2 py-1 text-xs hover:bg-muted"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={saveEdit}
                    disabled={saving || !draftName.trim()}
                    className="rounded-md bg-foreground px-2 py-1 text-xs text-white disabled:opacity-50"
                  >
                    {saving ? "..." : "Save"}
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="text-sm font-medium">{name}</div>
                <div className="text-xs text-muted-foreground">
                  {fileCount} {fileCount === 1 ? "file" : "files"}
                  {description ? ` · ${description}` : ""}
                </div>
              </>
            )}
          </div>
        </button>
        {!editing ? (
          <button
            type="button"
            onClick={startEdit}
            aria-label={`Edit ${name}`}
            className="ml-2 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        ) : null}
        <button
          type="button"
          onClick={onDelete}
          aria-label={`Delete ${name}`}
          disabled={editing}
          className="ml-2 rounded-md border border-border px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-40"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      {expanded ? (
        <div className="border-t border-border px-4 py-3 space-y-3">
          <DropUpload kbId={kb.id} onAllUploaded={loadFiles} />
          {loadingFiles ? (
            <div className="text-xs text-muted-foreground">Loading files…</div>
          ) : files && files.length > 0 ? (
            <ul className="divide-y divide-border rounded-md border border-border">
              {files.map((f) => (
                <li key={f.id} className="flex items-center justify-between px-3 py-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm">{f.filename}</div>
                    <div className="text-xs text-muted-foreground">
                      {f.extension.toUpperCase()} · {humanSize(f.size_bytes)} ·{" "}
                      <StatusBadge status={f.status} error={f.status_error} />
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteFile(f)}
                    aria-label={`Delete ${f.filename}`}
                    className="ml-2 rounded-md border border-border px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                  >
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="rounded-md border border-dashed border-border px-3 py-4 text-center text-xs text-muted-foreground">
              No files yet.
            </div>
          )}
        </div>
      ) : null}
    </li>
  );
}

function StatusBadge({ status, error }: { status: string; error: string | null }) {
  const label =
    status === "uploaded"
      ? "Pending processing"
      : status === "indexed"
        ? "Indexed"
        : status === "failed"
          ? "Failed"
          : status;
  const tone =
    status === "indexed"
      ? "text-emerald-600"
      : status === "failed"
        ? "text-red-600"
        : "text-muted-foreground";
  return (
    <span className={tone} title={error ?? ""}>
      {label}
    </span>
  );
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
