import type { RawSample } from "../types";
import { normalizeSample } from "./normalize";

/** pen 状態の one-hot: [pen_down, pen_up, end] (DESIGN §10.4)。 */
export type PenState = [number, number, number];
export const PEN_DOWN: PenState = [1, 0, 0];
export const PEN_UP: PenState = [0, 1, 0];
export const PEN_END: PenState = [0, 0, 1];

export type Stroke3Point = { dx: number; dy: number; pen: PenState };

export type Stroke3Sample = {
  char: string;
  charCode: string;
  seq: Stroke3Point[];
};

/**
 * 正規化 → dx,dy 差分 → pen_state 付与 (DESIGN §10.3, §10.4, §10.5)。
 * stroke 内は pen_down、stroke 間の移動は pen_up、末尾に end を付ける。
 */
export function toStroke3(sample: RawSample, opts: { flipY?: boolean } = {}): Stroke3Sample {
  const points = normalizeSample(sample, opts);
  const seq: Stroke3Point[] = [];

  let prevX = 0;
  let prevY = 0;
  let prevStroke = -1;
  let started = false;

  for (const p of points) {
    if (!started) {
      // 最初の点は原点 (dx=dy=0)、pen_down。
      seq.push({ dx: 0, dy: 0, pen: PEN_DOWN });
      prevX = p.x;
      prevY = p.y;
      prevStroke = p.strokeIndex;
      started = true;
      continue;
    }

    const dx = p.x - prevX;
    const dy = p.y - prevY;
    // stroke が変わった最初の移動は pen_up (前の stroke 末からの渡り)。
    const pen = p.strokeIndex !== prevStroke ? PEN_UP : PEN_DOWN;
    seq.push({ dx, dy, pen });
    prevX = p.x;
    prevY = p.y;
    prevStroke = p.strokeIndex;
  }

  if (seq.length > 0) {
    seq.push({ dx: 0, dy: 0, pen: PEN_END });
  }

  return { char: sample.char, charCode: sample.charCode, seq };
}
