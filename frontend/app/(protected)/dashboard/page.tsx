"use client";

export default function DashboardPage() {
  return (
    <section className="h-full overflow-auto px-6 py-6">
      <div className="mx-auto max-w-3xl space-y-4">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <div className="rounded-lg border border-dashed border-border bg-white p-10 text-center text-sm text-muted-foreground">
          Dashboard content (KB / Chat / Slide Maker stats and module
          summaries) is on the roadmap. Use the sidebar to jump into a
          module.
        </div>
      </div>
    </section>
  );
}
