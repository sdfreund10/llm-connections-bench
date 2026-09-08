export type CategoryLevel = 0 | 1 | 2 | 3;

export interface PuzzleGroup {
  level: number;
  group: string;
  members: string[];
}

export interface Puzzle {
  id: number;
  date: string;
  answers: PuzzleGroup[];
}

export interface Guess {
  guess: string[];
  reasoning: string;
  success: boolean;
  latency?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_cost?: number;
}

export interface ModelRun {
  status: "in_progress" | "completed";
  guesses: Guess[];
  outcome?: "solved" | "lost";
  mistakes?: number;
  invalid_guesses?: number;
  solved_groups?: number;
  llm_wait_s?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_cost?: number;
}

export type GamesLog = Record<string, Record<string, ModelRun>>;

export interface ModelStats {
  model: string;
  games: number;
  solved: number;
  lost: number;
  winRate: number;
  avgMistakes: number;
  avgWaitS: number | null;
  totalCost: number | null;
  totalTokens: number | null;
}

export interface DateSummary {
  date: string;
  puzzle: Puzzle | null;
  runs: Array<{ model: string; run: ModelRun }>;
}
