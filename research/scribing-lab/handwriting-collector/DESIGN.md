# 日本語単文字オンライン筆跡データ収集ツール 設計・仕様書

## 1. 概要

本ツールは、日本語手書き筆跡生成モデルの学習用データを収集するためのローカルWebアプリケーションである。

ユーザーに提示された日本語文字を、ペンタブレットまたはスタイラス対応デバイスで1文字ずつ書かせ、その筆跡をオンライン時系列データとして保存する。

収集対象は、スキャン画像ではなく、次のような時系列データである。

```text
x, y, t, pressure, pen_state
```

最終的には、このデータを用いて、文字ID条件付きの単文字筆跡生成モデルを学習する。

```text
char_id
+ previous_point
↓
RNN / LSTM / GRU / Transformer
↓
next dx, dy, pen_state
```

初期目標は、文章生成ではなく、単文字生成である。

```text
「あ」を指定すると、自然な「あ」の筆跡系列を複数生成できる
「日」を指定すると、自然な「日」の筆跡系列を複数生成できる
```

## 2. 背景

日本語文章筆記エンジンを作る上で、最終的には以下のような処理系が必要になる。

```text
日本語文字列
↓
文字配置
↓
単文字またはストローク生成
↓
文章全体の揺らぎ・字間・基線補正
↓
プロッタ出力
```

このうち、最初に検証すべき中核は、単文字のオンライン筆跡生成である。

日本語は英語筆記体と比べて文字間接続が弱い。そのため、最初から文章全体を連続系列として生成するよりも、まずは各文字を自然に生成できる単文字モデルを作り、その後に文字配置・字間・基線・全体癖を重ねる方が実装しやすい。

つまり、本プロジェクトの初期仮説は次である。

```text
日本語自然筆記 =
  単文字筆跡生成
  + 文字配置
  + 字間揺らぎ
  + writer style の一貫性
```

本ツールは、このうち「単文字筆跡生成」のための自前データを集めるために作る。

## 3. 動機

既存の日本語オンライン筆跡データセットには、TUAT HANDS などがある。しかし、利用申請・ライセンス・配布条件の確認が必要であり、PoC段階では導入コストが高い。

一方、単文字生成の検証だけであれば、対象文字を絞って自分で書いたデータでも十分に実験できる。

例えば、初期実験では以下程度の規模でよい。

```text
ひらがな 46字 × 50サンプル = 2,300サンプル
頻出漢字 100字 × 50サンプル = 5,000サンプル
合計 7,300サンプル
```

この規模であれば、手作業でも数日以内に収録可能である。

ただし、手動でファイル名を付けたり、文字ラベルを管理したり、ストロークを後から分割したりするのは面倒であり、ミスも起きやすい。

そこで、提示文字を見て書くだけで、以下を自動で記録する専用ツールを作る。

```text
文字ラベル
サンプル番号
筆記座標
時刻
筆圧
ストローク境界
書き直し履歴
収録順序
```

## 4. 用途

本ツールの主用途は、筆跡生成モデル用のデータ収集である。

### 4.1 主要用途

```text
日本語単文字オンライン筆跡生成モデルの学習データ作成
自分の筆跡分布の収集
ペンプロッタ用筆記エンジンの初期データ作成
ひらがな・漢字・カタカナの筆跡変動収集
RNN/LSTM/Transformer 系モデルのPoC
```

### 4.2 副次用途

```text
筆跡特徴量の分析
文字ごとの書き癖の可視化
ストローク数・筆順の統計
筆圧変化の分析
プロッタ出力用の実測軌跡テンプレート作成
```

### 4.3 対象外

初期版では以下は対象外とする。

```text
自動文字認識
筆順の自動正誤判定
美文字判定
クラウド同期
複数ユーザー管理
他人の筆跡模倣
署名模倣
スキャン画像からの筆跡抽出
```

## 5. 基本方針

### 5.1 ブラウザベースで実装する

初期版は、ローカルで動くWebアプリとして実装する。

```text
Vite
TypeScript
Canvas
Pointer Events
JSONL export
```

Electron やネイティブアプリは初期段階では不要である。

理由は、ブラウザの Pointer Events により、ペン入力の座標・筆圧・傾き・時刻を取得できるためである。

### 5.2 固定周期で直接保存しない

収録時点では、ブラウザから来た入力イベントをできるだけそのまま保存する。

```text
収録時:
  生イベント列を保存

学習前処理:
  100Hz などへリサンプリング
  x,y を dx,dy に変換
  pen_state を整形
```

固定周期に丸めたデータだけを保存すると、後から別のサンプリング周期で試したくなったときに情報が失われる。

したがって、生データを master とし、学習用データは派生物として作る。

### 5.3 1文字終了は自動判定しない

ペンアップは「一画の終了」であって、「一文字の終了」ではない。

特に漢字では、1文字が複数ストロークで構成される。

したがって、文字サンプルの確定はユーザー操作で行う。

```text
pen down:
  stroke 開始

pen up:
  stroke 終了

Space / Enter:
  この文字サンプルを確定して次へ

Backspace / R:
  書き直し
```

### 5.4 提示順はランダム化する

同じ文字を連続で大量に書くと、運動が最適化されすぎる。

悪い収録順:

```text
あ あ あ あ あ あ
い い い い い い
う う う う う う
```

良い収録順:

```text
あ 日 の 本 い 語 る 人
日 い あ 語 の 本 人 る
```

そのため、文字リストをラウンドごとにシャッフルする。

```ts
const queue = Array.from({ length: rounds }, () => shuffle(chars)).flat()
```

## 6. 想定ユーザーフロー

### 6.1 初回設定

ユーザーは最初に以下を設定する。

```text
writer_id
対象文字セット
各文字の収録回数
キャンバスサイズ
保存形式
```

例:

```json
{
  "writer_id": "self_001",
  "charset": "hiragana_basic",
  "rounds": 50,
  "canvas": {
    "width": 800,
    "height": 800
  }
}
```

### 6.2 収録開始

画面中央に現在の提示文字を表示する。

```text
現在の文字: あ
残り: 2299 / 2300
サンプル: 1 / 50
```

ユーザーはキャンバスに文字を書く。

### 6.3 書き直し

失敗したら、`Backspace` または `R` で現在のサンプルを破棄する。

```text
現在の文字だけ消す
同じ文字を再提示する
sample_id は進めない
```

### 6.4 確定

`Space` または `Enter` で現在の文字サンプルを確定する。

確定時に次を行う。

```text
空サンプルでないか検査
stroke が存在するか検査
サンプルをメモリ内 dataset に追加
次の文字を提示
```

### 6.5 保存

一定サンプルごとに自動保存用のダウンロードを促す、または手動で `S` キーにより JSONL を export する。

ブラウザだけで完結させる場合、まずはファイルダウンロードでよい。

## 7. UI仕様

### 7.1 画面構成

```text
+---------------------------------------------------+
| Writer: self_001   Progress: 123 / 2300            |
| Current char: あ                                  |
+---------------------------------------------------+
|                                                   |
|                  [ writing canvas ]               |
|                                                   |
+---------------------------------------------------+
| Space: next | Backspace: retry | U: undo | S: save |
+---------------------------------------------------+
```

### 7.2 表示項目

必須表示:

```text
現在の提示文字
全体進捗
現在文字の収録回数
キャンバス
操作ヘルプ
```

任意表示:

```text
直近の筆跡プレビュー
筆圧可視化
ストローク数
経過時間
点数
```

### 7.3 操作

| 操作        | 機能              |
| --------- | --------------- |
| ペン接触      | stroke開始        |
| ペン移動      | 点を追加            |
| ペン離し      | stroke終了        |
| Space     | サンプル確定、次へ       |
| Enter     | サンプル確定、次へ       |
| Backspace | 現在サンプルを破棄して書き直し |
| R         | 現在サンプルを破棄して書き直し |
| U         | 最後のstrokeだけ取り消し |
| S         | dataset保存       |
| P         | 一時停止            |
| Esc       | メニュー            |

## 8. データ仕様

### 8.1 生データ形式

収録時には、ストローク単位で生イベントを保存する。

```ts
type RawPoint = {
  x: number
  y: number
  t: number
  pressure: number
  tiltX?: number
  tiltY?: number
  pointerType: string
}

type RawStroke = {
  strokeIndex: number
  points: RawPoint[]
}

type RawSample = {
  version: string
  sampleId: string
  writerId: string
  char: string
  charCode: string
  charsetName: string
  promptIndex: number
  repetitionIndex: number
  createdAt: string
  canvas: {
    width: number
    height: number
    devicePixelRatio: number
  }
  strokes: RawStroke[]
}
```

### 8.2 JSONL保存例

1行1サンプルで保存する。

```jsonl
{"version":"0.1","sampleId":"self_001_000001","writerId":"self_001","char":"あ","charCode":"U+3042","charsetName":"hiragana_basic","promptIndex":0,"repetitionIndex":0,"createdAt":"2026-06-26T10:00:00.000+09:00","canvas":{"width":800,"height":800,"devicePixelRatio":2},"strokes":[{"strokeIndex":0,"points":[{"x":300.2,"y":211.4,"t":0,"pressure":0.32,"tiltX":4,"tiltY":-12,"pointerType":"pen"},{"x":302.6,"y":213.1,"t":8.2,"pressure":0.37,"tiltX":4,"tiltY":-12,"pointerType":"pen"}]}]}
```

### 8.3 charCode

`charCode` は Unicode code point 文字列とする。

例:

```text
あ → U+3042
日 → U+65E5
語 → U+8A9E
```

サロゲートペアを含む文字にも将来対応できるよう、JavaScript の `codePointAt` を使う。

### 8.4 時刻

点の `t` は、サンプル開始時刻を 0 とする相対ミリ秒とする。

```text
stroke開始時刻ではなく、文字サンプル開始時刻からの相対時刻
```

これにより、stroke間の待機時間も保持できる。

例:

```text
stroke 0:
  t = 0ms 〜 300ms

stroke 1:
  t = 520ms 〜 750ms
```

この場合、300ms〜520ms が pen-up 中の待機時間として残る。

## 9. 収録イベント仕様

### 9.1 pointerdown

条件:

```text
pointerType が pen である
または設定で mouse/touch 収録を許可している
```

処理:

```text
新しい stroke を開始
pointer capture を設定
最初の点を記録
sampleStartTime が未設定なら設定
```

### 9.2 pointermove

処理:

```text
現在 stroke が存在する場合のみ記録
getCoalescedEvents が使える場合は展開して記録
各イベントの x,y,t,pressure,tilt を保存
```

### 9.3 pointerup

処理:

```text
最後の点を記録
現在 stroke を閉じる
```

### 9.4 pointercancel

処理:

```text
現在 stroke を閉じる
警告を表示
必要ならその stroke を invalid として扱う
```

### 9.5 実装イメージ

```ts
function toPoint(e: PointerEvent, sampleStartTime: number): RawPoint {
  const rect = canvas.getBoundingClientRect()

  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
    t: e.timeStamp - sampleStartTime,
    pressure: e.pressure,
    tiltX: e.tiltX,
    tiltY: e.tiltY,
    pointerType: e.pointerType,
  }
}

function collectMove(e: PointerEvent) {
  if (!currentStroke) return

  const events = e.getCoalescedEvents?.() ?? [e]

  for (const ev of events) {
    currentStroke.points.push(toPoint(ev, sampleStartTime))
  }
}
```

## 10. 学習用前処理仕様

生データはそのまま学習に入れない。別の前処理スクリプトで学習用形式へ変換する。

### 10.1 正規化

各サンプルを文字単位で正規化する。

```text
x_min, y_min を引く
max(width, height) で割る
中心を揃える
必要なら y 軸を反転する
```

例:

```python
x = (x - x_min) / scale
y = (y - y_min) / scale
```

### 10.2 リサンプリング

生データを一定時間間隔に補間する。

初期設定:

```text
100Hz
10ms間隔
```

ただし、元データが粗い場合は無理に増やさない。

選択肢:

```text
50Hz
100Hz
200Hz
```

推奨:

```text
初期PoC: 100Hz
軽量学習: 50Hz
速度・筆圧重視: 100〜200Hz
```

### 10.3 dx, dy 変換

絶対座標を差分座標に変換する。

```python
dx[t] = x[t] - x[t - 1]
dy[t] = y[t] - y[t - 1]
```

モデルには基本的に `x,y` ではなく `dx,dy` を入力する。

理由:

```text
位置依存性を減らせる
文字の形状変化として扱いやすい
Graves / Sketch-RNN 系の形式に近い
```

### 10.4 pen_state

学習用には次の3状態を使う。

```text
pen_down
pen_up
end
```

表現:

```text
[1, 0, 0] = pen_down
[0, 1, 0] = pen_up
[0, 0, 1] = end
```

単文字データでは、ストローク内は `pen_down`、ストローク間移動は `pen_up`、最後に `end` を付ける。

### 10.5 学習用系列例

```json
{
  "char": "あ",
  "char_id": 0,
  "seq": [
    {"dx": 0.00, "dy": 0.00, "pen": [1, 0, 0]},
    {"dx": 0.01, "dy": 0.02, "pen": [1, 0, 0]},
    {"dx": 0.03, "dy": 0.01, "pen": [1, 0, 0]},
    {"dx": 0.20, "dy": -0.10, "pen": [0, 1, 0]},
    {"dx": 0.00, "dy": 0.00, "pen": [0, 0, 1]}
  ]
}
```

## 11. 文字セット仕様

### 11.1 初期文字セット

最初はひらがなから始める。

```text
あいうえお
かきくけこ
さしすせそ
たちつてと
なにぬねの
はひふへほ
まみむめも
やゆよ
らりるれろ
わをん
```

濁音・半濁音・小書き文字は第2段階で追加する。

第2段階:

```text
がぎぐげご
ざじずぜぞ
だぢづでど
ばびぶべぼ
ぱぴぷぺぽ
ゃゅょっ
```

第3段階:

```text
頻出漢字
カタカナ
数字
句読点
```

### 11.2 頻出漢字セット

初期漢字は、文章で頻出し、かつ画数が極端に多くない文字を選ぶ。

例:

```text
日 本 人 大 小 中 上 下 山 川
田 口 目 手 足 年 月 火 水 木
金 土 今 何 私 君 行 見 言 語
書 読 食 生 学 校 先 時 間
```

初期段階では100字程度に絞る。

## 12. 収録セッション仕様

### 12.1 セッション単位

1回の収録作業を session として扱う。

```ts
type Session = {
  sessionId: string
  writerId: string
  charsetName: string
  rounds: number
  startedAt: string
  completedAt?: string
  queue: PromptItem[]
  samples: RawSample[]
}
```

### 12.2 PromptItem

```ts
type PromptItem = {
  promptIndex: number
  char: string
  repetitionIndex: number
  status: "pending" | "done" | "skipped"
}
```

### 12.3 中断・再開

初期版では、セッション状態を LocalStorage に保存する。

```text
現在のキュー
収録済みサンプル
現在の promptIndex
writer_id
```

将来版では、IndexedDB を使う。

## 13. 品質管理

### 13.1 最低限のバリデーション

サンプル確定時に以下を検査する。

```text
stroke が1本以上ある
点数が一定数以上ある
bbox が小さすぎない
筆記時間が短すぎない
筆記時間が長すぎない
```

例:

```text
点数 < 5:
  無効

bbox width < 10px and bbox height < 10px:
  無効

duration < 50ms:
  無効

duration > 30s:
  確認
```

### 13.2 書き直し推奨

以下の場合は警告を出す。

```text
キャンバス外に大きくはみ出した
stroke数が極端に少ない
点数が極端に多い
筆圧が常に0
```

ただし、初期版では自動破棄しない。

### 13.3 プレビュー

確定前に現在サンプルを表示する。

表示:

```text
軌跡線
strokeごとの色分け optional
bbox
開始点・終了点 optional
```

## 14. 保存形式

### 14.1 推奨形式

初期版は JSONL を採用する。

理由:

```text
1行1サンプルで扱いやすい
途中で壊れても復旧しやすい
Python/Pandas/PyTorch前処理に読み込みやすい
git diff も比較的見やすい
```

### 14.2 ファイル名

```text
handwriting_raw_{writer_id}_{charset}_{timestamp}.jsonl
```

例:

```text
handwriting_raw_self001_hiragana_20260626_101530.jsonl
```

### 14.3 メタデータ

別途 metadata JSON を出力してもよい。

```json
{
  "dataset_version": "0.1",
  "writer_id": "self_001",
  "charset": "hiragana_basic",
  "rounds": 50,
  "created_at": "2026-06-26T10:15:30+09:00",
  "tool_version": "0.1.0",
  "device": {
    "user_agent": "...",
    "screen_width": 1920,
    "screen_height": 1080
  }
}
```

## 15. 実装構成

### 15.1 ディレクトリ構成

```text
handwriting-collector/
  package.json
  index.html
  src/
    main.ts
    app.ts
    canvas/
      CanvasInput.ts
      StrokeRenderer.ts
    data/
      charset.ts
      queue.ts
      sample.ts
      exportJsonl.ts
    state/
      sessionStore.ts
    preprocess/
      normalize.ts
      resample.ts
      toStroke3.ts
    styles.css
```

### 15.2 主要コンポーネント

```text
App
  全体状態管理

PromptPanel
  現在の提示文字と進捗表示

WritingCanvas
  Pointer Events を受け取り stroke を記録

ControlPanel
  next / retry / undo / save

DatasetExporter
  JSONL を生成して保存

SessionStore
  LocalStorage に進捗を保存
```

## 16. コア実装仕様

### 16.1 Canvas入力

```ts
canvas.addEventListener("pointerdown", onPointerDown)
canvas.addEventListener("pointermove", onPointerMove)
canvas.addEventListener("pointerup", onPointerUp)
canvas.addEventListener("pointercancel", onPointerCancel)
```

`pointerdown` 時に `setPointerCapture` を呼び、キャンバス外に少し出ても入力を取り続ける。

```ts
function onPointerDown(e: PointerEvent) {
  if (settings.penOnly && e.pointerType !== "pen") return

  canvas.setPointerCapture(e.pointerId)

  if (!sampleStartTime) {
    sampleStartTime = e.timeStamp
  }

  currentStroke = {
    strokeIndex: currentStrokes.length,
    points: [toPoint(e)],
  }

  currentStrokes.push(currentStroke)
}
```

### 16.2 moveイベント

```ts
function onPointerMove(e: PointerEvent) {
  if (!currentStroke) return

  const events = e.getCoalescedEvents?.() ?? [e]

  for (const ev of events) {
    currentStroke.points.push(toPoint(ev))
  }

  render()
}
```

### 16.3 upイベント

```ts
function onPointerUp(e: PointerEvent) {
  if (!currentStroke) return

  currentStroke.points.push(toPoint(e))
  currentStroke = null
  render()
}
```

### 16.4 確定処理

```ts
function commitSample() {
  const validation = validateSample(currentStrokes)

  if (!validation.ok) {
    showWarning(validation.message)
    return
  }

  const sample = buildSample({
    char: currentPrompt.char,
    writerId,
    strokes: currentStrokes,
  })

  session.samples.push(sample)
  currentStrokes = []
  advancePrompt()
  saveSessionToLocalStorage()
}
```

## 17. モデル学習との接続

このツールで収録したデータは、以下のモデルに接続する。

### 17.1 単文字LSTM-MDN

```text
char_id
+ previous dx, dy, pen_state
↓
LSTM
↓
MDN(dx, dy)
+ pen_state softmax
```

### 17.2 単文字Transformer Decoder

```text
char embedding
+ positional encoding
+ previous stroke tokens
↓
Transformer decoder
↓
next stroke token
```

### 17.3 将来的なWriterStyle学習

複数人で収録する場合は、writer_id を embedding として使う。

```text
char_id
+ writer_id
+ previous point
↓
trajectory generator
```

ただし、自分一人のPoCでは writer_id は定数でよい。

## 18. 最初に実装しないもの

初期版では以下をあえて実装しない。

```text
自動筆順判定
自動文字認識
複雑なデータベース
アカウント管理
クラウド保存
画像補正
機械学習モデル内蔵
リアルタイム生成プレビュー
```

理由は、データ収集の成否に直接関係しないためである。

まず必要なのは、正しくラベル付けされたオンライン筆跡データを安定して集めることである。

## 19. MVP要件

MVPとして必要な機能は以下。

```text
文字セットを指定できる
提示文字が表示される
ペンタブでキャンバスに書ける
stroke が分かれて保存される
Space で次の文字へ進める
Backspace で書き直せる
JSONL として保存できる
収録途中で中断しても復旧できる
```

MVP完了条件:

```text
ひらがな 46字 × 10回 = 460サンプルを収録できる
収録データをPythonで読み込める
各サンプルをSVG/PNGとして再描画できる
dx,dy,pen_state形式へ変換できる
```

## 20. v1要件

v1では次を追加する。

```text
文字セット編集UI
収録進捗の詳細表示
LocalStorage/IndexedDBによる自動保存
最後のstroke取り消し
サンプル一覧プレビュー
不良サンプルの削除
筆圧表示
データセット統計表示
```

統計例:

```text
文字ごとのサンプル数
平均stroke数
平均点数
平均筆記時間
bboxサイズ分布
pressure平均
```

## 21. v2要件

v2では、学習・評価との接続を強める。

```text
前処理済み stroke-3 export
PyTorch Dataset export
SVG一括出力
PNG一括出力
モデル学習用 train/valid split
文字ごとの品質チェック
筆順テンプレートとの比較 optional
```

## 22. リスクと対策

### 22.1 ブラウザや環境で筆圧が取れない

対策:

```text
pressure が常に0または0.5でも収録可能にする
pressure は optional とする
学習初期版では pressure を使わない
```

### 22.2 イベント間隔が不安定

対策:

```text
生の t を保存する
前処理でリサンプリングする
getCoalescedEvents が使える場合は利用する
```

### 22.3 同じ文字を連続して書くことで癖が偏る

対策:

```text
ラウンドごとに文字順をシャッフルする
長時間収録を避ける
複数日に分けて収録する
```

### 22.4 疲労で後半の筆跡が変わる

これは欠点でもあり、実際の文章筆記らしい変化でもある。

対策:

```text
session_id と時刻を保存する
収録順序を保存する
後で分析できるようにする
```

### 22.5 文字サンプルの品質がばらつく

対策:

```text
プレビュー表示
書き直し機能
bbox/点数/duration の簡易チェック
```

## 23. 開発ロードマップ

### Phase 0: 技術検証

```text
Canvas にペンで線が描ける
x,y,t,pressure が取れる
stroke に分割できる
JSONとして保存できる
```

### Phase 1: MVP

```text
文字キュー
提示文字
Spaceで次へ
Backspaceで書き直し
JSONL export
LocalStorage復旧
```

### Phase 2: 前処理

```text
JSONL読込
正規化
リサンプリング
dx,dy変換
pen_state付与
SVG/PNG再描画
```

### Phase 3: 学習接続

```text
PyTorch Dataset
LSTM-MDN baseline
単文字生成
SVGレンダリング
```

### Phase 4: データ品質改善

```text
統計画面
不良サンプル除去
筆圧分析
サンプル一覧
文字ごとの進捗管理
```

## 24. 推奨する最初の実験

最初は以下でよい。

```text
対象:
  ひらがな 46字

回数:
  各10回

合計:
  460サンプル

目的:
  収録ツールと前処理の検証
```

次に、

```text
ひらがな 46字 × 50回 = 2,300サンプル
```

へ増やす。

漢字はその後でよい。

```text
頻出漢字 50字 × 30回 = 1,500サンプル
```

この段階で、単文字生成モデルのPoCには十分なデータになる。

## 25. 結論

本ツールの本質は、単なるお絵描きアプリではない。

目的は、機械学習で扱える形の日本語オンライン筆跡データを、自前で効率よく、正確なラベル付きで収録することである。

最重要要件は以下である。

```text
提示文字と筆跡系列が正しく対応している
stroke境界が保持されている
時刻情報が保持されている
生データが失われない
後から任意の学習形式に変換できる
```

したがって、初期版では美しいUIよりも、データの完全性・再現性・前処理しやすさを優先する。

最終的には、このツールで収録したデータを使って、

```text
char_id
→ 自然な日本語単文字オンライン筆跡系列
```

を生成するモデルを学習し、その後に文字配置・字間・文章コンテクストを追加して、日本語文章筆記エンジンへ拡張する。
