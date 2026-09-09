/**
 * Shared price/context/capability formatting for anywhere a model is listed
 * — the External Providers "Fetch available models" list, the Task
 * Shortlist picker, and the Rule Extraction model dropdown — so all three
 * render the same OpenRouter pricing data (or the same "no published
 * pricing" fallback for providers that don't publish it) identically.
 */

interface ModelMetaSource {
  context_length?: number | null;
  input_price_per_million?: number | null;
  output_price_per_million?: number | null;
}

function formatPrice(value: number): string {
  if (value === 0) return "free";
  // Sub-cent per-million prices (e.g. $0.15) still deserve 2 decimals;
  // anything under $0.01 gets a 4th so it doesn't round away to "$0.00".
  const decimals = value < 0.01 ? 4 : 2;
  return `$${value.toFixed(decimals)}`;
}

function formatContext(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(tokens % 1_000_000 ? 1 : 0)}M ctx`;
  if (tokens >= 1_000) return `${Math.round(tokens / 1000)}K ctx`;
  return `${tokens} ctx`;
}

/** e.g. "$3.00 / $15.00 per 1M · 200K ctx", or "no published pricing" when a
 * driver's provider doesn't expose this data (see LLMProviderModel). */
export function formatModelMeta(model: ModelMetaSource): string {
  const parts: string[] = [];
  const { input_price_per_million: inputPrice, output_price_per_million: outputPrice } = model;
  if (inputPrice != null || outputPrice != null) {
    const inStr = inputPrice != null ? formatPrice(inputPrice) : "?";
    const outStr = outputPrice != null ? formatPrice(outputPrice) : "?";
    parts.push(`${inStr} / ${outStr} per 1M`);
  }
  if (model.context_length != null) {
    parts.push(formatContext(model.context_length));
  }
  return parts.length > 0 ? parts.join(" · ") : "no published pricing";
}
