"use client";

export function Kpi({ icon, label, value, sub, tone }: {
  icon: string; label: string; value: string | number; sub?: string; tone?: string;
}) {
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide text-gray-500">{label}</span>
        <span className="text-lg">{icon}</span>
      </div>
      <div className={`mt-2 text-2xl font-semibold ${tone ?? "text-white"}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-gray-500">{sub}</div>}
    </div>
  );
}

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const map: Record<string, string> = {
    published: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
    failed: "text-red-300 bg-red-500/10 border-red-500/30",
    queued: "text-purple-300 bg-purple-500/10 border-purple-500/30",
    scheduled: "text-orange-300 bg-orange-500/10 border-orange-500/30",
    detected: "text-yellow-300 bg-yellow-500/10 border-yellow-500/30",
    processing: "text-sky-300 bg-sky-500/10 border-sky-500/30",
    active: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
    authorized: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
    error: "text-red-300 bg-red-500/10 border-red-500/30",
  };
  const cls = map[status ?? ""] ?? "text-gray-300 bg-panel2 border-line";
  return <span className={`badge ${cls}`}>{status}</span>;
}

export function ScoreBar({ score }: { score: number }) {
  const color = score >= 85 ? "bg-emerald-400" : score >= 60 ? "bg-amber-400" : "bg-gray-600";
  return (
    <div className="flex items-center gap-2 min-w-32">
      <div className="h-2 w-24 bg-line rounded-full overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${Math.min(100, score)}%` }} />
      </div>
      <span className="text-xs text-gray-400">{score.toFixed(0)}/100</span>
    </div>
  );
}

export function ErrorNote({ msg }: { msg: string }) {
  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 text-sm px-4 py-3">
      ⚠️ {msg}
    </div>
  );
}

export function PageHead({ title, desc, actions }: {
  title: string; desc?: string; actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
      <div>
        <h2 className="text-xl font-semibold text-white">{title}</h2>
        {desc && <p className="text-sm text-gray-500 mt-0.5">{desc}</p>}
      </div>
      <div className="flex items-center gap-2">{actions}</div>
    </div>
  );
}
