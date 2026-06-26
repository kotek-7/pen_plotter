import type { PromptItem } from "../types";

/** Fisher-Yates シャッフル (非破壊)。 */
export function shuffle<T>(items: readonly T[]): T[] {
  const out = items.slice();
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/**
 * ラウンドごとに文字順をシャッフルしたプロンプトキューを作る。
 * 同じ文字を連続で書かせないことで運動の最適化による偏りを避ける (DESIGN §5.4)。
 * repetitionIndex は「その文字が何度目か」を表す。
 */
export function buildQueue(chars: readonly string[], rounds: number): PromptItem[] {
  const queue: PromptItem[] = [];
  const repetitionCount = new Map<string, number>();

  for (let round = 0; round < rounds; round += 1) {
    for (const char of shuffle(chars)) {
      const repetitionIndex = repetitionCount.get(char) ?? 0;
      repetitionCount.set(char, repetitionIndex + 1);
      queue.push({
        promptIndex: queue.length,
        char,
        repetitionIndex,
        status: "pending",
      });
    }
  }

  return queue;
}
