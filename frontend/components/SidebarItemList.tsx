"use client";

import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { useEffect, useState, type KeyboardEvent } from "react";

export type SidebarItem = {
  id: number;
  title: string;
};

type Props = {
  /** Header label shown above the list (e.g. "Chats", "Knowledge Bases"). */
  label: string;
  items: SidebarItem[];
  loaded: boolean;
  /** id of the row to highlight, if any. */
  activeId: number | null;
  /** Optional new-item handler. When omitted, the +/empty buttons are hidden. */
  onCreate?: () => Promise<void> | void;
  onSelect: (id: number) => void;
  onDelete: (id: number) => Promise<void> | void;
  /** When omitted, the pencil button is hidden. */
  onRename?: (id: number, newTitle: string) => Promise<void>;
  /** Customize the empty state copy. */
  emptyLabel?: string;
};

/**
 * Generic sidebar list used by Chat sessions, Knowledge Bases, and Slide
 * projects. Each row supports inline rename (when onRename is provided) and
 * a delete action confirmed via window.confirm.
 */
export function SidebarItemList({
  label,
  items,
  loaded,
  activeId,
  onCreate,
  onSelect,
  onDelete,
  onRename,
  emptyLabel,
}: Props) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");

  // Cancel pending rename when items change underneath us (e.g., delete).
  useEffect(() => {
    if (editingId != null && !items.some((i) => i.id === editingId)) {
      setEditingId(null);
    }
  }, [items, editingId]);

  function startRename(item: SidebarItem) {
    setDraft(item.title);
    setEditingId(item.id);
  }

  function cancelRename() {
    setEditingId(null);
  }

  async function commitRename(id: number) {
    const trimmed = draft.trim();
    if (!trimmed || !onRename) {
      setEditingId(null);
      return;
    }
    try {
      await onRename(id, trimmed);
    } finally {
      setEditingId(null);
    }
  }

  function onKey(e: KeyboardEvent<HTMLInputElement>, id: number) {
    if (e.key === "Enter") {
      e.preventDefault();
      commitRename(id);
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancelRename();
    }
  }

  async function handleDelete(id: number, title: string) {
    if (!window.confirm(`Delete "${title}"?`)) return;
    await onDelete(id);
  }

  return (
    <>
      <div className="flex items-center justify-between border-t border-border px-3 pt-3 text-xs text-muted-foreground">
        <span>{label}</span>
        {onCreate ? (
          <button
            type="button"
            onClick={() => onCreate()}
            aria-label={`New ${label}`}
            className="rounded p-1 hover:bg-muted hover:text-foreground"
          >
            <Plus className="h-4 w-4" />
          </button>
        ) : null}
      </div>
      <div className="flex-1 overflow-auto px-2 py-2">
        {!loaded ? (
          <div className="px-3 py-2 text-xs text-muted-foreground">Loading…</div>
        ) : items.length === 0 ? (
          onCreate ? (
            <button
              type="button"
              onClick={() => onCreate()}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <Plus className="h-4 w-4" />
              {emptyLabel ?? `New ${label}`}
            </button>
          ) : (
            <div className="px-3 py-2 text-xs text-muted-foreground">
              {emptyLabel ?? `No ${label.toLowerCase()} yet.`}
            </div>
          )
        ) : (
          <ul className="space-y-1">
            {items.map((item) => {
              const isActive = item.id === activeId;
              const isEditing = item.id === editingId;
              return (
                <li
                  key={item.id}
                  className={`group flex items-center gap-1 rounded-md px-2 py-1.5 text-sm ${
                    isActive
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  {isEditing ? (
                    <>
                      <input
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={(e) => onKey(e, item.id)}
                        autoFocus
                        className="flex-1 rounded border border-border bg-white px-1.5 py-0.5 text-xs text-foreground"
                        maxLength={200}
                      />
                      <button
                        type="button"
                        onClick={() => commitRename(item.id)}
                        aria-label="Save"
                        className="rounded p-1 hover:text-foreground"
                      >
                        <Check className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={cancelRename}
                        aria-label="Cancel rename"
                        className="rounded p-1 hover:text-foreground"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => onSelect(item.id)}
                        className="flex-1 truncate text-left"
                        title={item.title}
                      >
                        {item.title}
                      </button>
                      {onRename ? (
                        <button
                          type="button"
                          onClick={() => startRename(item)}
                          aria-label={`Rename ${item.title}`}
                          className="hidden rounded p-1 hover:text-foreground group-hover:block"
                        >
                          <Pencil className="h-3 w-3" />
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => handleDelete(item.id, item.title)}
                        aria-label={`Delete ${item.title}`}
                        className="hidden rounded p-1 hover:text-red-600 group-hover:block"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </>
  );
}
