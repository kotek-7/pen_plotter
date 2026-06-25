# Preview

正準軌跡(`x, y, t, pen_state, pressure`)を目視確認用の preview SVG に変換する基盤。

engine からも実機 export からも独立した描画専用の基盤として扱う。preview の見た目
(線幅、筆圧→線幅、色、ペンアップ移動の表示)はここで調整する。

## 変換規則

- `pen_state==1` の連続点を実線ストロークとして描く。
- `pen_state==0` の連続点はペンアップ移動として淡い破線で描く(任意)。
- 紙面座標は Y-UP。Y 反転は描画時のみ行い、座標系自体は反転しない。

## 使い方

ライブラリ:

```py
from scribing_preview.svg import trajectory_to_svg, PreviewConfig

svg = trajectory_to_svg(trajectory, PreviewConfig(scale=3.0))
```

CLI(既存 run の `trajectory.json` から `preview.svg` を再生成):

```sh
cd research/scribing-lab/preview
uv sync --extra dev
uv run scribe-render ../runs/20260626T123456_example
```
