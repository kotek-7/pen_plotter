import type { RawStroke } from "../types";

export type Validation = {
  ok: boolean;
  /** 致命的ではないが確認を促す内容。ok=true でも入りうる。 */
  warning?: string;
  /** ok=false のときの理由。 */
  message?: string;
};

const MIN_POINTS = 5;
const MIN_BBOX_PX = 10;
const MIN_DURATION_MS = 50;
const MAX_DURATION_MS = 30_000;

function flatten(strokes: RawStroke[]) {
  return strokes.flatMap((s) => s.points);
}

/** サンプル確定時の最低限のバリデーション (DESIGN §13.1)。 */
export function validateSample(strokes: RawStroke[]): Validation {
  if (strokes.length === 0) {
    return { ok: false, message: "stroke がありません" };
  }

  const points = flatten(strokes);
  if (points.length < MIN_POINTS) {
    return { ok: false, message: `点が少なすぎます (${points.length} < ${MIN_POINTS})` };
  }

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const width = Math.max(...xs) - Math.min(...xs);
  const height = Math.max(...ys) - Math.min(...ys);
  if (width < MIN_BBOX_PX && height < MIN_BBOX_PX) {
    return { ok: false, message: "筆跡が小さすぎます" };
  }

  const ts = points.map((p) => p.t);
  const duration = Math.max(...ts) - Math.min(...ts);
  if (duration < MIN_DURATION_MS) {
    return { ok: false, message: "筆記時間が短すぎます" };
  }

  // 自動破棄はせず警告のみ (DESIGN §13.2)。
  const pressures = points.map((p) => p.pressure);
  const allZeroPressure = pressures.every((p) => p === 0);
  if (duration > MAX_DURATION_MS) {
    return { ok: true, warning: "筆記時間が長めです。意図したサンプルか確認してください" };
  }
  if (allZeroPressure) {
    return { ok: true, warning: "筆圧が常に0です (デバイスが筆圧未対応の可能性)" };
  }

  return { ok: true };
}
