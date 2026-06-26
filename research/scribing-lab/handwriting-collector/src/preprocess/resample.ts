import type { RawSample, RawStroke } from "../types";

export type ResampledPoint = { x: number; y: number; t: number; pressure: number; strokeIndex: number };

/** stroke 内を一定時間間隔で線形補間する (DESIGN §10.2)。stroke 境界は跨がない。 */
function resampleStroke(stroke: RawStroke, intervalMs: number): ResampledPoint[] {
  const pts = stroke.points;
  if (pts.length === 0) {
    return [];
  }
  if (pts.length === 1) {
    return [{ ...pts[0], strokeIndex: stroke.strokeIndex }];
  }

  const out: ResampledPoint[] = [];
  const start = pts[0].t;
  const end = pts[pts.length - 1].t;
  let j = 0;
  for (let t = start; t <= end + 1e-6; t += intervalMs) {
    while (j < pts.length - 2 && pts[j + 1].t < t) {
      j += 1;
    }
    const a = pts[j];
    const b = pts[j + 1];
    const span = b.t - a.t;
    const r = span > 1e-9 ? (t - a.t) / span : 0;
    out.push({
      x: a.x + (b.x - a.x) * r,
      y: a.y + (b.y - a.y) * r,
      t,
      pressure: a.pressure + (b.pressure - a.pressure) * r,
      strokeIndex: stroke.strokeIndex,
    });
  }
  return out;
}

/** サンプル全体を Hz 指定で再サンプリングする。 */
export function resampleSample(sample: RawSample, hz: number): ResampledPoint[] {
  const intervalMs = 1000 / hz;
  return sample.strokes.flatMap((s) => resampleStroke(s, intervalMs));
}
