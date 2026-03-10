"use client";

import type { APIProviderComparison } from "@/types";

const PROVIDER_COLORS: Record<string, string> = {
  OpenAI: "bg-green-500",
  Anthropic: "bg-orange-500",
  Google: "bg-blue-500",
  Mistral: "bg-purple-500",
  "Self-Hosted": "bg-brand-500",
};

export function APIProviderComparisonCard({
  data,
}: {
  data: APIProviderComparison;
}) {
  const maxCost = Math.max(
    ...data.api_providers.map((p) => p.monthly_cost),
    data.self_hosted_monthly
  );

  // Count how many providers are more expensive than self-hosted
  const moreExpensive = data.api_providers.filter(
    (p) => p.monthly_cost > data.self_hosted_monthly
  ).length;

  return (
    <div className="card">
      <h3 className="text-lg font-bold text-white">
        Self-Hosted vs API Providers
      </h3>
      <p className="mt-1 text-sm text-gray-400">
        Based on{" "}
        <span className="text-white font-medium">
          {data.monthly_requests.toLocaleString()}
        </span>{" "}
        requests/month ({data.avg_input_tokens_per_request} input +{" "}
        {data.avg_output_tokens_per_request} output tokens per request)
      </p>

      {/* Summary banner */}
      {moreExpensive > 0 && (
        <div className="mt-4 rounded-lg border border-green-800 bg-green-900/20 p-3">
          <p className="text-sm text-green-300">
            Self-hosting is cheaper than{" "}
            <span className="font-bold">{moreExpensive}</span> of{" "}
            {data.api_providers.length} API providers at your usage level.
            {data.api_providers.length > 0 && (
              <>
                {" "}
                You save up to{" "}
                <span className="font-bold text-green-200">
                  $
                  {(
                    data.api_providers[data.api_providers.length - 1]
                      .monthly_cost - data.self_hosted_monthly
                  ).toLocaleString()}
                  /mo
                </span>{" "}
                vs {data.api_providers[data.api_providers.length - 1].provider}{" "}
                {data.api_providers[data.api_providers.length - 1].model}.
              </>
            )}
          </p>
        </div>
      )}

      {/* Bar chart comparison */}
      <div className="mt-6 space-y-3">
        {/* Self-hosted bar (always first) */}
        <ComparisonBar
          label={`Self-Hosted (${data.self_hosted_provider.toUpperCase()})`}
          cost={data.self_hosted_monthly}
          maxCost={maxCost}
          color="bg-brand-500"
          highlight
        />

        {/* Divider */}
        <div className="border-t border-gray-700 my-2" />

        {/* API provider bars */}
        {data.api_providers.map((p) => (
          <ComparisonBar
            key={`${p.provider}-${p.model}`}
            label={`${p.provider} — ${p.model}`}
            cost={p.monthly_cost}
            maxCost={maxCost}
            color={PROVIDER_COLORS[p.provider] || "bg-gray-500"}
            cheaper={p.monthly_cost < data.self_hosted_monthly}
            moreExpensive={p.monthly_cost > data.self_hosted_monthly}
            savings={
              p.monthly_cost > data.self_hosted_monthly
                ? p.monthly_cost - data.self_hosted_monthly
                : undefined
            }
          />
        ))}
      </div>

      {/* Detailed table */}
      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-700 text-gray-500">
            <tr>
              <th className="pb-2 pr-4">Provider</th>
              <th className="pb-2 pr-4 text-right">Input $/1M</th>
              <th className="pb-2 pr-4 text-right">Output $/1M</th>
              <th className="pb-2 pr-4 text-right">Monthly</th>
              <th className="pb-2 text-right">vs Self-Hosted</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            <tr className="bg-brand-900/10">
              <td className="py-2.5 pr-4 font-medium text-brand-400">
                Self-Hosted ({data.self_hosted_provider.toUpperCase()})
              </td>
              <td className="py-2.5 pr-4 text-right text-gray-400">—</td>
              <td className="py-2.5 pr-4 text-right text-gray-400">—</td>
              <td className="py-2.5 pr-4 text-right font-bold text-white">
                ${data.self_hosted_monthly.toLocaleString()}
              </td>
              <td className="py-2.5 text-right text-gray-500">baseline</td>
            </tr>
            {data.api_providers.map((p) => {
              const diff = p.monthly_cost - data.self_hosted_monthly;
              const pct =
                data.self_hosted_monthly > 0
                  ? ((diff / data.self_hosted_monthly) * 100).toFixed(0)
                  : "—";
              return (
                <tr key={`${p.provider}-${p.model}`}>
                  <td className="py-2.5 pr-4 font-medium text-gray-300">
                    {p.provider}{" "}
                    <span className="text-gray-500">{p.model}</span>
                  </td>
                  <td className="py-2.5 pr-4 text-right text-gray-400">
                    ${p.input_cost_per_million}
                  </td>
                  <td className="py-2.5 pr-4 text-right text-gray-400">
                    ${p.output_cost_per_million}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-medium text-white">
                    ${p.monthly_cost.toLocaleString()}
                  </td>
                  <td
                    className={`py-2.5 text-right font-medium ${
                      diff > 0 ? "text-red-400" : "text-green-400"
                    }`}
                  >
                    {diff > 0 ? "+" : ""}
                    {pct}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-4 text-xs text-gray-600">
        API pricing based on published rates. Self-hosted cost includes compute,
        storage, bandwidth, and KV cache overhead. Actual costs may vary.
      </p>
    </div>
  );
}

function ComparisonBar({
  label,
  cost,
  maxCost,
  color,
  highlight = false,
  cheaper = false,
  moreExpensive = false,
  savings,
}: {
  label: string;
  cost: number;
  maxCost: number;
  color: string;
  highlight?: boolean;
  cheaper?: boolean;
  moreExpensive?: boolean;
  savings?: number;
}) {
  const width = maxCost > 0 ? Math.max((cost / maxCost) * 100, 2) : 2;

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span
          className={
            highlight
              ? "font-bold text-brand-400"
              : cheaper
              ? "text-green-400"
              : "text-gray-300"
          }
        >
          {label}
        </span>
        <span className="flex items-center gap-2">
          <span
            className={
              highlight
                ? "font-bold text-white"
                : moreExpensive
                ? "text-red-400"
                : cheaper
                ? "text-green-400"
                : "text-gray-300"
            }
          >
            ${cost.toLocaleString()}/mo
          </span>
          {savings && (
            <span className="text-xs text-red-400/70">
              +${savings.toLocaleString()}
            </span>
          )}
        </span>
      </div>
      <div className="h-2.5 w-full rounded-full bg-gray-800">
        <div
          className={`h-2.5 rounded-full ${color} ${
            highlight ? "ring-1 ring-brand-400/50" : ""
          }`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}
