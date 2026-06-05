# 03 Character Structure

## 目的

文字構造辞書は、入力文字を筆順付きの画列へ変換する。日本語の手書き再現では、字形画像だけでなく、どの順番でどの画を書くかが重要である。

## 最小データモデル

```json
{
  "char_id": "U+6C38",
  "literal": "永",
  "source": "kanjivg",
  "license": "CC BY-SA 3.0",
  "bbox": [0.0, 0.0, 1.0, 1.0],
  "strokes": [
    {
      "stroke_id": 1,
      "order": 1,
      "stroke_type": "ten",
      "path": "M ...",
      "skeleton_points": [[0.50, 0.08], [0.52, 0.15]],
      "terminal": "tome",
      "confidence": 1.0
    }
  ]
}
```

## 画種

初期実装では次の分類に落とす。

- `ten`: 点
- `yoko`: 横画
- `tate`: 縦画
- `hidari`: 左払い
- `migi`: 右払い
- `hane`: はね
- `ori`: 折れ
- `none`: 未分類

プロッタ出力では、これを `tome`, `harai`, `hane`, `none` の終端イベントへ写像する。

## KanjiVG 取り込み

KanjiVG は最初の主辞書とする。SVG path、stroke order、stroke type、部品構造を取り出す。

処理:

1. 対象文字の SVG を読む。
2. stroke group を筆順順に列挙する。
3. path を正規化座標へ変換する。
4. path から skeleton points を作る。
5. stroke type を内部画種へ変換する。
6. license metadata を保持する。

参照:

- [KanjiVG SVG format](https://kanjivg.tagaini.net/svg-format.html)
- [KanjiVG GitHub](https://github.com/KanjiVG/kanjivg)

## MJ / IVS

MJ 文字情報一覧表は、異体字や人名漢字を扱うために使う。MVP では文字同定テーブルだけを保持し、字形生成は KanjiVG 対応文字に限定する。

参照:

- [MJ 文字情報一覧表](https://moji.or.jp/mojikiban/mjlist/)

## GlyphWiki / KAGE fallback

KanjiVG にない文字の fallback として調査する。ただし、初期 MVP には入れない。利用条件、dump、生成 SVG の権利関係を確認してから採用する。

参照:

- [GlyphWiki overview](https://wiki.suikawiki.org/n/GlyphWiki)
- [KAGE overview](https://wiki.suikawiki.org/n/KAGE)

## 研究課題

- KanjiVG path から手書き骨格をどう抽出するか。
- 楷書辞書を、硬すぎない手書き骨格へどう変形するか。
- 筆順変動を許すべき文字と許さない文字をどう分けるか。
- `stroke_type` と実際の終筆イベントの対応をどう評価するか。
- KanjiVG 由来の骨格が `too-font-like` / `skeleton-too-rigid` になった場合、辞書側で補正する問題と motion 側で吸収する問題をどう分けるか。

## 初期評価

- `永` の画順が期待通りである。
- `あ`, `い`, `う`, `え`, `お` の画列が取得できる。
- 生成 skeleton が A4 座標へ安定に配置できる。
- 画順を保持したまま G-code に変換できる。
- 短文で配置したときに、文字骨格の硬さが文章全体の機械感を悪化させない。
