import { App } from "./app";
import { CHARSETS, getCharset } from "./data/charset";
import { buildQueue } from "./data/queue";
import { localISO } from "./data/sample";
import { clearSession, loadSession } from "./state/sessionStore";
import type { Session, SetupConfig } from "./types";

const setup = byId("setup");
const form = byId("setupForm") as HTMLFormElement;
const charsetSelect = byId("charset") as HTMLSelectElement;
const resumeBtn = byId("resumeBtn") as HTMLButtonElement;
const resumeNote = byId("resumeNote");

populateCharsets();
wireResume();

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const cfg = readConfig(new FormData(form));
  clearSession(); // 新規開始時は前回の途中セッションを破棄する。
  startWith(createSession(cfg));
});

function populateCharsets(): void {
  for (const cs of CHARSETS) {
    const opt = document.createElement("option");
    opt.value = cs.name;
    opt.textContent = `${cs.label}`;
    charsetSelect.appendChild(opt);
  }
}

function wireResume(): void {
  const saved = loadSession();
  if (!saved || saved.cursor >= saved.queue.length) {
    return;
  }
  resumeNote.hidden = false;
  resumeNote.textContent = `前回: ${saved.writerId} / ${saved.charsetName} — ${saved.samples.length} / ${saved.queue.length} 収録済み`;
  resumeBtn.hidden = false;
  resumeBtn.addEventListener("click", () => startWith(saved));
}

function readConfig(data: FormData): SetupConfig {
  const writerId = String(data.get("writerId") ?? "").trim() || "self_001";
  return {
    writerId,
    charsetName: String(data.get("charset") ?? CHARSETS[0].name),
    rounds: clampInt(Number(data.get("rounds")), 1, 500, 10),
    canvasSize: clampInt(Number(data.get("canvasSize")), 200, 1600, 800),
    penOnly: data.get("penOnly") === "on",
  };
}

function createSession(cfg: SetupConfig): Session {
  const charset = getCharset(cfg.charsetName);
  const dpr = window.devicePixelRatio || 1;
  return {
    sessionId: newId(),
    writerId: cfg.writerId,
    charsetName: cfg.charsetName,
    rounds: cfg.rounds,
    penOnly: cfg.penOnly,
    canvas: { width: cfg.canvasSize, height: cfg.canvasSize, devicePixelRatio: dpr },
    startedAt: localISO(),
    cursor: 0,
    queue: buildQueue(charset.chars, cfg.rounds),
    samples: [],
  };
}

function startWith(session: Session): void {
  setup.hidden = true;
  new App(session).start();
}

function clampInt(value: number, min: number, max: number, fallback: number): number {
  if (!Number.isFinite(value)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.round(value)));
}

function newId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function byId(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`missing element #${id}`);
  }
  return el;
}
