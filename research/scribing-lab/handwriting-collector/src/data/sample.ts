import {
  DATA_VERSION,
  type CanvasSettings,
  type Guide,
  type PromptItem,
  type RawSample,
  type RawStroke,
} from "../types";

/** code point を "U+XXXX" 形式へ。サロゲートペアにも対応する。 */
export function charCodeLabel(char: string): string {
  const code = char.codePointAt(0);
  if (code === undefined) {
    return "U+0000";
  }
  return `U+${code.toString(16).toUpperCase().padStart(4, "0")}`;
}

/** ローカルタイムゾーンつき ISO 8601 文字列 (例: 2026-06-26T10:00:00.000+09:00)。 */
export function localISO(date = new Date()): string {
  const tzMinutes = -date.getTimezoneOffset();
  const sign = tzMinutes >= 0 ? "+" : "-";
  const abs = Math.abs(tzMinutes);
  const pad = (n: number, width = 2) => String(n).padStart(width, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}` +
    `.${pad(date.getMilliseconds(), 3)}${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
  );
}

export function sampleId(writerId: string, sequence: number): string {
  return `${writerId}_${String(sequence).padStart(6, "0")}`;
}

export function buildSample(args: {
  writerId: string;
  charsetName: string;
  prompt: PromptItem;
  strokes: RawStroke[];
  canvas: CanvasSettings;
  guide: Guide;
  sequence: number;
}): RawSample {
  return {
    version: DATA_VERSION,
    sampleId: sampleId(args.writerId, args.sequence),
    writerId: args.writerId,
    char: args.prompt.char,
    charCode: charCodeLabel(args.prompt.char),
    charsetName: args.charsetName,
    promptIndex: args.prompt.promptIndex,
    repetitionIndex: args.prompt.repetitionIndex,
    createdAt: localISO(),
    canvas: { ...args.canvas },
    guide: { cell: { ...args.guide.cell } },
    strokes: args.strokes,
  };
}
