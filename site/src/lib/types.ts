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
}

export interface ModelRun {
  status: "in_progress" | "completed";
  guesses: Guess[];
  outcome?: "solved" | "lost";
  mistakes?: number;
  invalid_guesses?: number;
}

export type GamesLog = Record<string, Record<string, ModelRun>>;

export interface ModelStats {
  model: string;
  games: number;
  solved: number;
  lost: number;
  winRate: number;
  avgMistakes: number;
}

export interface DateSummary {
  date: string;
  puzzle: Puzzle | null;
  runs: Array<{ model: string; run: ModelRun }>;
}
