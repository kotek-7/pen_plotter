# Character Dictionary Research Plan

## 目的

入力文字から、筆順、画種、部品構造、正規化 skeleton を持つ stroke template を生成する。手書き生成の content 制約をこの辞書が担う。

## 背景

日本語文字は、単に輪郭をなぞるだけでは人間の筆記にならない。筆順、画の始終点、払い・はね・とめ、部品配置が必要である。KanjiVG はこの目的に最も近い公開資産で、MJ 文字情報一覧表は異体字や UCS/IVS 対応に使える。

## 主要仮説

1. KanjiVG の stroke path と stroke type から、初期の手書き skeleton は構築できる。
2. stroke type を単純化しても、終端イベントの制御には十分使える。
3. 異体字対応は MVP では生成対象外にし、文字同定 metadata として先に保持すればよい。
4. KanjiVG 由来の骨格は硬すぎる可能性があるため、辞書 MVP の段階から `too-font-like` と `skeleton-too-rigid` を評価対象にする。

## スコープ

含む:

- KanjiVG parser の設計。
- stroke template schema。
- かなと頻出漢字の小規模辞書。
- stroke type から terminal event への変換。
- skeleton rigidity review。

含まない:

- 全 JIS 第一水準対応。
- GlyphWiki/KAGE の本格取り込み。
- 筆順変動の学習。

## 実験

### Experiment 1: KanjiVG path extraction

対象文字:

- `永`
- ひらがな 10 字。
- 頻出漢字 20 字。

確認:

- stroke count。
- order。
- bbox。
- path から skeleton points への変換。

### Experiment 2: terminal event mapping

KanjiVG stroke type を `tome`, `harai`, `hane`, `none` へ写像する。

評価:

- `永` の終端イベントが直感と大きく外れない。
- G-code exporter へ finish 情報を渡せる。

### Experiment 3: skeleton rigidity review

KanjiVG path から得た skeleton が、手書き骨格として硬すぎないかを確認する。

評価:

- `too-font-like` と `skeleton-too-rigid` を failure tags として付与できる。
- motion model 側で補正すべき問題と、辞書側で修正すべき問題を分けられる。

### Experiment 4: layout normalization

正規化座標から A4 mm 座標へ配置する。

評価:

- 文字サイズ変更で形が崩れない。
- 行方向の baseline と bbox が安定する。

## 成果物

- `stroke-template.schema.json` 案。
- 小規模辞書データ。
- 正規化済み辞書 JSON 出力。
- KanjiVG parser 仕様。
- terminal mapping table。
- skeleton rigidity review。
- license metadata 設計。

## 評価指標

- parser 成功率。
- stroke count の一致。
- path bbox の妥当性。
- skeleton の連続性。
- terminal mapping の人手確認結果。
- skeleton rigidity の人手確認結果。

## リスク

- KanjiVG の字形が硬く、手書き skeleton として不自然。
- CC BY-SA 3.0 の継承条件。
- かなの stroke type が漢字ほど扱いやすくない可能性。
- path から skeleton への抽出で筆画幅や輪郭情報が混ざる可能性。

## 参照

- [KanjiVG GitHub](https://github.com/KanjiVG/kanjivg)
- [KanjiVG SVG format](https://kanjivg.tagaini.net/svg-format.html)
- [MJ 文字情報一覧表](https://moji.or.jp/mojikiban/mjlist/)
