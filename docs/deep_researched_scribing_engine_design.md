以下は、 deep research による日本語文章筆記エンジンの調査結果をコンテクストに含む LLM によって出力された、開発中に deep research の調査結果リソースを活用するための技術調査・設計案ドキュメントである。

# 日本語文章筆記エンジン 技術調査・設計ドキュメント

## 0. 要旨

日本語文章をペンプロッタで自然に筆記するには、単にフォント輪郭を崩すのではなく、**文章全体の一貫した筆跡スタイル、文字間隔、行基線、文字ごとの崩れ、ストローク順序、運筆速度を階層的に生成する必要がある**。

本設計では、最終出力を画像ではなく、

```text
x, y, t, pen_state, pressure_optional
```

からなる **オンライン筆跡系列** として扱う。

採用方針は次の通り。

```text
Japanese Text
  ↓
Text / Line Layout Planner
  ↓
Character Planner
  ↓
Stroke Planner
  ↓
Context Field
  ↓
Trajectory Generator
  ↓
Kinematic / Plotter Post Processor
  ↓
SVG / G-code / HPGL
```

特に重要なのは、`Trajectory Generator` に直接文字だけを渡すのではなく、事前に **文章文脈に基づく StrokeCondition** を作ることである。

```text
StrokeTemplate
+ WriterProfile
+ SentenceContext
+ CharContext
+ NeighborTransition
→ StrokeCondition
→ Trajectory
```

この方向性は、文章レベルのオンライン手書き生成で **文字間接続・spacing・文脈依存字形** を明示的に扱う CASHG の問題設定に近い。CASHG は sentence-level online handwriting で、文レベル生成には context-dependent characters、stroke continuity、spacing が必要だとし、Character Context Encoder と bigram-aware sliding-window Transformer decoder を用いる。([arXiv][1])

---

## 1. 問題設定

### 1.1 目的

目的は、日本語文字列から、ペンプロッタで描画可能な自然な筆跡を生成することである。

対象は次を含む。

```text
ひらがな
カタカナ
漢字
英数字
句読点
記号
横書き文章
将来的には縦書き
```

最終的に必要な出力は、単なる SVG パスではなく、少なくとも以下を含むべきである。

```json
{
  "x": 12.3,
  "y": 45.6,
  "t": 0.734,
  "pen": "down"
}
```

可能なら次も含める。

```json
{
  "pressure": 0.72,
  "tilt_x": 0.1,
  "tilt_y": -0.2,
  "velocity": 48.0
}
```

ただし、多くのペンプロッタは筆圧や傾きを物理的に制御できないため、初期実装では `x, y, t, pen_state` を主対象にする。

---

## 2. なぜフォント変形では不十分か

フォントベース方式は次のような処理になる。

```text
文字列
↓
フォントアウトライン
↓
輪郭抽出
↓
ランダム変形
↓
プロット
```

これは「手書き風の形」は作れるが、「人が書いた運動」にはならない。

不自然さの原因は主に次である。

```text
書き順がない
筆画単位ではなく輪郭単位である
速度変化がない
文字間接続がない
文章全体の癖がない
同じノイズが局所的すぎる
```

日本語、特に漢字では筆画と筆順が字形理解に直結する。KanjiVG は各漢字について、ストロークの形状、方向、筆順、部品、部首、ストローク種別を SVG として提供しており、これは「アウトライン」ではなく「筆画構造」を得るための実用的な基礎データになる。([KanjiVG][2])

---

## 3. 先行研究マップ

### 3.1 系統分類

| 系統                      | 代表例                          | 生成対象                     | 本プロジェクトでの位置付け          |
| ----------------------- | ---------------------------- | ------------------------ | ---------------------- |
| RNN/MDN 系               | Graves 2013                  | オンライン筆跡点列                | 基準実装として重要              |
| Style/Content 分離        | DeepWriting                  | digital ink              | WriterStyle 設計の参考      |
| Sentence-level online   | CASHG                        | 文レベルオンライン筆跡              | 本命設計の直接参考              |
| Latent diffusion        | DiffInk                      | full-line pen trajectory | v2 以降の候補               |
| Layout/Glyph 分離         | Decoupling Layout from Glyph | 中国語行レベル online           | 日本語行レイアウト設計の参考         |
| VAE短期生成                 | DeepWriteSYN                 | 短時間筆跡セグメント               | stroke variation 生成に有用 |
| Kinematic model         | Sigma-Lognormal              | 運動速度・軌跡                  | Post Processor に採用候補   |
| Offline GAN/Transformer | ScrabbleGAN, GANwriting, HWT | 画像                       | 直接採用は低優先               |
| 文字構造DB                  | KanjiVG                      | 筆順・筆画                    | 初期実装で採用                |
| 日本語オンラインDB              | TUAT HANDS                   | 日本語時系列筆跡                 | 学習データ候補                |

---

## 4. 主要先行研究

### 4.1 Graves 2013: RNN + MDN + Attention

Alex Graves の “Generating Sequences With Recurrent Neural Networks” は、オンライン手書き生成の古典的基準である。LSTM が `Δx, Δy, pen_state` を逐次生成し、テキスト条件付きの手書き合成では入力文字列への attention を使う。論文はオンライン手書きを実数値系列として扱い、RNN が一点ずつ予測する方式で高品質な筆記体を生成できることを示した。([arXiv][3])

この方式の利点は明確である。

```text
x,y の時系列を直接生成できる
SVG/G-code へ変換しやすい
実装例が多い
```

一方、日本語文章筆記には弱点がある。

```text
長い文章で局所崩れが蓄積しやすい
漢字の筆画構造を明示的に持たない
文字間 spacing や接続が暗黙的
筆順辞書との統合が必要
```

実装リソースとしては `sjvasquez/handwriting-synthesis` が Graves 論文の TensorFlow 実装で、README でも原論文の手書き合成実験を実装し、生成サンプル品質が論文に近いと説明している。([GitHub][4]) また `X-rayLaser/pytorch-handwriting-synthesis-toolkit` は PyTorch 実装で、LSTM、attention、mixture-density-networks、text-to-handwriting をトピックとして持つ。([GitHub][5])

**本プロジェクトでの扱い**
Graves 型は PoC の比較対象・基準実装として使う。ただし最終設計の中核にはしない。理由は、日本語文章では「文字構造」「行レイアウト」「文字間接続」を明示的に制御したいからである。

---

### 4.2 DeepWriting: Style / Content 分離

DeepWriting は digital ink を対象に、content と style を分離して、任意テキストを特定スタイルで合成・編集できる生成モデルを提案している。論文は、手書き認識ではデジタル表現へ変換する際に個人の見た目が失われるという問題を挙げ、style transfer、単語レベル編集、スペル修正などの用途を示している。([arXiv][6])

この考え方は非常に重要である。

筆記エンジン内部では、少なくとも次を分離する必要がある。

```text
content: 何を書くか
style: 誰のような筆跡傾向か
layout: どこに配置するか
trajectory: どう動いて書くか
```

**本プロジェクトでの扱い**
DeepWriting の直接再実装ではなく、`WriterProfile` / `WriterEmbedding` の設計思想として採用する。

```json
{
  "writer_profile": {
    "slant": 0.08,
    "roundness": 0.42,
    "kanji_density": 0.73,
    "kana_size_ratio": 0.82,
    "spacing_mean": 1.05,
    "stroke_end_sharpness": 0.36
  }
}
```

---

### 4.3 CASHG: Context-Aware Stylized Online Handwriting Generation

CASHG は、現在の設計に最も近い研究である。問題設定は **sentence-level online handwriting** であり、自然な文レベル筆跡には context-dependent characters、stroke continuity、spacing が必要だと明示している。構造としては Character Context Encoder、bigram-aware sliding-window Transformer decoder、gated context fusion を用い、前文字から現文字への局所遷移を重視する。([arXiv][1])

これは本プロジェクトで言う次の部分に対応する。

```text
Context Field
+ NeighborTransition
+ StrokeCondition
```

CASHG の重要な示唆は、文レベル自然性を RNN の隠れ状態に丸投げしない点である。

```text
悪い設計:
文字 → 点列

良い設計:
文字 + 前後文字 + 文脈 + spacing + writer style → 点列
```

**本プロジェクトでの扱い**
文章筆記エンジンの中核方針として採用する。完全な CASHG 実装ではなく、日本語用に次のように翻案する。

```text
Character Context Encoder
→ 日本語文字種、前後文字、行内位置、筆画密度を埋め込む

Bigram-aware transition
→ 前文字終端と現文字開始の間隔・浮筆移動を生成

StrokeCondition
→ 各ストロークに文脈条件を付与
```

---

### 4.4 DiffInk: Full-line latent diffusion

DiffInk は、text-to-online handwriting generation において full-line handwriting generation を目的とする latent diffusion Transformer である。InkVAE によりオンライン筆跡を潜在空間に圧縮し、OCR-based loss による glyph accuracy、style-classification loss による style fidelity を導入し、その潜在空間上で InkDiT が target text と reference style から coherent pen trajectories を生成する。([arXiv][7])

この研究は非常に強力だが、初期実装としては重い。

利点:

```text
行全体の一貫性を扱いやすい
style reference から筆跡を条件付けられる
full-line trajectory を直接生成する
```

欠点:

```text
学習データ要求が大きい
モデルが複雑
日本語漢字の筆順制約を入れるには追加設計が必要
デバッグが難しい
```

**本プロジェクトでの扱い**
v2 以降の候補。初期実装では採用せず、まずは CASHG 型の階層条件付き生成を作る。

---

### 4.5 Decoupling Layout from Glyph in Online Chinese Handwriting Generation

この研究は、中国語の online handwriting generation において、テキスト行を **layout** と **glyph** に分ける設計を取る。Layout generator が各 glyph の位置を自己回帰的に生成し、1D U-Net ベースの diffusion denoiser を含む stylized font synthesizer がスタイル付き文字を生成する。CASIA-OLHWDB 上で構造的に正しく識別困難な imitation samples を生成できると報告している。([arXiv][8])

日本語にも強く転用可能である。

```text
文章レベル自然性 = layout
各文字の自然性 = glyph / stroke
```

と分離すると、次の問題を扱いやすい。

```text
漢字とかなのサイズ差
文字間隔
行末の詰まり
基線ドリフト
文字ごとの傾き
```

**本プロジェクトでの扱い**
`LineLayoutPlanner` と `CharacterPlanner` の分離設計として採用する。

---

### 4.6 DeepWriteSYN

DeepWriteSYN は、online handwriting を短時間セグメントに分割し、sequence-to-sequence VAE で合成する。セグメントは文字の一部から文字全体まで設定でき、人口全体の自然変動や特定被験者の自然変動を生成できるとされる。([arXiv][9])

これは日本語の「ストローク変動生成」に使いやすい。

```text
標準ストローク
↓
自然変動サンプラ
↓
少し違うストローク
```

**本プロジェクトでの扱い**
初期実装では直接採用しないが、`StrokeVariationModel` の候補として残す。

---

### 4.7 Sigma-Lognormal / Kinematic Theory

Sigma-Lognormal は、人間の運動を lognormal な速度プロファイルの重ね合わせとして扱う運動学モデルである。3D on-air signatures の合成研究では、lognormality principle が指先運動の神経運動制御過程を模倣すると説明され、軌跡と速度、既知軌跡からの運動情報、実署名の duplicate samples の合成に利用されている。([arXiv][10])

さらに、Kinematic Theory は 2D spatiotemporal trajectories を virtual target points 間の曲線と速度プリミティブで表す枠組みとして説明されている。([arXiv][11])

**本プロジェクトでの扱い**
Trajectory Generator そのものを Sigma-Lognormal だけで構成するのは、日本語文章全体には硬い。だが、生成後の `Kinematic Post Processor` として非常に有効。

```text
Transformer/Diffusion が幾何軌跡を生成
↓
Sigma-Lognormal が速度・時間割り当てを補正
↓
Plotter profile が物理制約を反映
```

採用理由:

```text
人間の速度変化を明示できる
プロッタの速度制御に接続できる
ストローク終端の減速や払いを表現しやすい
学習モデルの後処理として扱いやすい
```

---

## 5. 画像生成系研究の扱い

### 5.1 ScrabbleGAN

ScrabbleGAN は、可変長の手書きテキスト画像を生成する GAN 系研究で、任意長単語やスタイル操作を扱う。([arXiv][12])

**本プロジェクトでは直接採用しない。**
理由は、出力が画像であり、ペンプロッタに必要な筆順・時間・pen-up が得られないため。

ただし、次には使える。

```text
画像として自然かどうかの discriminator 参考
合成画像データ拡張
offline 評価器
```

---

### 5.2 GANwriting

GANwriting は、style features と textual content を条件に、任意語彙の手書き単語画像を生成する few-shot style imitation 系研究である。([arXiv][13])

**本プロジェクトでは直接採用しない。**

理由:

```text
画像出力でありオンライン軌跡ではない
日本語漢字の筆順を扱わない
プロッタ制御に戻すにはベクトル化が必要
```

一方、style/content の損失設計は参考になる。

---

### 5.3 Handwriting Transformers

HWT は Transformer ベースの styled handwritten text image generation であり、style examples の長距離・短距離関係を self-attention で捉え、style-content entanglement を扱う。任意長テキストや few-shot style に対応するとされる。([arXiv][14])

**本プロジェクトでの扱い**
画像生成としては不採用。ただし、style reference encoder の考え方は `WriterProfileEncoder` に転用可能。

---

### 5.4 CalliGAN

CalliGAN は中国書道文字生成で、style と structure を意識した Chinese calligraphy character generator である。漢字の component information をモデルに取り込む点が重要である。([arXiv][15])

**本プロジェクトでの扱い**
筆順・運筆出力ではないため直接採用しない。ただし、漢字を単一画像として扱うのではなく、構造・部品情報を条件にする設計は採用する。

---

## 6. データセット・リソース調査

### 6.1 TUAT HANDS-kuchibue

TUAT Nakagawa Lab. HANDS-kuchibue_d-97-06 は、東京農工大中川研究室が収集したオンライン手書きデータベースであり、120人の筆者が日本語新聞から抜粋された共通サンプルテキストを書いたデータを含む。漢字、かな、英数字、記号を含み、各筆者セットには 3,356 文字カテゴリに対する 11,962 パターンが含まれる。([東京農工大学][16])

**本プロジェクトでの価値**

```text
日本語オンライン筆跡である
文脈中の文字を含む
writer 単位の癖推定に使える
かな・漢字混在を扱える
```

**注意**

```text
利用申請が必要
マニュアルは日本語中心
商用利用条件は要確認
```

---

### 6.2 TUAT HANDS-nakayosi

TUAT Nakagawa Lab. HANDS-nakayosi_t-98-09 は、163人の筆者によるオンライン手書き日本語データベースで、新聞由来の共通サンプルテキストを対象とする。各筆者セットには 4,438 文字カテゴリに対する 10,403 パターンがあり、JIS第1水準漢字、約1,000字のJIS第2水準漢字、ひらがな、カタカナ、英数字、記号を含む。([東京農工大学][17])

**本プロジェクトでの価値**

```text
日本語文字カテゴリが広い
writer_id による筆跡スタイル学習が可能
漢字の字形変動を学習できる
```

**優先度**

`kuchibue` と `nakayosi` は最優先候補。特に日本語文章筆記エンジンでは、ETL のような画像DBより価値が高い。

---

### 6.3 ETL Character Database

ETL Character Database は、約120万件の手書き・印刷文字画像を含む日本語文字データベースで、英数字、記号、ひらがな、カタカナ、教育漢字、JIS第1水準漢字などを含む。AIST の前身である電子技術総合研究所が 1973〜1984 年に収集したもので、ETL1〜ETL9 に分かれる。([etlcdb -][18])

ETL8 は 956カテゴリ、ETL9 は 3,036カテゴリの手書き漢字・ひらがなを含み、ETL9 は 4,000人、607,200サンプルという大規模な画像データである。([etlcdb -][18])

**本プロジェクトでの価値**

```text
日本語手書き字形の画像分布を学べる
OCR/認識器の学習に使える
字形自然性評価器に使える
```

**制約**

```text
オンライン筆跡ではない
筆順・速度・pen-up がない
Trajectory Generator の直接学習には不向き
```

**使い方**

```text
字形評価器
日本語文字認識器
レンダリング後の自然性評価
offline-to-online 補助研究
```

---

### 6.4 KanjiVG

KanjiVG は、日本語漢字について、SVG 形式でストローク形状、方向、筆順、部品、部首、ストローク種別を提供する。ライセンスは Creative Commons Attribution-Share Alike 3.0 と記載されている。([KanjiVG][2])

**本プロジェクトでの価値**

```text
漢字の標準筆順を得られる
StrokeTemplate の初期値にできる
部品構造を CharacterPlanner に渡せる
学習データが不足する文字の fallback になる
```

**制約**

```text
手書き実測データではない
標準字形に寄る
ひらがな・カタカナ対応は別途必要
```

**採用**

初期実装で採用する。

---

### 6.5 IAM-OnDB

IAM On-Line Handwriting Database は英語のオンライン手書き文データベースで、ホワイトボード上で取得された手書き英語テキストを XML 形式で保持し、writer-id、transcription、記録設定を含む。221人の筆者、1,700以上のフォーム、13,049のラベル付きテキスト行、86,272語インスタンスを含む。([FKi Research Group][19])

**本プロジェクトでの価値**

```text
英語オンライン手書き生成の標準データ
Graves 系実装の検証に使える
行レベル処理・writer style 学習の参考になる
```

**制約**

```text
日本語ではない
漢字筆画構造がない
かな漢字混在の spacing には使えない
```

---

### 6.6 CASIA-OLHWDB / CASIA-HWDB

CASIA-OLHWDB はオンライン中国語手書きデータベースとして多くの研究で使われる。たとえば CASIA-OLHWDB1.0 は 3,866 クラス、420人の writer を含むと報告されている。([arXiv][20])

中国語と日本語は完全には同じでないが、漢字系文字の stroke 構造・文字密度・writer variation という点では参考になる。

**本プロジェクトでの価値**

```text
漢字系オンライン筆跡の大規模データ
Diffusion/Transformer 系の事前学習候補
漢字筆画密度の高い文字に有用
```

**制約**

```text
日本語固有のかな混在がない
字形差・簡体字/繁体字/日本字体差に注意
```

---

### 6.7 Quick, Draw!

Quick, Draw! Dataset は 345カテゴリ、5,000万件規模の drawing データで、timestamped vectors として保存される。([GitHub][21]) Sketch-RNN 用の前処理済み `.npz` データも提供され、各例は `Δx, Δy, pen-up` を含む stroke-3/5 系形式で扱われる。([GitHub][21])

**本プロジェクトでの価値**

```text
大規模なベクタ手描きデータ
ストローク生成の一般事前学習
ノイズ・低周波揺らぎの統計分析
```

**制約**

```text
文字ではなく落書き
日本語筆記構造には直接使えない
```

---

### 6.8 Kuzushiji 系データ

Kuzushiji-MNIST、Kuzushiji-49、Kuzushiji-Kanji は古典日本語崩し字の認識ベンチマークとして導入された。論文は、Kuzushiji が現代日本人の多くに読めない前近代日本語の筆記体系であり、機械学習ベンチマークとしてこれらのデータセットを提案している。([arXiv][22])

**本プロジェクトでの扱い**

現代日本語筆記エンジンには直接不要。ただし、崩し字風・行書風・歴史文書風を扱う将来拡張では有用。

---

## 7. 採用アーキテクチャ

### 7.1 全体構成

```text
InputText
  ↓
TextNormalizer
  ↓
LineLayoutPlanner
  ↓
CharacterPlanner
  ↓
StrokePlanner
  ↓
ContextFieldGenerator
  ↓
StrokeConditionBuilder
  ↓
TrajectoryGenerator
  ↓
KinematicPostProcessor
  ↓
PlotterBackend
```

---

## 8. モジュール仕様

### 8.1 TextNormalizer

役割:

```text
Unicode正規化
全角/半角処理
禁則処理
句読点処理
対応不能文字の fallback
```

出力:

```json
{
  "chars": [
    {"char": "今", "type": "kanji"},
    {"char": "日", "type": "kanji"},
    {"char": "は", "type": "hiragana"}
  ]
}
```

初期実装では、正規化は最小限でよい。

---

### 8.2 LineLayoutPlanner

役割は、文章全体の配置を決めること。

```text
行分割
文字枠位置
基線
文字間隔
行内ドリフト
行末詰まり
```

出力例:

```json
{
  "line_id": 0,
  "baseline": {
    "type": "low_frequency_curve",
    "amplitude_mm": 0.6
  },
  "chars": [
    {
      "char": "今",
      "char_index": 0,
      "box": {"x": 0.0, "y": 0.2, "w": 8.5, "h": 9.2},
      "scale": 1.02,
      "slant": 0.03
    }
  ]
}
```

文章自然性ではここが非常に重要である。Decoupling Layout from Glyph のように、行レベル生成では layout と glyph を分離する方が、各文字生成と全体配置を独立に改善できる。([arXiv][8])

---

### 8.3 CharacterPlanner

役割:

```text
文字種判定
漢字/かな/記号別の生成方針選択
文字密度推定
部品構造取得
```

漢字の場合:

```text
KanjiVG から標準ストローク列を取得
文字の構成要素を取得
筆順を取得
```

KanjiVG は各漢字の stroke order と stroke type を提供するため、StrokePlanner の初期テンプレートとして使える。([KanjiVG][2])

---

### 8.4 StrokePlanner

役割:

```text
文字を stroke template 群へ変換
各 stroke の種別・始点・終点・曲率を定義
writer style による大域変形を適用
```

内部表現:

```json
{
  "char": "木",
  "strokes": [
    {
      "stroke_index": 0,
      "stroke_type": "horizontal",
      "skeleton": [[0.15, 0.30], [0.85, 0.28]],
      "order": 0
    },
    {
      "stroke_index": 1,
      "stroke_type": "vertical",
      "skeleton": [[0.50, 0.10], [0.48, 0.88]],
      "order": 1
    }
  ]
}
```

この段階ではまだ自然な運筆ではなく、筆画の「意図」を作るだけでよい。

---

### 8.5 ContextFieldGenerator

役割は、文章全体に一貫してかかる癖を生成すること。

```text
基線ドリフト
文字サイズ揺らぎ
字間揺らぎ
傾き揺らぎ
疲労による後半変化
漢字/かなサイズ比
```

ここは独立乱数ではなく、低周波場として生成する。

```python
scale_i = writer.scale_mean + low_freq_noise(i)
slant_i = writer.slant_mean + low_freq_noise(i)
baseline_x = low_freq_noise(x)
spacing_i = writer.spacing_mean + low_freq_noise(i)
```

重要なのは、文字ごとにランダムに崩すのではなく、文章全体で連続した癖を持たせることである。

---

### 8.6 StrokeConditionBuilder

Trajectory Generator に渡す条件を作る。

```json
{
  "char": "日",
  "char_type": "kanji",
  "char_index": 1,
  "stroke_index": 2,
  "stroke_type": "vertical",
  "prev_char": "今",
  "next_char": "は",
  "line_position": 0.12,
  "writer_id": "synthetic_writer_003",
  "writer_style": {
    "slant": 0.04,
    "roundness": 0.31,
    "spacing": 1.08
  },
  "layout": {
    "box_x": 8.4,
    "box_y": 0.1,
    "box_w": 8.1,
    "box_h": 8.8,
    "baseline_offset": 0.2
  },
  "context": {
    "char_scale": 0.97,
    "stroke_length_gain": 0.94,
    "curvature_gain": 1.06,
    "terminal_style": "soft_tome"
  },
  "transition": {
    "prev_pen_end": [7.8, 6.2],
    "entry_target": [8.6, 1.1],
    "air_move_style": "short_arc"
  }
}
```

CASHG が predecessor-current transition と spacing を重視するのと同様、本設計でも `transition` を明示的に渡す。([arXiv][1])

---

## 9. Trajectory Generator 設計

### 9.1 入出力

入力:

```text
StrokeCondition
```

出力:

```text
[(x, y, t, pen_state, optional_pressure)]
```

内部的には `x,y` ではなく、次を生成する方が安定する。

```text
Δx, Δy, Δt, pen_state
```

Graves 型や Sketch-RNN 系でも、ストロークは座標差分と pen 状態で扱われる。Sketch-RNN の実装説明では、各例は `Δx, Δy` と pen lifted binary を持つ stroke-3 形式として説明されている。([GitHub][23])

---

### 9.2 最小構成

初期実装では、完全学習モデルよりも hybrid 方式がよい。

```text
StrokeTemplate
↓
幾何変形
↓
低周波ノイズ
↓
速度プロファイル付与
↓
pen-up移動付与
```

疑似コード:

```python
def generate_stroke(condition):
    path = load_template(condition.stroke_type)

    path = fit_to_skeleton(path, condition.skeleton)
    path = apply_writer_style(path, condition.writer_style)
    path = apply_context_deformation(path, condition.context)
    path = add_low_frequency_noise(path, condition.noise_field)

    timed_path = assign_velocity_profile(
        path,
        stroke_type=condition.stroke_type,
        terminal_style=condition.context["terminal_style"]
    )

    return timed_path
```

---

### 9.3 学習モデル構成

MVP 以降は次のようにする。

```text
Condition Encoder
  - char embedding
  - stroke_type embedding
  - writer embedding
  - context embedding
  - neighbor transition embedding

Trajectory Decoder
  - Transformer Decoder or GRU/LSTM
  - output distribution over Δx, Δy, Δt, pen_state
```

出力分布:

```text
Mixture of Gaussians for Δx, Δy
Categorical for pen_state
Log-normal or positive distribution for Δt
```

Graves 2013 は MDN による連続座標分布と RNN による逐次生成を使うため、この設計の基礎として使える。([arXiv][3])

---

### 9.4 Diffusion 版

v2 では、各 stroke あるいは full-line latent を diffusion で生成する。

候補:

```text
Stroke-level diffusion
Line-level latent diffusion
```

DiffInk は full-line handwriting generation を latent diffusion Transformer で扱い、InkVAE でオンライン筆跡を潜在化し、OCR loss と style-classification loss を使って字形正確性とスタイル保持を両立させている。([arXiv][7])

ただし、初期実装では diffusion は過剰である。

理由:

```text
大量データが必要
日本語筆順制約を入れる必要がある
失敗時の原因分析が難しい
```

---

## 10. Kinematic Post Processor

Trajectory Generator が出した点列に対し、人間らしい速度とプロッタ制約を付ける。

### 10.1 役割

```text
速度制限
加速度制限
コーナー減速
払い・止めの時間割り当て
pen-up 移動の速度
プロッタ固有の遅延補正
```

### 10.2 Sigma-Lognormal の使用

各 stroke を virtual target 間の運動として扱い、速度を lognormal profile に近づける。

```text
開始: 低速
中間: 加速
終端: 減速
止め: 停止時間
払い: 終端速度を残す
```

Sigma-Lognormal 系の研究は、人間の運動や署名合成で軌跡と速度を扱い、synthetic signatures や air writing にも適用されている。([arXiv][10])

---

## 11. Plotter Backend

### 11.1 出力形式

最低限対応:

```text
SVG path
```

次に対応:

```text
G-code
HPGL
AxiDraw SVG
```

### 11.2 重要な設計

プロッタでは「見た目のパス」だけでなく、速度が重要。

```gcode
G1 X10.0 Y20.0 F1200
G1 X11.0 Y20.2 F900
G1 X11.4 Y20.6 F600
```

曲がる部分、止め、払いで `F` を変える。

### 11.3 pen-up

人間の筆記では、pen-up 中の移動も次の文字の自然性に影響する。

```text
stroke end
↓
air move
↓
next stroke begin
```

プロッタでは実際に紙に描かれないが、時間・開始方向・次の stroke の入りに影響するため、内部モデルには保持する。

---

## 12. 採用技術と採否理由

### 12.1 採用

| 技術                             | 採用理由                                            |
| ------------------------------ | ----------------------------------------------- |
| KanjiVG                        | 漢字の筆順・筆画・部品構造を初期テンプレート化できるため。([KanjiVG][2])     |
| TUAT HANDS                     | 日本語オンライン筆跡で、writer ごとの文脈中文字を持つため。([東京農工大学][16]) |
| CASHG 型 context-aware 生成       | 文レベル自然性に必要な接続・spacing を明示できるため。([arXiv][1])     |
| DeepWriting 的 style/content 分離 | WriterProfile を設計する理論的根拠になるため。([arXiv][6])      |
| Sigma-Lognormal 後処理            | 速度・運動らしさを制御でき、プロッタ速度制御に接続できるため。([arXiv][10])    |
| ETL                            | オフライン字形評価器・認識器の学習に使えるため。([etlcdb -][18])        |

---

### 12.2 条件付き採用

| 技術                         | 採用条件                                                 |
| -------------------------- | ---------------------------------------------------- |
| Graves 型 RNN/MDN           | 英文・簡易筆記の baseline として使う。日本語中核にはしない。([arXiv][3])      |
| DiffInk 型 latent diffusion | データ・計算資源が揃った v2 で検討。([arXiv][7])                     |
| Sketch-RNN                 | ストロークVAE・stroke形式の参考にする。日本語文章には直接使わない。([GitHub][23]) |
| DeepWriteSYN               | stroke variation module として検討。([arXiv][9])           |
| CASIA-OLHWDB               | 漢字系事前学習に使えるが、日本語固有性に注意。([arXiv][20])                 |

---

### 12.3 不採用または低優先

| 技術                | 理由                                                         |
| ----------------- | ---------------------------------------------------------- |
| ScrabbleGAN       | 画像生成であり、オンライン軌跡が得られない。([arXiv][12])                        |
| GANwriting        | 画像ベースで、筆順・時間・pen-up が得られない。([arXiv][13])                   |
| HWT               | 高品質な画像生成には有用だが、プロッタ出力には再ベクトル化が必要。([arXiv][14])             |
| CalliGAN          | 漢字構造条件付けは参考になるが、書道画像生成であり通常筆記・オンライン軌跡とは目的が違う。([arXiv][15]) |
| Quick, Draw! 直接学習 | 大規模だが文字ではなく doodle。補助データに限定。([GitHub][21])                 |

---

## 13. 実装ロードマップ

### Phase 0: ルールベース PoC

目的:

```text
日本語文字列 → 筆順付き SVG/G-code
```

実装:

```text
KanjiVG parser
ひらがな・カタカナ簡易テンプレート
文字枠配置
低周波ノイズ
速度プロファイル
```

成果物:

```text
「今日はいい天気です」をプロッタで描ける
文字ごとに微妙な差がある
ただしまだ機械的
```

---

### Phase 1: Context Field 導入

目的:

```text
文章全体に一貫した癖を持たせる
```

実装:

```text
WriterProfile
ContextField
文字サイズ揺らぎ
字間揺らぎ
行基線ドリフト
漢字/かなサイズ比
```

期待効果:

```text
文字単体の寄せ集め感が減る
文章としての筆跡になる
```

---

### Phase 2: Online データ学習

目的:

```text
実測筆跡から stroke variation を学ぶ
```

データ:

```text
TUAT HANDS-kuchibue
TUAT HANDS-nakayosi
必要に応じて IAM-OnDB, CASIA
```

モデル:

```text
Condition Encoder
Trajectory Decoder
MDN or Transformer
```

損失:

```text
座標誤差
pen_state CE
速度プロファイル誤差
stroke length 誤差
文字認識損失 optional
```

---

### Phase 3: CASHG 型 sentence-level 改良

目的:

```text
文字間接続と spacing を明示的に学習
```

実装:

```text
Character Context Encoder
Bigram transition encoder
Sliding-window Transformer
Boundary loss
Spacing loss
```

CASHG は sentence-level online handwriting において、文字境界の接続性と spacing を明示的に評価する CSM を提案しているため、この段階の評価指標として参考にする。([arXiv][1])

---

### Phase 4: Diffusion / InkVAE 版

目的:

```text
行全体の自然性をさらに上げる
```

候補:

```text
InkVAE
Latent Diffusion Transformer
OCR loss
Style classification loss
```

DiffInk は full-line 生成で glyph accuracy と style fidelity を同時に扱うため、最終品質を狙うなら参考価値が高い。([arXiv][7])

---

## 14. 評価方法

### 14.1 人間評価

評価観点:

```text
文章として自然か
文字単体が読めるか
同じ人が書いたように見えるか
プロッタ臭さがあるか
```

### 14.2 認識器評価

```text
OCR/HWR で読めるか
文字誤読率
漢字/かな別誤読率
```

ETL は日本語文字画像の認識器学習に使えるため、レンダリング後の字形評価器に向く。([etlcdb -][18])

### 14.3 軌跡評価

```text
DTW distance
stroke length distribution
curvature distribution
velocity profile
pen-up distance
stroke count consistency
```

### 14.4 文章境界評価

```text
文字間隔分布
前文字終端→次文字始端の距離
行基線ドリフト
漢字/かなサイズ比
```

CASHG が提案する connectivity と spacing の評価観点は、この評価設計に直接対応する。([arXiv][1])

---

## 15. 推奨する初期実装構成

最初に作るべき構成はこれ。

```text
KanjiVG + handwritten kana templates
+ WriterProfile
+ ContextField
+ rule-based StrokeCondition
+ kinematic trajectory generator
+ SVG/G-code backend
```

まだ deep learning を使わない。

理由:

```text
日本語筆記の設計検証が先
データ入手前に動く
プロッタ固有問題を早期に発見できる
学習モデルの責務を切り分けられる
```

次に、TUAT データを使って `StrokeVariationModel` を差し替える。

---

## 16. 最重要設計判断

### 16.1 文字単位生成ではなく stroke 条件付き生成

悪い設計:

```text
char → trajectory
```

良い設計:

```text
char
+ stroke
+ writer
+ context
+ neighbor transition
→ trajectory
```

### 16.2 文脈は後処理ではなく入力条件

悪い設計:

```text
各文字を生成
↓
あとから行に並べる
```

良い設計:

```text
行文脈を先に生成
↓
各ストロークに条件として渡す
```

### 16.3 筆跡スタイルはランダムではなく一貫場

悪い設計:

```text
stroke마다 random noise
```

良い設計:

```text
writer profile + low-frequency context field
```

### 16.4 軌跡と速度を分ける

悪い設計:

```text
SVG path only
```

良い設計:

```text
geometry path
+ timing
+ velocity
+ pen-up
```

---

## 17. 最小データ構造案

### 17.1 WriterProfile

```json
{
  "writer_id": "synthetic_001",
  "global": {
    "slant": 0.04,
    "roundness": 0.35,
    "stroke_pressure": 0.7,
    "speed_mean": 45.0,
    "speed_variance": 0.15
  },
  "layout": {
    "spacing_mean": 1.05,
    "spacing_variance": 0.12,
    "baseline_drift": 0.3,
    "kana_scale": 0.82,
    "kanji_scale": 1.0
  },
  "stroke": {
    "hane_gain": 1.2,
    "harai_gain": 0.9,
    "tome_duration": 0.08,
    "curve_noise": 0.04
  }
}
```

### 17.2 StrokeCondition

```json
{
  "text_id": "sample_001",
  "line_index": 0,
  "char": "今",
  "char_index": 0,
  "stroke_index": 2,
  "stroke_type": "left_falling",
  "stroke_template": {
    "points": [[0.6, 0.2], [0.4, 0.5], [0.2, 0.8]]
  },
  "layout": {
    "x": 12.0,
    "y": 5.0,
    "w": 8.0,
    "h": 9.0
  },
  "context": {
    "line_position": 0.14,
    "local_scale": 0.97,
    "local_slant": 0.05,
    "baseline_offset": 0.2
  },
  "neighbor": {
    "prev_char": null,
    "next_char": "日",
    "prev_stroke_end": null,
    "next_entry_hint": [20.2, 6.1]
  }
}
```

### 17.3 Trajectory

```json
{
  "stroke_id": "sample_001_line0_char0_stroke2",
  "points": [
    {"x": 12.4, "y": 5.2, "t": 0.000, "pen": "down"},
    {"x": 12.2, "y": 5.8, "t": 0.018, "pen": "down"},
    {"x": 11.8, "y": 6.7, "t": 0.041, "pen": "down"}
  ]
}
```

---

## 18. 開発中に参照すべきリソース一覧

### オンライン手書き生成

* Graves 2013: RNN + MDN + attention の基準研究。([arXiv][3])
* DeepWriting: digital ink の style/content 分離。([arXiv][6])
* CASHG: sentence-level online handwriting、接続と spacing の明示モデル。([arXiv][1])
* DiffInk: full-line latent diffusion Transformer。([arXiv][7])
* DeepWriteSYN: 短期ストロークVAE合成。([arXiv][9])

### 日本語・漢字リソース

* TUAT HANDS-kuchibue: 日本語新聞文脈のオンライン手書き。([東京農工大学][16])
* TUAT HANDS-nakayosi: より広い日本語文字カテゴリのオンライン手書き。([東京農工大学][17])
* KanjiVG: 漢字筆順・筆画・部品構造。([KanjiVG][2])
* ETL Character Database: 日本語手書き画像評価・認識器用。([etlcdb -][18])
* Kuzushiji-MNIST/K49/K-Kanji: 崩し字系の将来拡張。([arXiv][22])

### 補助データ・OSS

* IAM-OnDB: 英語オンライン手書き文データ。([FKi Research Group][19])
* CASIA-OLHWDB: 中国語オンライン手書き。([arXiv][20])
* Quick, Draw!: 大規模 timestamped vector drawing。([GitHub][21])
* Sketch-RNN: stroke-3/5 形式と seq2seq VAE 実装参考。([GitHub][23])
* `sjvasquez/handwriting-synthesis`: Graves 実装参考。([GitHub][4])
* `pytorch-handwriting-synthesis-toolkit`: PyTorch 版 Graves 実装参考。([GitHub][5])

---

## 19. 最終的な推奨設計

結論として、最も筋が良い設計は次。

```text
Rule/DB-based Japanese stroke structure
+ Context-aware sentence-level conditioning
+ Data-driven trajectory generation
+ Kinematic post-processing
```

具体的には、

```text
KanjiVG
→ StrokeTemplate

TUAT HANDS
→ WriterProfile / StrokeVariation / TrajectoryDecoder

CASHG style context modeling
→ SentenceContext / NeighborTransition

Sigma-Lognormal
→ Velocity / Timing / Plotter realism

ETL
→ Rendered glyph evaluation
```

である。

初期段階では deep learning よりも、**StrokeCondition の設計を固めること**が重要。なぜなら、最終的に Transformer や Diffusion を使うとしても、モデルに何を条件として渡すかが自然な日本語文章筆記の品質を決めるためである。

[1]: https://arxiv.org/abs/2604.02103?utm_source=chatgpt.com "CASHG: Context-Aware Stylized Online Handwriting Generation"
[2]: https://kanjivg.tagaini.net/ "The Kanji Vector Graphics (KanjiVG) project - KanjiVG"
[3]: https://arxiv.org/abs/1308.0850?utm_source=chatgpt.com "Generating Sequences With Recurrent Neural Networks"
[4]: https://github.com/sjvasquez/handwriting-synthesis "GitHub - sjvasquez/handwriting-synthesis: Handwriting Synthesis with RNNs ✏️ · GitHub"
[5]: https://github.com/X-rayLaser/pytorch-handwriting-synthesis-toolkit "GitHub - X-rayLaser/pytorch-handwriting-synthesis-toolkit: Handwriting generation and handwriting synthesis as described in Alex Graves's paper https://arxiv.org/abs/1308.0850. Pytorch implementation. · GitHub"
[6]: https://arxiv.org/abs/1801.08379?utm_source=chatgpt.com "DeepWriting: Making Digital Ink Editable via Deep Generative Modeling"
[7]: https://arxiv.org/abs/2509.23624?utm_source=chatgpt.com "DiffInk: Glyph- and Style-Aware Latent Diffusion Transformer for Text to Online Handwriting Generation"
[8]: https://arxiv.org/abs/2410.02309?utm_source=chatgpt.com "Decoupling Layout from Glyph in Online Chinese Handwriting Generation"
[9]: https://arxiv.org/abs/2009.06308?utm_source=chatgpt.com "DeepWriteSYN: On-Line Handwriting Synthesis via Deep Short-Term Representations"
[10]: https://arxiv.org/abs/2401.16329?utm_source=chatgpt.com "Synthesis of 3D on-air signatures with the Sigma-Lognormal model"
[11]: https://arxiv.org/abs/2401.16519?utm_source=chatgpt.com "Extending the kinematic theory of rapid movements with new primitives"
[12]: https://arxiv.org/abs/2003.10557?utm_source=chatgpt.com "ScrabbleGAN: Semi-Supervised Varying Length Handwritten Text Generation"
[13]: https://arxiv.org/abs/2003.02567?utm_source=chatgpt.com "GANwriting: Content-Conditioned Generation of Styled Handwritten Word Images"
[14]: https://arxiv.org/abs/2104.03964?utm_source=chatgpt.com "Handwriting Transformers"
[15]: https://arxiv.org/abs/2005.12500?utm_source=chatgpt.com "CalliGAN: Style and Structure-aware Chinese Calligraphy Character Generator"
[16]: https://web.tuat.ac.jp/~nakagawa/database/en/about_kuchibue.html "Nakagawa Laboratory - On-line Handwriting Database"
[17]: https://web.tuat.ac.jp/~nakagawa/database/en/about_nakayosi.html "Nakagawa Laboratory - On-line Handwriting Database"
[18]: https://etlcdb.db.aist.go.jp/the-etl-character-database/ "The ETL Character Database - etlcdb"
[19]: https://fki.tic.heia-fr.ch/databases/iam-on-line-handwriting-database "Research Group on Computer Vision and Artificial Intelligence — Computer Vision and Artificial Intelligence"
[20]: https://arxiv.org/abs/1505.04922?utm_source=chatgpt.com "Character-level Chinese Writer Identification using Path Signature Feature, DropStroke and Deep CNN"
[21]: https://github.com/googlecreativelab/quickdraw-dataset "GitHub - googlecreativelab/quickdraw-dataset: Documentation on how to access and use the Quick, Draw! Dataset. · GitHub"
[22]: https://arxiv.org/abs/1812.01718?utm_source=chatgpt.com "Deep Learning for Classical Japanese Literature"
[23]: https://github.com/tensorflow/magenta/tree/main/magenta/models/sketch_rnn "magenta/magenta/models/sketch_rnn at main · magenta/magenta · GitHub"
