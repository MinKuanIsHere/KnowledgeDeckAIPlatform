"use client";

export default function KnowledgeBasesIndexPage() {
  return (
    <section className="h-full overflow-auto px-6 py-6">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-xl font-semibold">Knowledge Bases</h1>
        <div className="mt-4 rounded-lg border border-dashed border-border bg-white p-10 text-center text-sm text-muted-foreground">
          Pick a knowledge base from the sidebar, or click + to create one.
        </div>
      </div>
    </section>
  );
}
