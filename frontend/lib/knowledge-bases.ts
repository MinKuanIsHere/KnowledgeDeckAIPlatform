"use client";

import { api } from "./api";

export type FileStatus =
  | "uploaded"
  | "parsing"
  | "parsed"
  | "embedding"
  | "indexed"
  | "failed";

export type KnowledgeBase = {
  id: number;
  name: string;
  description: string | null;
  file_count: number;
  created_at: string;
};

export type KnowledgeBaseCreated = {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
};

export type KnowledgeFile = {
  id: number;
  knowledge_base_id: number;
  filename: string;
  extension: string;
  size_bytes: number;
  status: FileStatus;
  status_error: string | null;
  created_at: string;
};

export async function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  const res = await api.get<KnowledgeBase[]>("/knowledge-bases");
  return res.data;
}

export async function createKnowledgeBase(input: {
  name: string;
  description?: string | null;
}): Promise<KnowledgeBaseCreated> {
  const res = await api.post<KnowledgeBaseCreated>("/knowledge-bases", {
    name: input.name,
    description: input.description ?? null,
  });
  return res.data;
}

export async function deleteKnowledgeBase(id: number): Promise<void> {
  await api.delete(`/knowledge-bases/${id}`);
}

export async function listFiles(kbId: number): Promise<KnowledgeFile[]> {
  const res = await api.get<KnowledgeFile[]>(`/knowledge-bases/${kbId}/files`);
  return res.data;
}

export async function uploadFile(
  kbId: number,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<KnowledgeFile> {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post<KnowledgeFile>(
    `/knowledge-bases/${kbId}/files`,
    form,
    {
      onUploadProgress: (e) => {
        if (!onProgress || !e.total) return;
        onProgress(Math.min(100, Math.round((e.loaded / e.total) * 100)));
      },
    },
  );
  return res.data;
}

export async function deleteFile(kbId: number, fileId: number): Promise<void> {
  await api.delete(`/knowledge-bases/${kbId}/files/${fileId}`);
}
