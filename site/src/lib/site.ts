/** Public site identity and outbound links. */
export const siteUrl = "https://connections-bench.sfreund.tools";

export const githubUrl = "https://github.com/sdfreund10/llm-connections-bench";

export const puzzleSourceUrl =
  "https://github.com/Eyefyre/NYT-Connections-Answers";

export const openRouterUrl = "https://openrouter.ai/";

export const connectionsGameUrl = "https://www.nytimes.com/games/connections";

/** Set when the personal site is ready; empty hides the link. */
export const personalSiteUrl = "";

export const authorName = "Steve Freund";

export const defaultTitle = "llm-connections — LLMs vs Connections";

export const defaultDescription =
  "How well do language models play Connections? Daily results and season standings.";

export function absoluteUrl(pathname: string): string {
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return new URL(path, siteUrl).href;
}
