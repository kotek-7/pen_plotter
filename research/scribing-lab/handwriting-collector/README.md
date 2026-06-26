# handwriting-collector

日本語単文字オンライン筆跡データ収集ツール (MVP)。ペンタブ/スタイラスで提示文字を 1 文字ずつ書き、
`x, y, t, pressure, pen_state` のオンライン時系列を JSONL として収録する。

設計の正本は [DESIGN.md](DESIGN.md)。本 README は使い方の要約。

## セットアップ

```sh
cd research/scribing-lab/handwriting-collector
npm install
npm run dev      # http://127.0.0.1:5180/
```

ビルド / 型チェック:

```sh
npm run build      # tsc --noEmit + vite build → dist/
npm run typecheck
```

## 使い方

1. 開始画面で writer ID・文字セット・収録回数 (rounds)・キャンバスサイズ・ペン入力のみ収録、を設定して開始する。
2. 中央に提示された文字をキャンバスに書く。
3. キー操作:

| キー | 機能 |
| --- | --- |
| `Space` / `Enter` | 現在サンプルを確定して次へ |
| `Backspace` / `R` | 現在サンプルを破棄して書き直し |
| `Ctrl`+`Z` / `Cmd`+`Z` / `U` | 直前の stroke だけ取り消し |
| `S` | これまでの dataset を JSONL + metadata で保存 |
| `P` | 一時停止 / 再開 |
| `Esc` | 進捗を保存してメニューへ戻る |

- 提示順はラウンドごとにシャッフルされる (同じ文字の連続を避ける)。
- 確定時に最低限のバリデーション (点数・bbox・筆記時間) を行い、不正なら確定をブロックする。
- 進捗は LocalStorage に自動保存され、中断後は開始画面の「前回の続きから再開」で復旧できる。
- 完了時に自動で JSONL + metadata がダウンロードされる。

## 出力形式

1 行 1 サンプルの JSONL (`RawSample`)。詳細は DESIGN.md §8。座標は canvas の CSS ピクセル、
`t` はサンプル開始からの相対ミリ秒、stroke 境界を保持する。

ファイル名: `handwriting_raw_{writer}_{charset}_{timestamp}.jsonl`

## 学習用前処理 (TS ユーティリティ)

`src/preprocess/` に生データ→学習形式の純関数を用意している (DESIGN.md §10)。

- `normalize.ts`: 文字単位の bbox 正規化 (`max(w,h)` で割る、y 反転オプション)
- `resample.ts`: stroke 内を Hz 指定で線形リサンプリング (stroke 境界は跨がない)
- `toStroke3.ts`: 正規化 → `dx,dy` 差分 → `pen_state` one-hot `[down, up, end]`

## スコープ

本実装は DESIGN.md の MVP (§19) を対象とする。文字セット編集 UI・サンプル一覧・統計画面・
IndexedDB・PyTorch/SVG 一括出力などは v1/v2 (§20, §21) の範囲で未実装。
