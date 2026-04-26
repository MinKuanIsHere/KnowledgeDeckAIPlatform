"use client";

import { create } from "zustand";

import {
  type SlideProject,
  deleteSlideProject,
  listSlideProjects,
  updateSlideProject,
} from "./slides";

type SlideState = {
  projects: SlideProject[];
  loaded: boolean;
  refresh: () => Promise<void>;
  // No `create` action here — generation is owned by the slides page (it
  // calls the LLM-backed /generate endpoint and adds to the store).
  add: (p: SlideProject) => void;
  remove: (id: number) => Promise<void>;
  rename: (id: number, title: string) => Promise<void>;
};

export const useSlideStore = create<SlideState>((set, get) => ({
  projects: [],
  loaded: false,
  refresh: async () => {
    try {
      set({ projects: await listSlideProjects(), loaded: true });
    } catch {
      set({ loaded: true });
    }
  },
  add: (p) => set({ projects: [p, ...get().projects] }),
  remove: async (id) => {
    await deleteSlideProject(id);
    set({ projects: get().projects.filter((p) => p.id !== id) });
  },
  rename: async (id, title) => {
    const updated = await updateSlideProject(id, title);
    set({
      projects: get().projects.map((p) =>
        p.id === id ? { ...p, title: updated.title } : p,
      ),
    });
  },
}));
