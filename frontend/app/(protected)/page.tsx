"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { ChatInput } from "../../components/ChatInput";
import { useChatSessionsStore } from "../../lib/chat-store";
import {
  type ChatMessage,
  type Citation,
  getSession,
  streamChat,
} from "../../lib/chat";
import { listKnowledgeBases, type KnowledgeBase } from "../../lib/knowledge-bases";

export default function ChatPage() {
  const router = useRouter();
  const params = useSearchParams();

  const sessions = useChatSessionsStore((s) => s.sessions);
  const loaded = useChatSessionsStore((s) => s.loaded);
  const refresh = useChatSessionsStore((s) => s.refresh);
  const newChat = useChatSessionsStore((s) => s.newChat);
  const bumpUpdatedAt = useChatSessionsStore((s) => s.bumpUpdatedAt);

  const sidParam = params.get("sid");
  const activeId = sidParam ? Number(sidParam) : null;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);

  const [streamingText, setStreamingText] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<Citation[] | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Load KBs once for the input picker; sessions list is owned by the
  // sidebar's Zustand store.
  useEffect(() => {
    listKnowledgeBases()
      .then(setKnowledgeBases)
      .catch(() => setKnowledgeBases([]));
  }, []);

  // If the URL has no ?sid and the sidebar has loaded sessions, default to
  // the most-recently-updated one to avoid an empty landing state.
  useEffect(() => {
    if (activeId !== null) return;
    if (!loaded) return;
    if (sessions.length === 0) return;
    router.replace(`/?sid=${sessions[0].id}`);
  }, [activeId, loaded, sessions, router]);

  // Load messages when active session changes.
  useEffect(() => {
    if (activeId == null) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const detail = await getSession(activeId);
        if (cancelled) return;
        setMessages(detail.messages);
      } catch {
        if (!cancelled) setMessages([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText, isStreaming]);

  const activeSessionTitle = activeId
    ? sessions.find((s) => s.id === activeId)?.title ?? "Chat"
    : "Chat";

  const handleSend = useCallback(
    async (text: string, useRag: boolean, kbIds: number[] | null) => {
      let sid = activeId;
      if (sid == null) {
        const s = await newChat();
        sid = s.id;
        router.replace(`/?sid=${sid}`);
      }
      const optimisticUser: ChatMessage = {
        id: -Date.now(),
        role: "user",
        content: text,
        citations: null,
        created_at: new Date().toISOString(),
      };
      setMessages((cur) => [...cur, optimisticUser]);
      setStreamingText("");
      setStreamingCitations(null);
      setStreamError(null);
      setIsStreaming(true);

      let collected = "";
      let collectedCitations: Citation[] = [];

      await streamChat(
        { session_id: sid, message: text, use_rag: useRag, kb_ids: kbIds },
        {
          onToken: (t) => {
            collected += t;
            setStreamingText(collected);
          },
          onCitations: (items) => {
            collectedCitations = items;
            setStreamingCitations(items);
          },
          onDone: () => {
            const finalAssistant: ChatMessage = {
              id: -Date.now() - 1,
              role: "assistant",
              content: collected,
              citations: collectedCitations.length ? collectedCitations : null,
              created_at: new Date().toISOString(),
            };
            setMessages((cur) => [...cur, finalAssistant]);
            setStreamingText("");
            setStreamingCitations(null);
            setIsStreaming(false);
            // Update the sidebar's order locally, then re-fetch to pick up
            // any auto-titling the server applied on first message.
            bumpUpdatedAt(sid!);
            refresh();
          },
          onError: (msg) => {
            setStreamError(msg);
            setIsStreaming(false);
          },
        },
      );
    },
    [activeId, newChat, refresh, router, bumpUpdatedAt],
  );

  return (
    <section className="flex h-full flex-col">
      <header className="flex h-14 items-center justify-between border-b border-border bg-white/80 px-4">
        <div className="text-sm font-medium">{activeSessionTitle}</div>
        <div className="text-xs text-muted-foreground">Model: Gemma 4 E4B</div>
      </header>

      <div className="flex-1 overflow-auto px-4 py-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {messages.length === 0 && !isStreaming ? (
            <div className="rounded-lg border border-dashed border-border bg-white p-10 text-center text-sm text-muted-foreground">
              Type a message below to start. Toggle "Use RAG" to ground the
              answer in your knowledge bases.
            </div>
          ) : null}
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
          {isStreaming ? (
            <MessageBubble
              message={{
                id: -1,
                role: "assistant",
                content: streamingText || "…",
                citations: streamingCitations,
                created_at: new Date().toISOString(),
              }}
              streaming
            />
          ) : null}
          {streamError ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              Stream error: {streamError}
            </div>
          ) : null}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <ChatInput
        knowledgeBases={knowledgeBases}
        disabled={isStreaming}
        onSend={handleSend}
      />
    </section>
  );
}

function MessageBubble({
  message,
  streaming = false,
}: {
  message: ChatMessage;
  streaming?: boolean;
}) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
          isUser
            ? "bg-foreground text-white"
            : "border border-border bg-white text-foreground"
        }`}
      >
        {message.content}
        {streaming ? <span className="ml-1 animate-pulse">▍</span> : null}
        {message.citations && message.citations.length > 0 ? (
          <div className="mt-2 border-t border-border/40 pt-2 text-xs text-muted-foreground">
            Sources:{" "}
            {message.citations.map((c, i) => (
              <span key={c.file_id}>
                {i > 0 ? ", " : ""}
                {c.filename}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
