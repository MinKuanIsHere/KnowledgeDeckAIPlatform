import { FileText, MessageSquare, Presentation, Search } from "lucide-react";

const navItems = [
  { label: "Chat", icon: MessageSquare },
  { label: "Knowledge", icon: Search },
  { label: "Documents", icon: FileText },
  { label: "Slides", icon: Presentation }
];

export default function Home() {
  return (
    <main className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-64 border-r border-border bg-white/80 px-4 py-5 md:block">
        <div className="mb-6 text-lg font-semibold">KnowledgeDeck</div>
        <nav className="space-y-1">
          {navItems.map((item) => (
            <button
              className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              key={item.label}
              type="button"
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <section className="flex flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-border bg-white/80 px-4">
          <div className="text-sm font-medium">Chat</div>
          <div className="text-xs text-muted-foreground">Model: Gemma 4 E4B</div>
        </header>
        <div className="flex flex-1 items-center justify-center px-4">
          <div className="w-full max-w-3xl">
            <h1 className="mb-3 text-2xl font-semibold">Ask KnowledgeDeck</h1>
            <div className="rounded-lg border border-border bg-white p-3 shadow-sm">
              <textarea
                className="min-h-28 w-full resize-none bg-transparent text-sm outline-none"
                placeholder="Ask a question or describe the presentation you want to create..."
              />
              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs text-muted-foreground">RAG ready scaffold</span>
                <button className="rounded-md bg-foreground px-3 py-2 text-sm text-white" type="button">
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
