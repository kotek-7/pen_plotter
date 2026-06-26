import type { Session } from "../types";

const STORAGE_KEY = "handwriting-collector/session";

/** 進行中セッションを LocalStorage に保存する (DESIGN §12.3)。 */
export function saveSession(session: Session): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch (err) {
    // 容量超過などは収録を止めない。export を促す。
    console.warn("session save failed", err);
  }
}

export function loadSession(): Session | null {
  // localStorage は file:// やプライバシー設定で例外を投げることがある。
  // ここで落ちるとアプリ初期化全体が止まるため、必ず握りつぶす。
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Session;
    if (!parsed.queue || !parsed.samples) {
      return null;
    }
    return parsed;
  } catch (err) {
    console.warn("session load failed", err);
    return null;
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (err) {
    console.warn("session clear failed", err);
  }
}
