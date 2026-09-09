import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { GamesLog, Guess, ModelRun, ModelStats, Puzzle, DateSummary } from "./types";

const DATA_DIR = resolve(process.env.DATA_DIR ?? resolve(process.cwd(), "../data"));
const MIN_DATE = "2026-08-01";
export const HOME_PAGE_SIZE = 7;

function loadJson<T>(filename: string): T {
  return JSON.parse(readFileSync(resolve(DATA_DIR, filename), "utf-8")) as T;
}

export function getPuzzles(): Puzzle[] {
  const all = loadJson<Puzzle[]>("connections.json");
  return all.filter((p) => p.date >= MIN_DATE);
}

export function getPuzzleByDate(date: string): Puzzle | undefined {
  return getPuzzles().find((p) => p.date === date);
}

export function getGamesLog(): GamesLog {
  return loadJson<GamesLog>("games.json");
}

/** Deterministic shuffle so the board looks scrambled but stable per date. */
export function shuffledWords(puzzle: Puzzle): string[] {
  const words = puzzle.answers.flatMap((g) => g.members);
  let seed = 0;
  for (const ch of puzzle.date) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
  const arr = [...words];
  for (let i = arr.length - 1; i > 0; i--) {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    const j = seed % (i + 1);
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

export function getDatesWithRuns(): string[] {
  const log = getGamesLog();
  return Object.keys(log)
    .filter((d) => d >= MIN_DATE)
    .sort((a, b) => b.localeCompare(a));
}

export function getAllDateSummaries(): DateSummary[] {
  const log = getGamesLog();
  return getDatesWithRuns().map((date) => ({
    date,
    puzzle: getPuzzleByDate(date) ?? null,
    runs: Object.entries(log[date] ?? {})
      .map(([model, run]) => ({ model, run }))
      .sort((a, b) => a.model.localeCompare(b.model)),
  }));
}

export function getHomePageCount(pageSize = HOME_PAGE_SIZE): number {
  const total = getDatesWithRuns().length;
  return total === 0 ? 1 : Math.ceil(total / pageSize);
}

export function getPaginatedDates(page: number, pageSize = HOME_PAGE_SIZE): DateSummary[] {
  const all = getAllDateSummaries();
  const start = (page - 1) * pageSize;
  return all.slice(start, start + pageSize);
}

/** @deprecated Use getPaginatedDates for home; kept for any legacy callers */
export function getRecentDates(limit = HOME_PAGE_SIZE): DateSummary[] {
  return getPaginatedDates(1, limit);
}

export function getDateSummary(date: string): DateSummary | null {
  const log = getGamesLog();
  if (!log[date]) return null;
  return {
    date,
    puzzle: getPuzzleByDate(date) ?? null,
    runs: Object.entries(log[date])
      .map(([model, run]) => ({ model, run }))
      .sort((a, b) => a.model.localeCompare(b.model)),
  };
}

/** All model IDs present in the games log (corpus window), sorted. */
export function getAllModelIds(): string[] {
  const log = getGamesLog();
  const models = new Set<string>();
  for (const [date, day] of Object.entries(log)) {
    if (date < MIN_DATE) continue;
    for (const model of Object.keys(day)) models.add(model);
  }
  return [...models].sort((a, b) => a.localeCompare(b));
}

export function getModelStats(): ModelStats[] {
  const log = getGamesLog();
  const byModel = new Map<
    string,
    {
      solved: number;
      lost: number;
      mistakes: number;
      waitS: number;
      waitGames: number;
      totalCost: number;
      costGames: number;
      totalTokens: number;
      tokenGames: number;
    }
  >();

  for (const [date, day] of Object.entries(log)) {
    if (date < MIN_DATE) continue;
    for (const [model, run] of Object.entries(day)) {
      if (run.status !== "completed") continue;
      const entry = byModel.get(model) ?? {
        solved: 0,
        lost: 0,
        mistakes: 0,
        waitS: 0,
        waitGames: 0,
        totalCost: 0,
        costGames: 0,
        totalTokens: 0,
        tokenGames: 0,
      };
      if (run.outcome === "solved") entry.solved += 1;
      else if (run.outcome === "lost") entry.lost += 1;
      entry.mistakes += run.mistakes ?? 0;
      if (typeof run.llm_wait_s === "number") {
        entry.waitS += run.llm_wait_s;
        entry.waitGames += 1;
      }
      if (typeof run.total_cost === "number") {
        entry.totalCost += run.total_cost;
        entry.costGames += 1;
      }
      const tokens = (run.input_tokens ?? 0) + (run.output_tokens ?? 0);
      if (run.input_tokens != null || run.output_tokens != null) {
        entry.totalTokens += tokens;
        entry.tokenGames += 1;
      }
      byModel.set(model, entry);
    }
  }

  return [...byModel.entries()]
    .map(([model, s]) => {
      const games = s.solved + s.lost;
      return {
        model,
        games,
        solved: s.solved,
        lost: s.lost,
        winRate: games ? s.solved / games : 0,
        avgMistakes: games ? s.mistakes / games : 0,
        avgWaitS: s.waitGames ? s.waitS / s.waitGames : null,
        avgCost: s.costGames ? s.totalCost / s.costGames : null,
        avgTokens: s.tokenGames ? s.totalTokens / s.tokenGames : null,
      };
    })
    .sort((a, b) => b.winRate - a.winRate || a.avgMistakes - b.avgMistakes);
}

export function formatLatency(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;
}

export function formatCost(cost: number): string {
  if (cost === 0) return "$0";
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(3)}`;
}

export function formatTokens(n: number): string {
  const rounded = Math.round(n);
  if (rounded >= 1000) return `${(rounded / 1000).toFixed(rounded >= 10000 ? 0 : 1)}k`;
  return String(rounded);
}

export function shortModelName(model: string): string {
  const parts = model.split("/");
  return parts[parts.length - 1] ?? model;
}

export function formatDate(date: string): string {
  const d = new Date(`${date}T12:00:00`);
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function isCompleted(run: ModelRun): run is ModelRun & {
  outcome: "solved" | "lost";
  mistakes: number;
} {
  return run.status === "completed" && run.outcome != null;
}

export function solvedCategoryCount(guesses: Guess[]): number {
  return guesses.filter((g) => g.success).length;
}

const CATEGORY_TOTAL = 4;
export { CATEGORY_TOTAL };
