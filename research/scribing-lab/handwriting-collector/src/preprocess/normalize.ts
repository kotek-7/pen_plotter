import type { RawSample } from "../types";

export type NormPoint = { x: number; y: number; t: number; pressure: number; strokeIndex: number };

/**
 * サンプルを文字単位で正規化する (DESIGN §10.1)。
 * bbox の min を引き、max(width,height) で割って [0,1] 付近へ収める。
 * flipY=true で y 軸を上向き (紙座標系) に反転する。
 */
export function normalizeSample(sample: RawSample, opts: { flipY?: boolean } = {}): NormPoint[] {
  const points = sample.strokes.flatMap((s) =>
    s.points.map((p) => ({ ...p, strokeIndex: s.strokeIndex })),
  );
  if (points.length === 0) {
    return [];
  }

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const scale = Math.max(Math.max(...xs) - minX, Math.max(...ys) - minY, 1e-9);

  return points.map((p) => {
    const nx = (p.x - minX) / scale;
    const ny = (p.y - minY) / scale;
    return {
      x: nx,
      y: opts.flipY ? 1 - ny : ny,
      t: p.t,
      pressure: p.pressure,
      strokeIndex: p.strokeIndex,
    };
  });
}
