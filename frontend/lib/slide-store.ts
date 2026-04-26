"use client";

import { create } from "zustand";

import {
  type SlideSession,
  createSlideSession,
  deleteSlideSession,
  listSlideSessions,
  updateSlideSession,
} from "./slides";

type SlideState = {
  sessions: SlideSession[];
  loaded: boolean;
  refresh: () => Promise<void>;
  newSession: () => Promise<SlideSession>;
  remove: (id: number) => Promise<void>;
  rename: (id: number, title: string) => Promise<void>;
  /** Local-only patch (e.g., after a render call updates status/has_pptx). */
  patch: (id: number, patch: Partial<SlideSession>) => void;
  bumpUpdatedAt: (id: number) => void;
};

export const useSlideStore = create<SlideState>((set, get) => ({
  sessions: [],
  loaded: false,
  refresh: async () => {
    try {
      set({ sessions: await listSlideSessions(), loaded: true });
    } catch {
      set({ loaded: true });
    }
  },
  newSession: async () => {
    const s = await createSlideSession();
    set({ sessions: [s, ...get().sessions] });
    return s;
  },
  remove: async (id) => {
    await deleteSlideSession(id);
    set({ sessions: get().sessions.filter((s) => s.id !== id) });
  },
  rename: async (id, title) => {
    const updated = await updateSlideSession(id, title);
    set({
      sessions: get().sessions.map((s) =>
        s.id === id ? { ...s, title: updated.title } : s,
      ),
    });
  },
  patch: (id, patch) => {
    set({
      sessions: get().sessions.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    });
  },
  bumpUpdatedAt: (id) => {
    const now = new Date().toISOString();
    const list = [...get().sessions];
    const idx = list.findIndex((s) => s.id === id);
    if (idx < 0) return;
    const [target] = list.splice(idx, 1);
    list.unshift({ ...target, updated_at: now });
    set({ sessions: list });
  },
}));
