import { shuffledWords } from "./data";
import { groupColorIndex } from "./colors";
import type { CategoryLevel, Guess, Puzzle } from "./types";

export interface SolvedRow {
  words: string[];
  categoryIndex: CategoryLevel;
}

export interface ResultBoard {
  solvedRows: SolvedRow[];
  unsolvedWords: string[];
}

/** Match a correct guess to its category index in the puzzle data. */
export function categoryIndexForGuess(puzzle: Puzzle, guess: string[]): CategoryLevel | undefined {
  const sorted = [...guess].sort().join("\0");
  const idx = puzzle.answers.findIndex((group) => {
    const members = [...group.members].sort().join("\0");
    return members === sorted;
  });
  return idx >= 0 ? groupColorIndex(idx) : undefined;
}

/** Build NYT-style board: solved groups stacked at top, rest in grid below. */
export function buildResultBoard(puzzle: Puzzle, guesses: Guess[]): ResultBoard {
  const unsolved = new Set(shuffledWords(puzzle));
  const solvedRows: SolvedRow[] = [];

  for (const g of guesses) {
    if (!g.success) continue;
    const categoryIndex = categoryIndexForGuess(puzzle, g.guess);
    if (categoryIndex === undefined) continue;
    for (const word of g.guess) unsolved.delete(word);
    solvedRows.push({ words: g.guess, categoryIndex });
  }

  return {
    solvedRows,
    unsolvedWords: [...unsolved],
  };
}
