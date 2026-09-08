import type { CategoryLevel } from "./types";

export const CATEGORY_COLORS: Record<CategoryLevel, { bg: string; text: string; label: string }> = {
  0: { bg: "#f8df00", text: "#1a1a1a", label: "Yellow" },
  1: { bg: "#6aaa64", text: "#ffffff", label: "Green" },
  2: { bg: "#4a90d9", text: "#ffffff", label: "Blue" },
  3: { bg: "#bc9fdd", text: "#1a1a1a", label: "Purple" },
};

export function groupColorIndex(groupIndex: number): CategoryLevel {
  return Math.min(groupIndex, 3) as CategoryLevel;
}
