"use client";

import { useState } from "react";
import { ErrorNote, PageHead, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, useApi } from "@/lib/hooks";

const TYPES = ["daily", "weekly", "monthly", "network", "account"];

export default function ReportsPage() {
  const { data, error, reload } = useApi<any>("/reports");
  const [open, setOpen] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  async function generate(type: string) {
    setBusy(true);
    try {
      const rep = await api.post("/reports/generate", { type, send: false });
      setOpen(rep);
      reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHead
        title="📄 Reports"
        desc="Automatic daily / weekly / monthly reports — also sent to Telegram at 21:05 UTC"
        actions={
          TYPES.map((t) => (
            <button key={t} className="btn-ghost" disabled={busy} onClick={() => generate(t)}>
              {busy ? "…" : `+ ${t}`}
            </button>
          ))
        }
      />
      {error && <ErrorNote msg={error} />}

      {open && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
          onClick={() => setOpen(null)}>
          <div className="panel max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-white">{open.title}</h3>
              <button className="btn-ghost" onClick={() => setOpen(null)}>✖</button>
            </div>
            <pre className="text-sm text-gray-300 whitespace-pre-wrap bg-panel2 rounded-lg p-4 border border-line">
              {open.text_content}
            </pre>
          </div>
        </div>
      )}

      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[640px]">
          <thead>
            <tr>
              <th className="th">Report</th>
              <th className="th">Type</th>
              <th className="th">Period</th>
              <th className="th">Status</th>
              <th className="th text-right">View</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items ?? []).map((r: any) => (
              <tr key={r.id}>
                <td className="td text-white">{r.title}</td>
                <td className="td"><span className="badge">{r.report_type}</span></td>
                <td className="td text-xs">{fmtDate(r.period_start)} → {fmtDate(r.period_end)}</td>
                <td className="td"><StatusBadge status={r.status} /></td>
                <td className="td text-right">
                  <button className="btn-ghost" onClick={async () => setOpen(await api.get(`/reports/${r.id}`))}>
                    👁
                  </button>
                </td>
              </tr>
            ))}
            {!data?.items?.length && (
              <tr><td className="td text-center text-gray-500" colSpan={5}>No reports yet — generate one above.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
