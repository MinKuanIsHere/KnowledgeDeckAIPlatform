"use client";

import { create } from "zustand";

import {
  type KnowledgeBase,
  createKnowledgeBase,
  deleteKnowledgeBase,
  listKnowledgeBases,
  updateKnowledgeBase,
} from "./knowledge-bases";

type KbState = {
  kbs: KnowledgeBase[];
  loaded: boolean;
  refresh: () => Promise<void>;
  create: (name: string, description?: string | null) => Promise<KnowledgeBase>;
  remove: (id: number) => Promise<void>;
  rename: (id: number, name: string) => Promise<void>;
  // Updated locally after a file upload / delete touches the count.
  bumpFileCount: (id: number, delta: number) => void;
  setFileCount: (id: number, count: number) => void;
};

export const useKbStore = create<KbState>((set, get) => ({
  kbs: [],
  loaded: false,
  refresh: async () => {
    try {
      set({ kbs: await listKnowledgeBases(), loaded: true });
    } catch {
      set({ loaded: true });
    }
  },
  create: async (name, description) => {
    const created = await createKnowledgeBase({ name, description });
    // Backend returns no file_count on create, so seed it as 0.
    const row: KnowledgeBase = {
      id: created.id,
      name: created.name,
      description: created.description,
      file_count: 0,
      created_at: created.created_at,
    };
    set({ kbs: [row, ...get().kbs] });
    return row;
  },
  remove: async (id) => {
    await deleteKnowledgeBase(id);
    set({ kbs: get().kbs.filter((k) => k.id !== id) });
  },
  rename: async (id, name) => {
    const updated = await updateKnowledgeBase(id, { name });
    set({
      kbs: get().kbs.map((k) =>
        k.id === id ? { ...k, name: updated.name, description: updated.description } : k,
      ),
    });
  },
  bumpFileCount: (id, delta) => {
    set({
      kbs: get().kbs.map((k) =>
        k.id === id ? { ...k, file_count: Math.max(0, k.file_count + delta) } : k,
      ),
    });
  },
  setFileCount: (id, count) => {
    set({
      kbs: get().kbs.map((k) => (k.id === id ? { ...k, file_count: count } : k)),
    });
  },
}));
