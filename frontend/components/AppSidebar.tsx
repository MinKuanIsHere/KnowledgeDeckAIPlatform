"use client";

import { LogOut, MessageSquare, MessageSquarePlus, Plus, Presentation, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { useAuthStore } from "../lib/auth-store";
import { useChatSessionsStore } from "../lib/chat-store";

/**
 * Single sidebar shared across all (protected) pages. Lives in the layout so
 * navigating between Chat and Knowledge Bases never re-mounts it — the
 * sessions list keeps its scroll/state, and the URL tells us which session
 * is active (?sid=N) when the user is on the chat page.
 */
export function AppSidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const user = useAuthStore((s) => s.user);
  const clearSession = useAuthStore((s) => s.clearSession);

  const sessions = useChatSessionsStore((s) => s.sessions);
  const loaded = useChatSessionsStore((s) => s.loaded);
  const refresh = useChatSessionsStore((s) => s.refresh);
  const newChat = useChatSessionsStore((s) => s.newChat);
  const remove = useChatSessionsStore((s) => s.remove);

  const activeSidParam = params.get("sid");
  const activeSid = activeSidParam ? Number(activeSidParam) : null;
  const onChatPage = pathname === "/";
  const onKbPage = pathname?.startsWith("/knowledge-bases") ?? false;
  const onSlidesPage = pathname?.startsWith("/slides") ?? false;

  useEffect(() => {
    if (!loaded) refresh();
  }, [loaded, refresh]);

  function handleLogout() {
    clearSession();
    router.push("/login");
  }

  async function handleNewChat() {
    const s = await newChat();
    router.push(`/?sid=${s.id}`);
  }

  function handleSelect(sid: number) {
    router.push(`/?sid=${sid}`);
  }

  async function handleDelete(sid: number, ev: React.MouseEvent) {
    ev.stopPropagation();
    await remove(sid);
    if (sid === activeSid) router.push("/");
  }

  return (
    <aside className="hidden w-64 flex-col border-r border-border bg-white/80 md:flex">
      <div className="border-b border-border px-4 py-4 text-lg font-semibold">
        KnowledgeDeck
      </div>
      <nav className="space-y-1 px-2 py-3 text-sm">
        <Link
          href="/"
          className={`flex items-center gap-2 rounded-md px-3 py-2 ${
            onChatPage
              ? "bg-muted text-foreground"
              : "text-muted-foreground hover:bg-muted hover:text-foreground"
          }`}
        >
          <MessageSquare className="h-4 w-4" />
          Chat
        </Link>
        <Link
          href="/knowledge-bases"
          className={`flex items-center gap-2 rounded-md px-3 py-2 ${
            onKbPage
              ? "bg-muted text-foreground"
              : "text-muted-foreground hover:bg-muted hover:text-foreground"
          }`}
        >
          <Search className="h-4 w-4" />
          Knowledge Bases
        </Link>
        <Link
          href="/slides"
          className={`flex items-center gap-2 rounded-md px-3 py-2 ${
            onSlidesPage
              ? "bg-muted text-foreground"
              : "text-muted-foreground hover:bg-muted hover:text-foreground"
          }`}
        >
          <Presentation className="h-4 w-4" />
          Slide Maker
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
            {sessions.map((s) => {
              const isActive = onChatPage && s.id === activeSid;
              return (
                <li
                  key={s.id}
                  className={`group flex items-center justify-between rounded-md px-2 py-1.5 text-sm ${
                    isActive
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => handleSelect(s.id)}
                    className="flex-1 truncate text-left"
                    title={s.title}
                  >
                    {s.title}
                  </button>
                  <button
                    type="button"
                    onClick={(ev) => handleDelete(s.id, ev)}
                    aria-label={`Delete ${s.title}`}
                    className="ml-1 hidden rounded p-1 hover:text-red-600 group-hover:block"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              );
            })}
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
  );
}
