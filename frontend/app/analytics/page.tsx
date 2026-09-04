"use client";

import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { ErrorNote, PageHead } from "@/components/ui";
import { fmtInt, useApi } from "@/lib/hooks";

const TIP = { background: "#111827", border: "1px solid #1f2937", borderRadius: 8 };
const AXIS = { fill: "#6b7280", fontSize: 11 };

export default function AnalyticsPage() {
  const ts = useApi<any>("/analytics/timeseries?days=30");
  const cmp = useApi<any>("/analytics/comparison");
  const perf = useApi<any>("/analytics/trending-performance?limit=10");

  const series = (ts.data?.series ?? []).map((r: any) => ({
    ...r,
    engagement: r.views ? Number((((r.likes + r.comments + r.shares) / r.views) * 100).toFixed(2)) : 0,
  }));

  return (
    <div>
      <PageHead title="📈 Analytics" desc="Network & per-account performance (30 days)" />

      {ts.error && <ErrorNote msg={ts.error} />}

      <div className="grid lg:grid-cols-2 gap-4">
        <ChartCard title="👥 Follower growth">
          <LineChart data={series}>
            <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={AXIS} tickFormatter={(v: string) => v.slice(5)} />
            <YAxis tick={AXIS} tickFormatter={(v: number) => fmtInt(v)} />
            <Tooltip contentStyle={TIP} />
            <Line type="monotone" dataKey="followers" stroke="#34d399" strokeWidth={2} dot={false} />
          </LineChart>
        </ChartCard>

        <ChartCard title="👁 Views per day">
          <BarChart data={series}>
            <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={AXIS} tickFormatter={(v: string) => v.slice(5)} />
            <YAxis tick={AXIS} tickFormatter={(v: number) => fmtInt(v)} />
            <Tooltip contentStyle={TIP} />
            <Bar dataKey="views" fill="#6366f1" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title="💪 Engagement growth (%)">
          <AreaChart data={series}>
            <defs>
              <linearGradient id="eg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.5} />
                <stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={AXIS} tickFormatter={(v: string) => v.slice(5)} />
            <YAxis tick={AXIS} />
            <Tooltip contentStyle={TIP} />
            <Area type="monotone" dataKey="engagement" stroke="#f59e0b" fill="url(#eg)" strokeWidth={2} />
          </AreaChart>
        </ChartCard>

        <ChartCard title="🎬 Posts published">
          <BarChart data={series}>
            <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={AXIS} tickFormatter={(v: string) => v.slice(5)} />
            <YAxis tick={AXIS} allowDecimals={false} />
            <Tooltip contentStyle={TIP} />
            <Bar dataKey="posts" fill="#34d399" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title="📊 Account comparison (30-day views)">
          <BarChart data={cmp.data?.items ?? []} layout="vertical">
            <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
            <XAxis type="number" tick={AXIS} tickFormatter={(v: number) => fmtInt(v)} />
            <YAxis type="category" dataKey="username" width={90} tick={AXIS} />
            <Tooltip contentStyle={TIP} />
            <Legend />
            <Bar dataKey="views_30d" name="Views" fill="#6366f1" radius={[0, 3, 3, 0]} />
            <Bar dataKey="posts_30d" name="Posts" fill="#34d399" radius={[0, 3, 3, 0]} />
          </BarChart>
        </ChartCard>

        <div className="panel p-4">
          <h3 className="text-sm text-gray-400 mb-3">🔥 Trending content performance</h3>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {(perf.data?.items ?? []).map((p: any) => (
              <div key={p.content_id} className="flex items-center gap-3 text-sm border-t border-line/60 py-2 first:border-0">
                <span className="font-semibold text-emerald-300 w-10">{p.trend_score?.toFixed(0)}</span>
                <span className="flex-1 truncate">{p.title}</span>
                <span className="text-xs text-gray-500">{p.published_count} posts</span>
              </div>
            ))}
            {!perf.data?.items?.length && <p className="text-sm text-gray-500">No data yet.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactElement }) {
  return (
    <div className="panel p-4">
      <h3 className="text-sm text-gray-400 mb-3">{title}</h3>
      <div className="h-60">
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
