import { DATA_VERSION, TOOL_VERSION, type RawSample, type Session } from "../types";

/** dataset を JSONL 文字列へ (1 行 1 サンプル)。 */
export function toJsonl(samples: RawSample[]): string {
  return samples.map((s) => JSON.stringify(s)).join("\n") + (samples.length ? "\n" : "");
}

function stamp(date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
    `_${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
  );
}

function sanitize(value: string): string {
  return value.replace(/[^A-Za-z0-9_-]/g, "");
}

/** DESIGN §14.2 のファイル名規約。 */
export function datasetFilename(session: Session, date = new Date()): string {
  return `handwriting_raw_${sanitize(session.writerId)}_${sanitize(session.charsetName)}_${stamp(date)}.jsonl`;
}

export function metadataFilename(session: Session, date = new Date()): string {
  return `handwriting_meta_${sanitize(session.writerId)}_${sanitize(session.charsetName)}_${stamp(date)}.json`;
}

/** DESIGN §14.3 のメタデータ。 */
export function buildMetadata(session: Session): unknown {
  return {
    dataset_version: DATA_VERSION,
    tool_version: TOOL_VERSION,
    session_id: session.sessionId,
    writer_id: session.writerId,
    charset: session.charsetName,
    rounds: session.rounds,
    sample_count: session.samples.length,
    started_at: session.startedAt,
    created_at: new Date().toISOString(),
    device: {
      user_agent: navigator.userAgent,
      screen_width: window.screen.width,
      screen_height: window.screen.height,
      device_pixel_ratio: window.devicePixelRatio,
    },
  };
}

function download(filename: string, content: string, type: string): void {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // revoke は次フレームで (一部ブラウザで即時 revoke するとDLが失敗する)。
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** dataset (JSONL) と metadata (JSON) をダウンロードする。 */
export function exportSession(session: Session): void {
  const now = new Date();
  download(datasetFilename(session, now), toJsonl(session.samples), "application/x-ndjson");
  download(metadataFilename(session, now), JSON.stringify(buildMetadata(session), null, 2), "application/json");
}
