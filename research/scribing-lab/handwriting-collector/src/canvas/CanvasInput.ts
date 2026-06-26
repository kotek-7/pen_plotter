import type { RawPoint, RawStroke } from "../types";

export type CanvasInputOptions = {
  penOnly: boolean;
  onChange: () => void;
};

/**
 * Canvas の Pointer Events を受け取り、stroke 単位で生の入力点を記録する。
 * 座標は canvas の CSS ピクセル (左上原点)。t はサンプル開始からの相対ミリ秒。
 */
export class CanvasInput {
  private strokes: RawStroke[] = [];
  private current: RawStroke | null = null;
  private sampleStartTime: number | null = null;
  private cancelled = false;
  /** ペンのホバー位置 (CSS px)。Linux 等で OS カーソルが出ないため自前描画する。 */
  private cursor: { x: number; y: number } | null = null;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private options: CanvasInputOptions,
  ) {
    canvas.addEventListener("pointerdown", this.onPointerDown);
    canvas.addEventListener("pointermove", this.onPointerMove);
    canvas.addEventListener("pointerup", this.onPointerUp);
    canvas.addEventListener("pointercancel", this.onPointerCancel);
    canvas.addEventListener("pointerleave", this.onPointerLeave);
    // ペン描画中のスクロール・ジェスチャを抑止する。
    canvas.style.touchAction = "none";
  }

  getCursor(): { x: number; y: number } | null {
    return this.cursor;
  }

  private positionOf(e: PointerEvent): { x: number; y: number } {
    const rect = this.canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  setOptions(options: CanvasInputOptions): void {
    this.options = options;
  }

  getStrokes(): RawStroke[] {
    return this.strokes;
  }

  hasInk(): boolean {
    return this.strokes.length > 0;
  }

  wasCancelled(): boolean {
    return this.cancelled;
  }

  /** 現在のサンプルを破棄して空にする。 */
  reset(): void {
    this.strokes = [];
    this.current = null;
    this.sampleStartTime = null;
    this.cancelled = false;
    this.options.onChange();
  }

  /** 直前の stroke だけ取り消す。 */
  undoLastStroke(): void {
    if (this.current) {
      // 描画途中なら現在の stroke を捨てる。
      this.current = null;
    } else {
      this.strokes.pop();
    }
    this.reindex();
    this.options.onChange();
  }

  private reindex(): void {
    this.strokes.forEach((stroke, index) => {
      stroke.strokeIndex = index;
    });
  }

  private toPoint(e: PointerEvent): RawPoint {
    const rect = this.canvas.getBoundingClientRect();
    const start = this.sampleStartTime ?? e.timeStamp;
    const point: RawPoint = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      t: e.timeStamp - start,
      pressure: e.pressure,
      pointerType: e.pointerType,
    };
    if (e.tiltX !== 0 || e.tiltY !== 0) {
      point.tiltX = e.tiltX;
      point.tiltY = e.tiltY;
    }
    return point;
  }

  private onPointerDown = (e: PointerEvent): void => {
    if (this.options.penOnly && e.pointerType !== "pen") {
      return;
    }
    e.preventDefault();
    try {
      this.canvas.setPointerCapture(e.pointerId);
    } catch {
      // 一部環境/合成イベントでは capture できないことがある。収録は継続する。
    }

    if (this.sampleStartTime === null) {
      this.sampleStartTime = e.timeStamp;
    }

    this.cursor = this.positionOf(e);
    this.current = { strokeIndex: this.strokes.length, points: [this.toPoint(e)] };
    this.strokes.push(this.current);
    this.options.onChange();
  };

  private onPointerMove = (e: PointerEvent): void => {
    if (e.pointerType === "pen") {
      this.cursor = this.positionOf(e);
    }
    if (this.current) {
      const events =
        typeof e.getCoalescedEvents === "function" ? e.getCoalescedEvents() : [e];
      for (const ev of events.length ? events : [e]) {
        this.current.points.push(this.toPoint(ev));
      }
      this.options.onChange();
      return;
    }
    // ホバー: ペンのみ自前カーソルを更新するため再描画する。
    if (e.pointerType === "pen") {
      this.options.onChange();
    }
  };

  private onPointerLeave = (): void => {
    this.cursor = null;
    this.options.onChange();
  };

  private onPointerUp = (e: PointerEvent): void => {
    if (!this.current) {
      return;
    }
    this.current.points.push(this.toPoint(e));
    this.current = null;
    this.options.onChange();
  };

  private onPointerCancel = (): void => {
    if (this.current) {
      this.current = null;
    }
    this.cancelled = true;
    this.options.onChange();
  };
}
