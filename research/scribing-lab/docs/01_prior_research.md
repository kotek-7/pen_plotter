# 01 Prior Research

## 対象領域

この研究は、オンライン手書き生成、運動学モデル、日本語文字構造辞書、ペンプロッタ制御、主観評価を横断する。中心は、画像生成ではなく `x,y,t,pen_state` を持つオンライン筆記生成である。

## Sigma-Lognormal 系

Sigma-Lognormal は、人間の素早い筆記運動を lognormal な速度成分の重ね合わせとして扱う。Plamondon 系の研究は、手書き生成、合成データ生成、運動障害分析などに応用されている。

重要な示唆:

- 手書きらしさは、軌跡形状だけでなく速度プロファイルに現れる。
- 画ごとに速度ピークを持つため、プロッタの feedrate 生成と相性が良い。
- 神経モデルより解釈しやすく、初期 MVP に向いている。

参照:

- [A sigma-lognormal model-based approach to generating large synthetic online handwriting sample databases](https://digitalcommons.isical.ac.in/journal-articles/2438/)
- [The lognormal handwriter](https://pmc.ncbi.nlm.nih.gov/articles/PMC3867641/)
- [The Quest for Lognormality](https://iapr.org/archives/icdar2013/docs/ICDAR2013-Plamondon.pdf)

## RNN / MDN 系

Alex Graves の系列生成研究は、LSTM と MDN によるオンライン手書き生成の代表例である。テキスト条件付きで筆点列を生成できる点は重要だが、日本語漢字の筆順・画構造を保証するものではない。

この研究での位置づけ:

- 比較ベースラインとして有用。
- 英語オンライン手書きでは強いが、日本語の構造制約には辞書が必要。
- 主系ではなく、writer style や sequence prior の参照に使う。

参照:

- [Generating Sequences With Recurrent Neural Networks](https://arxiv.org/abs/1308.0850)

## VAE / DeepWriting / DeepWriteSYN

DeepWriting は digital ink の style と content の分離を扱う。DeepWriteSYN は短時間セグメント単位の VAE でオンライン手書きの自然な変動を生成する。

この研究での位置づけ:

- 画単位または短画列の shape variation に適する。
- 長文全体を直接生成するより、辞書と Sigma-Lognormal の間に補助的に挟む方が安全。
- writer profile の学習にも参考になる。

参照:

- [DeepWriting: Making Digital Ink Editable via Deep Generative Modeling](https://huggingface.co/papers/1801.08379)
- [DeepWriteSYN: On-Line Handwriting Synthesis via Deep Short-Term Representations](https://arxiv.org/abs/2009.06308)

## Transformer / Style Disentanglement 系

SDT は writer style と character style の分離を扱う。CASHG は文レベルのオンライン手書きで、文字間の接続性や spacing を明示的に扱う。

この研究での位置づけ:

- 文レベル spacing と局所文脈の設計に有用。
- データ要求が大きいため、MVP では導入しない。
- neural-variation の後半テーマとして扱う。

参照:

- [Disentangling Writer and Character Styles for Handwriting Generation](https://arxiv.org/abs/2303.14736)
- [CASHG: Context-Aware Stylized Online Handwriting Generation](https://arxiv.org/abs/2604.02103)

## 日本語オンライン手書きデータ

TUAT Nakagawa Lab. の Kuchibue/Nakayosi は、日本語オンライン手書きデータとして重要である。公式情報では、Kuchibue は 120 人、Nakayosi は 163 人規模のデータとして説明されている。

この研究での位置づけ:

- 字単位運動 prior と writer profile 学習の本命。
- 利用条件・費用・再配布制限が研究上の主要リスク。
- 入手できない場合は、自前収集と KanjiVG ベースの合成で代替する。

参照:

- [TUAT Nakagawa Lab. On-line Handwriting Database](https://web.tuat.ac.jp/~nakagawa/database/index.html)
- [Masaki Nakagawa profile](https://web.tuat.ac.jp/~nakagawa/en/nakagawa.html)
- [On-line Handwriting Recognition for Creative Human Interfaces](https://web.tuat.ac.jp/~nakagawa/pub/2004/pdf/nakagawa0503b-e.pdf)

## 文字構造資産

KanjiVG は SVG に筆順や画情報を持つ。MJ 文字情報一覧表は UCS/IVS/MJ 文字図形名の対応に使える。GlyphWiki/KAGE は fallback として有望だが、利用条件の確認が必要である。

参照:

- [KanjiVG GitHub](https://github.com/KanjiVG/kanjivg)
- [KanjiVG SVG format](https://kanjivg.tagaini.net/svg-format.html)
- [MJ 文字情報一覧表](https://moji.or.jp/mojikiban/mjlist/)
- [GlyphWiki overview](https://wiki.suikawiki.org/n/GlyphWiki)
- [KAGE overview](https://wiki.suikawiki.org/n/KAGE)

## プロッタ制御

AxiDraw API は pen-down/up speed、pen height、pen lowering/raising rate、delay を制御できる。xDraw/GRBL では Z 軸と feedrate に変換して同等の抽象を作る。

参照:

- [AxiDraw Python API Reference](https://axidraw.com/doc/py_api/)
