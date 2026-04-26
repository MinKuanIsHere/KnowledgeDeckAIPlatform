"use client";

import { LogOut, MessageSquarePlus, Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { ChatInput } from "../../components/ChatInput";
import { useAuthStore } from "../../lib/auth-store";
import {
  type ChatMessage,
  type ChatSession,
  type Citation,
  createSession,
  deleteSession,
  getSession,
  listSessions,
  streamChat,
} from "../../lib/chat";
import { listKnowledgeBases, type KnowledgeBase } from "../../lib/knowledge-bases";

export default function ChatPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const clearSession = useAuthStore((s) => s.clearSession);

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);

  // Streaming state — held in a ref alongside React state so the SSE callbacks
  // (which capture closures) can append without re-rendering on every token.
  const [streamingText, setStreamingText] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<Citation[] | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await listSessions());
    } catch {
      /* ignore — sidebar list is non-critical */
    }
  }, []);

  // Initial load: sessions list, KB list. Pick the first session if any.
  useEffect(() => {
    (async () => {
      const [sList, kList] = await Promise.all([
        listSessions(),
        listKnowledgeBases().catch(() => []),
      ]);
      setSessions(sList);
      setKnowledgeBases(kList);
      if (sList.length > 0) setActiveId(sList[0].id);
    })();
  }, []);

  // Load detail when active session changes.
  useEffect(() => {
    if (activeId == null) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    (async () => {
      const detail = await getSession(activeId);
      if (cancelled) return;
      setMessages(detail.messages);
    })();
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  // Auto-scroll to bottom on new messages or streaming tokens.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText, isStreaming]);

  function handleLogout() {
    clearSession();
    router.push("/login");
  }

  async function handleNewChat() {
    const s = await createSession();
    setSessions((cur) => [s, ...cur]);
    setActiveId(s.id);
    setMessages([]);
  }

  async function handleDeleteSession(id: number) {
    await deleteSession(id);
    setSessions((cur) => cur.filter((s) => s.id !== id));
    if (id === activeId) {
      setActiveId(null);
      setMessages([]);
    }
  }

  async function handleSend(text: string, useRag: boolean, kbIds: number[] | null) {
    let sid = activeId;
    if (sid == null) {
      const s = await createSession();
      setSessions((cur) => [s, ...cur]);
      sid = s.id;
      setActiveId(sid);
    }
    // Optimistic user message; real id arrives when we refetch the session.
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
          // Fold the streamed turn into the message list as a real assistant
          // message, then refetch sessions so the sidebar order/title update.
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
          refreshSessions();
        },
        onError: (msg) => {
          setStreamError(msg);
          setIsStreaming(false);
        },
      },
    );
  }

  return (
    <main className="flex h-screen bg-background text-foreground">
      <aside className="hidden w-64 flex-col border-r border-border bg-white/80 md:flex">
        <div className="border-b border-border px-4 py-4 text-lg font-semibold">
          KnowledgeDeck
        </div>
        <nav className="px-2 py-3 text-sm">
          <Link
            href="/knowledge-bases"
            className="flex items-center gap-2 rounded-md px-3 py-2 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <Search className="h-4 w-4" />
            Knowledge Bases
          </Link>
        </nav>
        <div className="flex items-center justify-between border-t border-border px-3 pt-3 text-xs text-muted-foreground">
          <span>Chats</span>
          <button
            type="button"
            onClick={handleNewChat}
            aria-label="New chat"
            className="rounded p-1 hover:bg-muted hover:text-foreground"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-auto px-2 py-2">
          {sessions.length === 0 ? (
            <button
              type="button"
              onClick={handleNewChat}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <MessageSquarePlus className="h-4 w-4" />
              Start a new chat
            </button>
          ) : (
            <ul className="space-y-1">
              {sessions.map((s) => (
                <li
                  key={s.id}
                  className={`group flex items-center justify-between rounded-md px-2 py-1.5 text-sm ${
                    s.id === activeId
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setActiveId(s.id)}
                    className="flex-1 truncate text-left"
                    title={s.title}
                  >
                    {s.title}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteSession(s.id)}
                    aria-label={`Delete ${s.title}`}
                    className="ml-1 hidden rounded p-1 hover:text-red-600 group-hover:block"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="border-t border-border px-3 py-3 text-xs text-muted-foreground">
          <div className="mb-2 truncate" title={user?.username}>
            {user?.username ?? ""}
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 rounded-md px-2 py-1 hover:bg-muted hover:text-foreground"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </aside>

      <section className="flex flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-border bg-white/80 px-4">
          <div className="text-sm font-medium">
            {activeId == null
              ? "Chat"
              : sessions.find((s) => s.id === activeId)?.title ?? "Chat"}
          </div>
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
    </main>
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
