"use client";

import { create } from "zustand";

import {
  type ChatSession,
  createSession,
  deleteSession,
  listSessions,
} from "./chat";

type ChatSessionsState = {
  sessions: ChatSession[];
  loaded: boolean;
  refresh: () => Promise<void>;
  newChat: () => Promise<ChatSession>;
  remove: (id: number) => Promise<void>;
  // Local-only update (e.g., after sending a message we already know the
  // server side has touched updated_at). Keeps the sidebar in sync without
  // an extra round-trip.
  bumpUpdatedAt: (id: number) => void;
};

export const useChatSessionsStore = create<ChatSessionsState>((set, get) => ({
  sessions: [],
  loaded: false,
  refresh: async () => {
    try {
      set({ sessions: await listSessions(), loaded: true });
    } catch {
      set({ loaded: true });
    }
  },
  newChat: async () => {
    const s = await createSession();
    set({ sessions: [s, ...get().sessions] });
    return s;
  },
  remove: async (id) => {
    await deleteSession(id);
    set({ sessions: get().sessions.filter((s) => s.id !== id) });
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
