/** Query param for the global visible-model filter. */
export const MODEL_QUERY_PARAM = "models";

/**
 * Featured models when the URL has no `models` param.
 * One representative each from OpenAI, Anthropic, and Google.
 */
export const DEFAULT_MODELS = [
  "openai/gpt-4.1",
  "anthropic/claude-haiku-4.5",
  "google/gemini-3.7-flash",
] as const;

export function parseModelsParam(search: string): string[] | null {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  if (!params.has(MODEL_QUERY_PARAM)) return null;
  const raw = params.get(MODEL_QUERY_PARAM) ?? "";
  if (raw === "") return [];
  return raw
    .split(",")
    .map((s) => {
      try {
        return decodeURIComponent(s.trim());
      } catch {
        return s.trim();
      }
    })
    .filter(Boolean);
}

export function serializeModelsParam(models: string[]): string {
  // Join only — URLSearchParams encodes `/` and other reserved chars once.
  return models.join(",");
}

export function defaultVisibleModels(available: string[]): string[] {
  const set = new Set(available);
  return DEFAULT_MODELS.filter((m) => set.has(m));
}

/** Resolve selection from the URL, falling back to curated defaults. */
export function resolveSelectedModels(search: string, available: string[]): string[] {
  const availableSet = new Set(available);
  const parsed = parseModelsParam(search);
  if (parsed === null) {
    return defaultVisibleModels(available);
  }
  return available.filter((m) => parsed.includes(m) && availableSet.has(m));
}

export function sameModelSet(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const set = new Set(a);
  return b.every((m) => set.has(m));
}
