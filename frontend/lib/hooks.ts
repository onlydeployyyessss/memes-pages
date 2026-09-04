"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

export function useApi<T = any>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      setData(await api.get(path));
    } catch (e: any) {
      setError(e.message || "request failed");
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}

export function fmtInt(n: number | null | undefined): string {
  const v = Number(n ?? 0);
  if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (Math.abs(v) >= 1_000) return (v / 1_000).toFixed(1) + "K";
  return String(v);
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export const STATUS_EMOJI: Record<string, string> = {
  detected: "🟡", processing: "🔵", queued: "🟣", scheduled: "🟠",
  published: "🟢", failed: "🔴", skipped: "⚪", cancelled: "⚫",
  active: "🟢", paused: "⏸", error: "🔴", disabled: "⚫",
  authorized: "🟢", not_authorized: "🔴", connected: "🟢",
  not_connected: "⚪", token_error: "🔴", sent: "🟢", generated: "•",
  completed: "🟢", planned: "•", running: "🔵", resting: "😴",
};

export function st(status: string | null | undefined): string {
  return STATUS_EMOJI[status ?? ""] ?? "•";
}
