"use client";

import { isAxiosError } from "axios";
import {
  Bot,
  Check,
  Copy,
  Download,
  Loader2,
  Pencil,
  Sparkles,
  Trash2,
  User,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ChatInput } from "../../../../components/ChatInput";
import { useKbStore } from "../../../../lib/kb-store";
import { useSlideStore } from "../../../../lib/slide-store";
import {
  type SlideMessage,
  type SlideMessageCitation,
  downloadSlideSession,
  getSlideSession,
  hasOutlineReady,
  renderSlideSession,
  streamSlideSession,
  stripOutlineReady,
} from "../../../../lib/slides";

function detailMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return err instanceof Error ? err.message : "Failed";
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  const time = d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
  if (sameDay) return time;
  const date = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return `${date}, ${time}`;
}

export default function SlideSessionPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const sessionId = Number(params.id);

  const sessions = useSlideStore((s) => s.sessions);
  const slidesLoaded = useSlideStore((s) => s.loaded);
  const refreshSlides = useSlideStore((s) => s.refresh);
  const removeSession = useSlideStore((s) => s.remove);
  const renameSession = useSlideStore((s) => s.rename);
  const patchSession = useSlideStore((s) => s.patch);
  const bumpUpdatedAt = useSlideStore((s) => s.bumpUpdatedAt);

  const knowledgeBases = useKbStore((s) => s.kbs);
  const kbsLoaded = useKbStore((s) => s.loaded);
  const refreshKbs = useKbStore((s) => s.refresh);

  const session = sessions.find((s) => s.id === sessionId);

  const [messages, setMessages] = useState<SlideMessage[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<
    SlideMessageCitation[] | null
  >(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [rendering, setRendering] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);

  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);
  const [savingTitle, setSavingTitle] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Hydrate ambient state.
  useEffect(() => {
    if (!slidesLoaded) refreshSlides();
  }, [slidesLoaded, refreshSlides]);
  useEffect(() => {
    if (!kbsLoaded) refreshKbs();
  }, [kbsLoaded, refreshKbs]);

  // Load this session's messages whenever the route id changes.
  useEffect(() => {
    if (!Number.isFinite(sessionId)) return;
    let cancelled = false;
    (async () => {
      try {
        const detail = await getSlideSession(sessionId);
        if (cancelled) return;
        setMessages(detail.messages);
      } catch {
        if (!cancelled) setMessages([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // Auto-scroll on new content.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText, isStreaming]);

  const handleSend = useCallback(
    async (text: string, useRag: boolean, kbIds: number[] | null) => {
      const optimistic: SlideMessage = {
        id: -Date.now(),
        role: "user",
        content: text,
        citations: null,
        created_at: new Date().toISOString(),
      };
      setMessages((cur) => [...cur, optimistic]);
      setStreamingText("");
      setStreamingCitations(null);
      setStreamError(null);
      setIsStreaming(true);

      let collected = "";
      let collectedCitations: SlideMessageCitation[] = [];
      let outlineReady = false;

      await streamSlideSession(
        sessionId,
        { message: text, use_rag: useRag, kb_ids: kbIds },
        {
          onToken: (t) => {
            collected += t;
            setStreamingText(collected);
          },
          onCitations: (items) => {
            collectedCitations = items;
            setStreamingCitations(items);
          },
          onDone: (ready) => {
            outlineReady = ready;
            const finalAssistant: SlideMessage = {
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
            bumpUpdatedAt(sessionId);
            refreshSlides();
            // outlineReady is reflected by the message body containing
            // [OUTLINE_READY]; the dedicated state isn't otherwise needed.
            void outlineReady;
          },
          onError: (msg) => {
            setStreamError(msg);
            setIsStreaming(false);
          },
        },
      );
    },
    [sessionId, bumpUpdatedAt, refreshSlides],
  );

  // Find the most recent assistant message that emitted [OUTLINE_READY] —
  // used to decide whether the Render button is enabled.
  const latestReadyOutline = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "assistant" && hasOutlineReady(m.content)) return m;
    }
    return null;
  })();

  async function handleRender() {
    if (!latestReadyOutline) return;
    setRendering(true);
    setRenderError(null);
    try {
      const updated = await renderSlideSession(sessionId);
      patchSession(sessionId, {
        status: updated.status,
        has_pptx: updated.has_pptx,
      });
    } catch (err) {
      setRenderError(detailMessage(err));
    } finally {
      setRendering(false);
    }
  }

  async function handleDownload() {
    if (!session) return;
    try {
      await downloadSlideSession(sessionId, session.title);
    } catch (err) {
      setRenderError(detailMessage(err));
    }
  }

  async function handleDelete() {
    if (!session) return;
    if (!window.confirm(`Delete "${session.title}"?`)) return;
    await removeSession(sessionId);
    router.push("/slides");
  }

  async function handleRename(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!session) return;
    const trimmed = draftTitle.trim();
    if (!trimmed) return;
    setSavingTitle(true);
    setRenameError(null);
    try {
      await renameSession(sessionId, trimmed);
      setEditing(false);
    } catch (err) {
      setRenameError(detailMessage(err));
    } finally {
      setSavingTitle(false);
    }
  }

  if (slidesLoaded && !session) {
    return (
      <section className="h-full overflow-auto px-6 py-6">
        <div className="mx-auto max-w-3xl">
          <div className="rounded-lg border border-dashed border-border bg-white p-10 text-center text-sm text-muted-foreground">
            Slide deck not found.
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="flex h-full flex-col">
      <header className="flex h-14 items-center justify-between border-b border-border bg-white/80 px-4">
        <div className="min-w-0 flex-1">
          {editing ? (
            <form onSubmit={handleRename} className="flex items-center gap-2">
              <input
                value={draftTitle}
                onChange={(e) => setDraftTitle(e.target.value)}
                maxLength={200}
                autoFocus
                className="flex-1 rounded-md border border-border bg-white px-2 py-1 text-sm"
              />
              <button
                type="submit"
                disabled={savingTitle || !draftTitle.trim()}
                className="rounded-md bg-foreground px-2 py-1 text-xs text-white disabled:opacity-50"
              >
                Save
              </button>
              <button
                type="button"
                onClick={() => setEditing(false)}
                className="rounded-md border border-border px-2 py-1 text-xs hover:bg-muted"
              >
                Cancel
              </button>
            </form>
          ) : (
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium">
                {session?.title ?? "Loading…"}
              </span>
              <StatusBadge
                status={session?.status ?? "outlining"}
                hasPptx={session?.has_pptx ?? false}
              />
            </div>
          )}
          {renameError ? (
            <div className="mt-1 text-xs text-red-600">{renameError}</div>
          ) : null}
        </div>
        {session && !editing ? (
          <div className="ml-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setDraftTitle(session.title);
                setRenameError(null);
                setEditing(true);
              }}
              aria-label="Rename"
              className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
            {session.has_pptx ? (
              <button
                type="button"
                onClick={handleDownload}
                className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted"
              >
                <Download className="h-3.5 w-3.5" /> Download
              </button>
            ) : null}
            <button
              type="button"
              onClick={handleDelete}
              aria-label="Delete"
              className="rounded-md border border-border px-2 py-1 text-xs text-red-600 hover:bg-red-50"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : null}
      </header>

      <div className="flex-1 overflow-auto px-4 py-6">
        <div className="mx-auto max-w-5xl space-y-4">
          {messages.length === 0 && !isStreaming ? (
            <div className="rounded-lg border border-dashed border-border bg-white p-10 text-center text-sm text-muted-foreground">
              Tell the planner what you want to make. It will ask follow-ups
              and propose an outline. When you confirm, render the PPTX.
            </div>
          ) : null}
          {messages.map((m) => (
            <SlideBubble key={m.id} message={m} />
          ))}
          {isStreaming ? (
            <SlideBubble
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

      {/* Render bar appears whenever an outline is marked ready. */}
      {latestReadyOutline && !isStreaming ? (
        <div className="border-t border-border bg-amber-50 px-4 py-3">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-3">
            <div className="text-xs text-amber-900">
              <Sparkles className="mr-1 inline h-3.5 w-3.5" />
              The outline is ready. Click Render to produce the PPTX via
              Presenton (about 20–60s).
            </div>
            <div className="flex items-center gap-2">
              {renderError ? (
                <span className="text-xs text-red-700">{renderError}</span>
              ) : null}
              <button
                type="button"
                onClick={handleRender}
                disabled={rendering}
                className="flex items-center gap-1 rounded-md bg-amber-600 px-3 py-1.5 text-xs text-white hover:bg-amber-700 disabled:opacity-50"
              >
                {rendering ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> Rendering…
                  </>
                ) : (
                  <>
                    <Sparkles className="h-3.5 w-3.5" /> Render slides
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <ChatInput
        knowledgeBases={knowledgeBases}
        disabled={isStreaming || rendering}
        onSend={handleSend}
      />
    </section>
  );
}

function StatusBadge({
  status,
  hasPptx,
}: {
  status: string;
  hasPptx: boolean;
}) {
  const { label, tone } = (() => {
    if (status === "rendered" && hasPptx)
      return { label: "Rendered", tone: "bg-emerald-100 text-emerald-700" };
    if (status === "rendering")
      return { label: "Rendering…", tone: "bg-amber-100 text-amber-800" };
    if (status === "failed")
      return { label: "Failed", tone: "bg-red-100 text-red-700" };
    return { label: "Outlining", tone: "bg-muted text-muted-foreground" };
  })();
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] ${tone}`}>{label}</span>
  );
}

function SlideBubble({
  message,
  streaming = false,
}: {
  message: SlideMessage;
  streaming?: boolean;
}) {
  const isUser = message.role === "user";
  const ts = formatTimestamp(message.created_at);
  const display = isUser ? message.content : stripOutlineReady(message.content);
  return (
    <div
      className={`flex items-start gap-2 ${
        isUser ? "flex-row-reverse" : "flex-row"
      }`}
    >
      <Avatar isUser={isUser} />
      <div
        className={`flex max-w-[85%] flex-col gap-1 md:max-w-[75%] lg:max-w-[65%] ${
          isUser ? "items-end" : "items-start"
        }`}
      >
        <div
          className={`rounded-lg px-3 py-2 text-sm ${
            isUser
              ? "whitespace-pre-wrap bg-foreground text-white"
              : "border border-border bg-white text-foreground"
          }`}
        >
          {isUser ? (
            <>
              {display}
              {streaming ? <span className="ml-1 animate-pulse">▍</span> : null}
            </>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {display || (streaming ? "…" : "")}
              </ReactMarkdown>
              {streaming ? <span className="ml-1 animate-pulse">▍</span> : null}
            </div>
          )}
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
        <div className="flex items-center gap-2 px-1 text-[10px] text-muted-foreground">
          <span>{ts}</span>
          {!isUser && !streaming && message.content ? (
            <CopyButton text={display} />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Avatar({ isUser }: { isUser: boolean }) {
  return isUser ? (
    <div
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-foreground text-white"
      aria-label="User"
    >
      <User className="h-4 w-4" />
    </div>
  ) : (
    <div
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-white text-foreground"
      aria-label="Assistant"
    >
      <Bot className="h-4 w-4" />
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      } finally {
        document.body.removeChild(ta);
      }
    }
  }
  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label="Copy markdown"
      className="flex items-center gap-1 rounded px-1 py-0.5 hover:bg-muted hover:text-foreground"
    >
      {copied ? (
        <>
          <Check className="h-3 w-3" /> Copied
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" /> Copy
        </>
      )}
    </button>
  );
}
