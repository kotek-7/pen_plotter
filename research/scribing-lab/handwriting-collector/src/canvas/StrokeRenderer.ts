import type { RawStroke } from "../types";

export type RenderOptions = {
  colorByStroke?: boolean;
  showBBox?: boolean;
  showEndpoints?: boolean;
  pressureWidth?: boolean;
};

const STROKE_COLORS = ["#1f2937", "#2563eb", "#dc2626", "#059669", "#7c3aed", "#d97706"];

/** stroke 列を 2D context に描画する。座標は CSS ピクセル想定。 */
export class StrokeRenderer {
  private readonly ctx: CanvasRenderingContext2D;

  constructor(
    canvas: HTMLCanvasElement,
    private readonly cssWidth: number,
    private readonly cssHeight: number,
  ) {
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      throw new Error("2d context unavailable");
    }
    this.ctx = ctx;
  }

  clear(): void {
    this.ctx.clearRect(0, 0, this.cssWidth, this.cssHeight);
  }

  render(strokes: RawStroke[], options: RenderOptions = {}): void {
    this.clear();
    const ctx = this.ctx;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    strokes.forEach((stroke, index) => {
      if (stroke.points.length === 0) {
        return;
      }
      const color = options.colorByStroke
        ? STROKE_COLORS[index % STROKE_COLORS.length]
        : "#1f2937";
      ctx.strokeStyle = color;

      if (options.pressureWidth) {
        this.renderPressure(stroke);
      } else {
        ctx.lineWidth = 2.4;
        ctx.beginPath();
        stroke.points.forEach((p, i) => {
          if (i === 0) ctx.moveTo(p.x, p.y);
          else ctx.lineTo(p.x, p.y);
        });
        ctx.stroke();
      }

      if (options.showEndpoints) {
        this.dot(stroke.points[0].x, stroke.points[0].y, "#059669");
        const last = stroke.points[stroke.points.length - 1];
        this.dot(last.x, last.y, "#dc2626");
      }
    });

    if (options.showBBox) {
      this.renderBBox(strokes);
    }
  }

  private renderPressure(stroke: RawStroke): void {
    const ctx = this.ctx;
    for (let i = 1; i < stroke.points.length; i += 1) {
      const a = stroke.points[i - 1];
      const b = stroke.points[i];
      const pressure = (a.pressure + b.pressure) / 2;
      ctx.lineWidth = 0.8 + pressure * 4.0;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
  }

  private dot(x: number, y: number, color: string): void {
    const ctx = this.ctx;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fill();
  }

  private renderBBox(strokes: RawStroke[]): void {
    const points = strokes.flatMap((s) => s.points);
    if (points.length === 0) {
      return;
    }
    const xs = points.map((p) => p.x);
    const ys = points.map((p) => p.y);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const ctx = this.ctx;
    ctx.save();
    ctx.strokeStyle = "rgba(0,0,0,0.25)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.strokeRect(minX, minY, Math.max(...xs) - minX, Math.max(...ys) - minY);
    ctx.restore();
  }
}
