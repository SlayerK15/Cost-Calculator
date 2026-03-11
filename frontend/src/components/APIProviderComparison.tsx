"use client";

import { useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import type { APIProviderComparison } from "@/types";

// Hex colors for chart bars
const PROVIDER_HEX: Record<string, string> = {
  OpenAI: "#22c55e",
  Anthropic: "#f97316",
  Google: "#3b82f6",
  Mistral: "#a855f7",
  DeepSeek: "#94a3b8",
  "Self-Hosted": "#5c7cfa",
};

const CHAT_SUBSCRIPTIONS = [
  { provider: "OpenAI", plan: "ChatGPT Plus", price: 20, limit: "~80 msgs/3hrs on GPT-4o" },
  { provider: "OpenAI", plan: "ChatGPT Pro", price: 200, limit: "Higher limits, o1-pro access" },
  { provider: "Anthropic", plan: "Claude Pro", price: 20, limit: "5× more usage than free" },
  { provider: "Anthropic", plan: "Claude Max", price: 100, limit: "20× more usage than free" },
  { provider: "Google", plan: "Gemini Advanced", price: 20, limit: "Rate-limited, 1M context" },
  { provider: "DeepSeek", plan: "DeepSeek Chat", price: 0, limit: "Free with rate limits" },
];

function formatCostPerReq(cost: number): string {
  if (cost < 0.0001) return `$${cost.toFixed(6)}`;
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(3)}`;
}

function formatDollars(v: number): string {
  if (v >= 1000) return `$${(v / 1000).toFixed(1)}k`;
  if (v >= 1) return `$${v.toFixed(0)}`;
  if (v >= 0.01) return `$${v.toFixed(2)}`;
  if (v >= 0.0001) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(6)}`;
}

function shortModel(provider: string, model: string): string {
  // Shorten for chart x-axis labels
  return model.replace(provider, "").trim();
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-xs shadow-xl">
      <p className="font-bold text-white">{d.fullName}</p>
      <p className="text-gray-400 mt-0.5">{d.type}</p>
      {d.monthly !== undefined && (
        <p className="mt-1 text-gray-300">
          Monthly: <span className="text-white font-medium">${d.monthly.toLocaleString()}</span>
        </p>
      )}
      {d.costPerReq !== undefined && (
        <p className="text-gray-300">
          Per request: <span className="text-white font-medium">{formatCostPerReq(d.costPerReq)}</span>
        </p>
      )}
      {d.breakeven && d.breakeven < Infinity && (
        <p className="text-gray-300">
          Breakeven: <span className="text-white font-medium">{d.breakeven.toLocaleString()} req/mo</span>
        </p>
      )}
    </div>
  );
}

type ViewMode = "monthly" | "perRequest";

export function APIProviderComparisonCard({
  data,
}: {
  data: APIProviderComparison;
}) {
  const [viewMode, setViewMode] = useState<ViewMode>("monthly");

  const selfHostedCostPerReq =
    data.monthly_requests > 0
      ? data.self_hosted_monthly / data.monthly_requests
      : 0;

  // Build chart data
  const chartData = useMemo(() => {
    const selfHosted = {
      name: `Self-Hosted`,
      shortName: data.self_hosted_provider.toUpperCase(),
      fullName: `Self-Hosted (${data.self_hosted_provider.toUpperCase()})`,
      provider: "Self-Hosted",
      type: "Dedicated GPU · No rate limits",
      monthly: data.self_hosted_monthly,
      costPerReq: selfHostedCostPerReq,
      color: PROVIDER_HEX["Self-Hosted"],
      isSelfHosted: true,
      breakeven: null as number | null,
    };

    const apiEntries = data.api_providers.map((p) => ({
      name: `${p.provider}`,
      shortName: shortModel(p.provider, p.model),
      fullName: `${p.provider} — ${p.model}`,
      provider: p.provider,
      type: "Pay-per-token API · Rate-limited",
      monthly: p.monthly_cost,
      costPerReq: p.cost_per_request,
      color: PROVIDER_HEX[p.provider] || "#64748b",
      isSelfHosted: false,
      breakeven: p.cost_per_request > 0
        ? Math.ceil(data.self_hosted_monthly / p.cost_per_request)
        : Infinity,
    }));

    // Sort by the active metric
    apiEntries.sort((a, b) =>
      viewMode === "monthly"
        ? a.monthly - b.monthly
        : a.costPerReq - b.costPerReq
    );

    return [selfHosted, ...apiEntries];
  }, [data, selfHostedCostPerReq, viewMode]);

  const moreExpensiveByReq = data.api_providers.filter(
    (p) => p.cost_per_request > selfHostedCostPerReq
  ).length;

  // Breakeven stats
  const sortedBreakevens = data.api_providers
    .map((p) => (p.cost_per_request > 0 ? Math.ceil(data.self_hosted_monthly / p.cost_per_request) : Infinity))
    .filter((b) => b < Infinity)
    .sort((a, b) => a - b);
  const medianBreakeven = sortedBreakevens.length > 0
    ? sortedBreakevens[Math.floor(sortedBreakevens.length / 2)]
    : 0;

  const totalInputTokens = (data.monthly_input_tokens / 1_000_000).toFixed(1);
  const totalOutputTokens = (data.monthly_output_tokens / 1_000_000).toFixed(1);

  const valueKey = viewMode === "monthly" ? "monthly" : "costPerReq";
  const selfHostedValue = viewMode === "monthly" ? data.self_hosted_monthly : selfHostedCostPerReq;

  return (
    <div className="card space-y-5">
      {/* Header */}
      <div>
        <h3 className="text-lg font-bold text-white">
          Self-Hosted vs API Providers
        </h3>
        <p className="mt-1 text-sm text-gray-400">
          Based on{" "}
          <span className="text-white font-medium">
            {data.monthly_requests.toLocaleString()}
          </span>{" "}
          requests/month ({data.avg_input_tokens_per_request} input +{" "}
          {data.avg_output_tokens_per_request} output tokens/req) ·{" "}
          {totalInputTokens}M input + {totalOutputTokens}M output tokens/month
        </p>
      </div>

      {/* Breakeven insight */}
      <div className="rounded-lg border border-brand-700 bg-brand-900/20 p-3">
        <p className="text-sm text-brand-300">
          <span className="font-bold">Breakeven:</span>{" "}
          Self-hosting beats most APIs at{" "}
          <span className="font-bold text-white">
            {medianBreakeven.toLocaleString()}
          </span>{" "}
          req/mo. You&apos;re at{" "}
          <span className="font-bold text-white">
            {data.monthly_requests.toLocaleString()}
          </span>
          {data.monthly_requests >= medianBreakeven ? (
            <span className="text-green-400 font-bold">
              {" "}— self-hosting wins at your volume.
            </span>
          ) : (
            <span className="text-yellow-400 font-bold">
              {" "}— scale up to break even.
            </span>
          )}
          {moreExpensiveByReq > 0 && (
            <span className="text-gray-400">
              {" "}Already cheaper than {moreExpensiveByReq} of {data.api_providers.length} providers per request.
            </span>
          )}
        </p>
      </div>

      {/* View toggle */}
      <div className="flex items-center gap-1 rounded-lg bg-gray-800 p-1 w-fit">
        <button
          onClick={() => setViewMode("monthly")}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
            viewMode === "monthly"
              ? "bg-brand-600 text-white shadow"
              : "text-gray-400 hover:text-gray-200"
          }`}
        >
          Monthly Cost
        </button>
        <button
          onClick={() => setViewMode("perRequest")}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
            viewMode === "perRequest"
              ? "bg-brand-600 text-white shadow"
              : "text-gray-400 hover:text-gray-200"
          }`}
        >
          Cost per Request
        </button>
      </div>

      {/* Bar chart */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-4">
        <p className="text-xs text-gray-500 mb-3 font-medium">
          {viewMode === "monthly"
            ? "Estimated Monthly Cost ($)"
            : "Cost per Request ($)"}
          {viewMode === "perRequest" && (
            <span className="font-normal text-gray-600 ml-2">
              Self-hosted cost drops as you scale — API stays flat
            </span>
          )}
        </p>
        <ResponsiveContainer width="100%" height={Math.max(320, chartData.length * 36)}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 0, right: 60, bottom: 0, left: 0 }}
            barCategoryGap="20%"
          >
            <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              type="number"
              tickFormatter={formatDollars}
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={{ stroke: "#334155" }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="shortName"
              width={120}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              content={<ChartTooltip />}
              cursor={{ fill: "rgba(255,255,255,0.03)" }}
            />
            <ReferenceLine
              x={selfHostedValue}
              stroke="#5c7cfa"
              strokeDasharray="6 3"
              strokeWidth={1.5}
              label={{
                value: "Self-Hosted",
                position: "top",
                fill: "#748ffc",
                fontSize: 10,
              }}
            />
            <Bar dataKey={valueKey} radius={[0, 6, 6, 0]} maxBarSize={28}>
              {chartData.map((entry, i) => (
                <Cell
                  key={i}
                  fill={entry.isSelfHosted ? "#5c7cfa" : entry.color}
                  fillOpacity={entry.isSelfHosted ? 1 : 0.75}
                  stroke={entry.isSelfHosted ? "#748ffc" : "transparent"}
                  strokeWidth={entry.isSelfHosted ? 2 : 0}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="mt-3 flex flex-wrap gap-3 text-[10px] text-gray-500">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: "#5c7cfa" }} />
            Self-Hosted (fixed cost)
          </span>
          {Object.entries(PROVIDER_HEX)
            .filter(([k]) => k !== "Self-Hosted")
            .filter(([k]) => data.api_providers.some((p) => p.provider === k))
            .map(([name, color]) => (
              <span key={name} className="flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
                {name} (pay-per-token)
              </span>
            ))}
        </div>
      </div>

      {/* Detailed table */}
      <div className="overflow-x-auto rounded-xl border border-gray-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-800/60 text-gray-500">
            <tr>
              <th className="px-4 py-2.5">Provider</th>
              <th className="px-4 py-2.5">Type</th>
              <th className="px-4 py-2.5 text-right">$/Request</th>
              <th className="px-4 py-2.5 text-right">Monthly</th>
              <th className="px-4 py-2.5 text-right">Breakeven</th>
              <th className="px-4 py-2.5 text-right">vs Self-Hosted</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            <tr className="bg-brand-900/10">
              <td className="px-4 py-2.5 font-medium text-brand-400">
                Self-Hosted ({data.self_hosted_provider.toUpperCase()})
              </td>
              <td className="px-4 py-2.5">
                <span className="inline-flex items-center rounded-full bg-brand-900/40 px-2 py-0.5 text-[10px] font-medium text-brand-300">
                  Dedicated GPU
                </span>
              </td>
              <td className="px-4 py-2.5 text-right font-bold text-white">
                {formatCostPerReq(selfHostedCostPerReq)}
              </td>
              <td className="px-4 py-2.5 text-right font-bold text-white">
                ${data.self_hosted_monthly.toLocaleString()}
              </td>
              <td className="px-4 py-2.5 text-right text-gray-500">—</td>
              <td className="px-4 py-2.5 text-right text-gray-500">baseline</td>
            </tr>
            {data.api_providers
              .slice()
              .sort((a, b) => a.monthly_cost - b.monthly_cost)
              .map((p) => {
                const diffPerReq = p.cost_per_request - selfHostedCostPerReq;
                const pctPerReq =
                  selfHostedCostPerReq > 0
                    ? ((diffPerReq / selfHostedCostPerReq) * 100).toFixed(0)
                    : "—";
                const breakeven = p.cost_per_request > 0
                  ? Math.ceil(data.self_hosted_monthly / p.cost_per_request)
                  : Infinity;
                const userAboveBreakeven = data.monthly_requests >= breakeven;
                return (
                  <tr key={`${p.provider}-${p.model}`} className="hover:bg-gray-800/30 transition-colors">
                    <td className="px-4 py-2.5 font-medium text-gray-300">
                      <span className="inline-block h-2 w-2 rounded-full mr-2" style={{ background: PROVIDER_HEX[p.provider] || "#64748b" }} />
                      {p.provider}{" "}
                      <span className="text-gray-500">{p.model}</span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="inline-flex items-center rounded-full bg-blue-900/30 px-2 py-0.5 text-[10px] font-medium text-blue-400">
                        Pay-per-token
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-gray-400">
                      {formatCostPerReq(p.cost_per_request)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-medium text-white">
                      ${p.monthly_cost.toLocaleString()}
                    </td>
                    <td className={`px-4 py-2.5 text-right text-xs ${userAboveBreakeven ? "text-green-400" : "text-gray-500"}`}>
                      {breakeven < Infinity ? (
                        <>
                          {breakeven.toLocaleString()} req/mo
                          {userAboveBreakeven && <span className="ml-1">✓</span>}
                        </>
                      ) : "—"}
                    </td>
                    <td
                      className={`px-4 py-2.5 text-right font-medium ${
                        diffPerReq > 0 ? "text-red-400" : "text-green-400"
                      }`}
                    >
                      {diffPerReq > 0 ? "+" : ""}
                      {pctPerReq}%
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>

      {/* Why self-host callout */}
      <div className="rounded-xl border border-gray-700 bg-gray-800/40 p-4">
        <h4 className="text-sm font-bold text-gray-200">
          Why self-host even when APIs look cheaper?
        </h4>
        <div className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2 text-xs text-gray-400">
          <div><span className="text-brand-400 font-medium">No rate limits</span> — full control over throughput, no RPM/TPM caps</div>
          <div><span className="text-brand-400 font-medium">Data privacy</span> — data never leaves your infrastructure (HIPAA, GDPR)</div>
          <div><span className="text-brand-400 font-medium">Predictable cost</span> — fixed monthly, no surprise bills from traffic spikes</div>
          <div><span className="text-brand-400 font-medium">Customization</span> — fine-tuning, LoRA, custom inference pipelines</div>
          <div><span className="text-brand-400 font-medium">No vendor lock-in</span> — not dependent on provider uptime or pricing changes</div>
          <div><span className="text-brand-400 font-medium">Low latency</span> — deploy in your own VPC/region for minimal latency</div>
        </div>
      </div>

      {/* Chat subscription reference */}
      <div className="rounded-xl border border-yellow-800/40 bg-yellow-900/10 p-4">
        <h4 className="text-sm font-bold text-yellow-300 flex items-center gap-2">
          <span>💬</span> Chat Subscriptions (not comparable)
        </h4>
        <p className="mt-1 text-xs text-yellow-400/80">
          These are consumer chat plans with strict rate limits — not
          programmatic API access. They cannot handle{" "}
          {data.monthly_requests.toLocaleString()} requests/month.
        </p>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {CHAT_SUBSCRIPTIONS.map((s) => (
            <div
              key={`${s.provider}-${s.plan}`}
              className="flex items-center gap-2 rounded-lg bg-yellow-900/10 px-2.5 py-1.5 text-xs"
            >
              <span className="font-medium text-gray-300 whitespace-nowrap">{s.plan}</span>
              <span className="text-yellow-400 font-bold whitespace-nowrap">
                {s.price === 0 ? "Free" : `$${s.price}/mo`}
              </span>
              <span className="text-gray-500 truncate text-[10px]">{s.limit}</span>
            </div>
          ))}
        </div>
      </div>

      <p className="text-xs text-gray-600">
        API pricing based on published rates. Self-hosted includes compute,
        storage, bandwidth, and KV cache overhead. Actual costs may vary.
      </p>
    </div>
  );
}
