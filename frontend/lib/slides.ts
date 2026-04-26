"use client";

import { api } from "./api";
import { useAuthStore } from "./auth-store";

export type SlideProject = {
  id: number;
  title: string;
  prompt: string;
  use_rag: boolean;
  kb_ids: number[] | null;
  created_at: string;
};

export type SlideProjectDetail = SlideProject & { outline: string };

export type GenerateRequest = {
  prompt: string;
  title?: string;
  use_rag: boolean;
  kb_ids: number[] | null;
};

export async function generateSlides(req: GenerateRequest): Promise<SlideProject> {
  const res = await api.post<SlideProject>("/slides/generate", {
    prompt: req.prompt,
    title: req.title ?? null,
    use_rag: req.use_rag,
    kb_ids: req.kb_ids,
  });
  return res.data;
}

export async function listSlideProjects(): Promise<SlideProject[]> {
  const res = await api.get<SlideProject[]>("/slides/projects");
  return res.data;
}

export async function getSlideProject(id: number): Promise<SlideProjectDetail> {
  const res = await api.get<SlideProjectDetail>(`/slides/projects/${id}`);
  return res.data;
}

export async function updateSlideProject(
  id: number,
  title: string,
): Promise<SlideProject> {
  const res = await api.patch<SlideProject>(`/slides/projects/${id}`, { title });
  return res.data;
}

export async function deleteSlideProject(id: number): Promise<void> {
  await api.delete(`/slides/projects/${id}`);
}

/**
 * Returns a URL string suitable for a "Download" anchor. Because the request
 * needs the Bearer header, browsers can't just hit the URL — instead the
 * caller fetches it and triggers a save via Blob URL.
 */
export async function downloadSlideProject(
  id: number,
  fallbackFilename: string,
): Promise<void> {
  const token = useAuthStore.getState().token;
  const baseURL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";
  const res = await fetch(`${baseURL}/slides/projects/${id}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  // Pull filename out of Content-Disposition when present, else use fallback.
  const disp = res.headers.get("Content-Disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(disp);
  const filename = match?.[1] ?? `${fallbackFilename}.txt`;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
