# 00 Overview

## 目的

この研究は、テキストからペンプロッタ向けの筆記軌跡を生成し、紙面上で人間の手書きと判別されにくい日本語文字を書くことを目的とする。

既存のフォントアウトライン方式は、字形の輪郭をなぞる用途には有効だが、人間の筆記とは異なる。人間の筆記では、筆順、速度変化、ペンアップ移動、終筆の抜き、字間、行方向の揺れ、筆者固有の癖が同時に現れる。この研究では、静的字形ではなく時間軸付きのオンライン筆記として生成する。

## 中心仮説

1. 手書きらしさは、静止画像の形状だけでなく、筆記運動の時間軸に強く依存する。
2. 日本語では、文字構造辞書で筆順と画種を拘束し、運動生成を確率化する構成が破綻しにくい。
3. writer profile を低次元の明示パラメータとして持つと、少量サンプルから個人差を近づけやすい。
4. xDraw/GRBL や AxiDraw では真の筆圧制御が限定されるため、pressure はまず仮想量として保持し、Z 高さ、速度、遅延へ写像する。
5. LLM エージェントが研究を主導する場合、評価基盤と実験記録基盤が先に存在しなければ、生成品質の改善を判断できない。

## LLM Agent Operating Model

LLM エージェントは、研究を次の閉ループとして進める。

```text
hypothesis
  -> experiment config
  -> generation / export
  -> tests and metrics
  -> artifact review
  -> failure taxonomy
  -> next experiment proposal
```

このループを成立させるため、最初に `evaluation-harness` と `writer-profile` の基盤部分を整備する。特に、実験 ID、seed、入力文字列、profile、生成物、評価結果を対応付けて保存できる状態を先に作る。

LLM エージェントは、評価結果を伴わない「見た目が良くなった」という判断を研究上の進捗として扱わない。各変更は、最低限の自動評価、成果物リンク、失敗分類、次の仮説を含む実験レポートとして残す。

## 全体アーキテクチャ

```text
text
  -> experiment config and profile selection
  -> text normalization
  -> character structure dictionary
  -> stroke templates
  -> writer profile adaptation
  -> shape variation
  -> sigma-lognormal timing
  -> pressure event model
  -> trajectory x,y,t,pen_state,pressure
  -> SVG / AxiDraw / G-code exporter
  -> preview / physical plotting
  -> metrics and experiment report
```

## 研究プロジェクト分割

| プロジェクト | 役割 | 初期成果物 |
|---|---|---|
| evaluation-harness | 自動評価、実験記録、成果物管理を再現可能にする | experiment registry と metric runner |
| writer-profile | 筆者固有の癖を保存・推定・適用し、実験条件として管理する | profile registry と baseline profiles |
| character-dictionary | 日本語文字から画列、筆順、画種、部品構造を得る | 小規模文字辞書 |
| motion-synthesis | 画骨格から人間らしい速度付き軌跡を生成する | Sigma-Lognormal MVP |
| plotter-export | 内部軌跡を実機命令へ落とす | xDraw G-code exporter |
| neural-variation | 神経モデルで自然な変動を補助する | 画単位 VAE/RNN baseline |

## 初期マイルストーン

最初の採択基準は、次の 3 文字列を現行フォント輪郭方式より自然に書けることである。

- `永`
- `あいうえお`
- 短文 3 種

自然さは、実機出力のスキャン画像、生成軌跡の速度分布、主観 ABX 評価で確認する。

## 成功条件

- 生成物が筆順を保持している。
- 速度が等速的ではなく、人間らしい加減速を持つ。
- ペンアップ移動が瞬間ジャンプではなく、機械制約内で自然に扱われる。
- 同一 writer profile から生成した文同士に一貫した癖が出る。
- 人間評価で、現行方式より手書きらしいと判定される。
- すべての主要実験が experiment registry に記録され、成果物と評価結果を追跡できる。

## 主要リスク

- TUAT 系データベースの入手・利用条件。
- KanjiVG/MJ/GlyphWiki 系資産のライセンス継承。
- xDraw の Z 軸制御で pressure を十分に表現できない可能性。
- 署名模倣や本人同意のない筆跡再現への濫用。
- 神経モデルを早期導入しすぎた場合の構造破綻。
- 評価基盤なしに LLM エージェントが生成モデルの局所改善へ進み、比較不能な成果物が増えること。
