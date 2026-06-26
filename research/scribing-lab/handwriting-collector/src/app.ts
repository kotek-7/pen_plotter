import { CanvasInput } from "./canvas/CanvasInput";
import { StrokeRenderer } from "./canvas/StrokeRenderer";
import { buildSample } from "./data/sample";
import { validateSample } from "./data/validate";
import { exportSession } from "./data/exportJsonl";
import { saveSession } from "./state/sessionStore";
import type { Guide, PromptItem, Session } from "./types";

/**
 * 書字セル枠の余白比。枠外の余白は、box を出る払い/はね/はみ出しを取りこぼさない
 * ための領域。和文は枠を埋めて書くため、余白は広めにとる。
 */
const GUIDE_MARGIN_RATIO = 0.18;

function computeGuide(width: number, height: number): Guide {
  const margin = Math.round(Math.min(width, height) * GUIDE_MARGIN_RATIO);
  const cell = { x: margin, y: margin, width: width - 2 * margin, height: height - 2 * margin };
  return { cell };
}

type Refs = {
  recorder: HTMLElement;
  canvas: HTMLCanvasElement;
  promptChar: HTMLElement;
  writerLabel: HTMLElement;
  progressLabel: HTMLElement;
  repLabel: HTMLElement;
  stats: HTMLElement;
  warning: HTMLElement;
};

export class App {
  private readonly refs: Refs;
  private input!: CanvasInput;
  private renderer!: StrokeRenderer;
  private guide!: Guide;
  private paused = false;
  private finished = false;

  constructor(private readonly session: Session) {
    this.refs = {
      recorder: must("recorder"),
      canvas: must("canvas") as HTMLCanvasElement,
      promptChar: must("promptChar"),
      writerLabel: must("writerLabel"),
      progressLabel: must("progressLabel"),
      repLabel: must("repLabel"),
      stats: must("stats"),
      warning: must("warning"),
    };
  }

  start(): void {
    this.refs.recorder.hidden = false;
    this.setupCanvas();
    this.input = new CanvasInput(this.refs.canvas, {
      penOnly: this.session.penOnly,
      onChange: () => this.onInkChange(),
    });
    window.addEventListener("keydown", this.onKeyDown);
    this.refs.writerLabel.textContent = `Writer: ${this.session.writerId}`;
    this.renderPrompt();
  }

  private setupCanvas(): void {
    const { width, height, devicePixelRatio: dpr } = this.session.canvas;
    const canvas = this.refs.canvas;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      throw new Error("2d context unavailable");
    }
    ctx.scale(dpr, dpr);
    this.renderer = new StrokeRenderer(canvas, width, height);
    this.guide = computeGuide(width, height);
  }

  private currentPrompt(): PromptItem | undefined {
    return this.session.queue[this.session.cursor];
  }

  private renderPrompt(): void {
    const total = this.session.queue.length;
    const done = this.session.samples.length;
    this.refs.progressLabel.textContent = `Progress: ${done} / ${total}`;

    const prompt = this.currentPrompt();
    if (!prompt) {
      this.complete();
      return;
    }
    this.refs.promptChar.textContent = prompt.char;
    this.refs.repLabel.textContent = `サンプル: ${prompt.repetitionIndex + 1} / ${this.session.rounds}`;
    this.input?.reset();
    this.renderer.clear();
    this.onInkChange();
  }

  private onInkChange(): void {
    if (!this.input) {
      return;
    }
    const strokes = this.input.getStrokes();
    this.renderer.render(strokes, {
      colorByStroke: true,
      showBBox: true,
      showEndpoints: true,
      guide: this.guide,
      cursor: this.input.getCursor(),
    });
    const points = strokes.reduce((n, s) => n + s.points.length, 0);
    this.refs.stats.textContent = `strokes: ${strokes.length} / points: ${points}`;
    if (this.input.wasCancelled()) {
      this.warn("pointercancel が発生しました。書き直しを推奨します");
    }
  }

  private commit(): void {
    if (this.finished || this.paused) {
      return;
    }
    const prompt = this.currentPrompt();
    if (!prompt) {
      return;
    }
    const strokes = this.input.getStrokes();
    const validation = validateSample(strokes);
    if (!validation.ok) {
      this.warn(validation.message ?? "無効なサンプルです");
      return;
    }

    const sample = buildSample({
      writerId: this.session.writerId,
      charsetName: this.session.charsetName,
      prompt,
      strokes,
      canvas: this.session.canvas,
      guide: this.guide,
      sequence: this.session.samples.length + 1,
    });
    this.session.samples.push(sample);
    prompt.status = "done";
    this.session.cursor += 1;
    saveSession(this.session);
    this.clearWarning();
    if (validation.warning) {
      this.warn(validation.warning);
    }
    this.renderPrompt();
  }

  private retry(): void {
    this.input.reset();
    this.clearWarning();
  }

  private undo(): void {
    this.input.undoLastStroke();
  }

  private save(): void {
    if (this.session.samples.length === 0) {
      this.warn("保存できるサンプルがありません");
      return;
    }
    exportSession(this.session);
  }

  private togglePause(): void {
    this.paused = !this.paused;
    this.refs.canvas.style.pointerEvents = this.paused ? "none" : "auto";
    this.refs.recorder.classList.toggle("paused", this.paused);
  }

  private complete(): void {
    this.finished = true;
    this.session.completedAt = new Date().toISOString();
    saveSession(this.session);
    this.refs.promptChar.textContent = "完了";
    this.refs.repLabel.textContent = "全サンプルを収録しました";
    this.refs.stats.textContent = `合計 ${this.session.samples.length} サンプル`;
    exportSession(this.session);
  }

  private warn(message: string): void {
    this.refs.warning.textContent = message;
    this.refs.warning.hidden = false;
  }

  private clearWarning(): void {
    this.refs.warning.textContent = "";
    this.refs.warning.hidden = true;
  }

  private onKeyDown = (e: KeyboardEvent): void => {
    // Ctrl+Z / Cmd+Z で直前の stroke を取り消す (Shift 併用は対象外)。
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && (e.key === "z" || e.key === "Z")) {
      e.preventDefault();
      this.undo();
      return;
    }

    switch (e.key) {
      case " ":
      case "Enter":
        e.preventDefault();
        this.commit();
        break;
      case "Backspace":
      case "r":
      case "R":
        e.preventDefault();
        this.retry();
        break;
      case "u":
      case "U":
        e.preventDefault();
        this.undo();
        break;
      case "s":
      case "S":
        e.preventDefault();
        this.save();
        break;
      case "p":
      case "P":
        e.preventDefault();
        this.togglePause();
        break;
      case "Escape":
        e.preventDefault();
        saveSession(this.session);
        location.reload();
        break;
      default:
        break;
    }
  };
}

function must(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`missing element #${id}`);
  }
  return el;
}
