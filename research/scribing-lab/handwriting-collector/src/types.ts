export const DATA_VERSION = "0.1";
export const TOOL_VERSION = "0.1.0";

/** 収録された生の入力点。ブラウザイベントをできるだけそのまま保持する。 */
export type RawPoint = {
  x: number;
  y: number;
  /** サンプル開始時刻を 0 とする相対ミリ秒。 */
  t: number;
  pressure: number;
  tiltX?: number;
  tiltY?: number;
  pointerType: string;
};

/** 一画 (pen down から pen up まで)。 */
export type RawStroke = {
  strokeIndex: number;
  points: RawPoint[];
};

/** 1文字サンプル。JSONL の 1 行に対応する。 */
export type RawSample = {
  version: string;
  sampleId: string;
  writerId: string;
  char: string;
  charCode: string;
  charsetName: string;
  promptIndex: number;
  repetitionIndex: number;
  createdAt: string;
  canvas: {
    width: number;
    height: number;
    devicePixelRatio: number;
  };
  strokes: RawStroke[];
};

export type PromptStatus = "pending" | "done" | "skipped";

export type PromptItem = {
  promptIndex: number;
  char: string;
  repetitionIndex: number;
  status: PromptStatus;
};

export type CanvasSettings = {
  width: number;
  height: number;
  devicePixelRatio: number;
};

export type Session = {
  sessionId: string;
  writerId: string;
  charsetName: string;
  rounds: number;
  penOnly: boolean;
  canvas: CanvasSettings;
  startedAt: string;
  completedAt?: string;
  cursor: number;
  queue: PromptItem[];
  samples: RawSample[];
};

export type SetupConfig = {
  writerId: string;
  charsetName: string;
  rounds: number;
  canvasSize: number;
  penOnly: boolean;
};
