from __future__ import annotations

Stroke = list[tuple[float, float]]


def place_in_cell(
    strokes: list[Stroke],
    *,
    origin_x: float,
    top_y: float,
    cell_size: float,
    baseline: float = 0.9,
) -> list[Stroke]:
    """生成字形をセルへ配置する (DR Phase5 の layout: box/baseline/spacing)。

    生成器の出力はセル正規化 (y-down) かつ第一ストローク点基準の相対座標。サイズ正規化は
    行わず（字面の大きさはモデル出力の素のまま＝セル正規化 × ``cell_size``）、**位置だけ**
    揃える。

    - box: ``(origin_x, top_y)`` を左上、一辺 ``cell_size`` のセル
    - baseline: 字面下端 (bbox) をセル上端から ``baseline`` 比率の高さへ揃える
    - 水平: 字面中心 (bbox) をセル中央へ寄せる

    bbox は配置（中心・下端）の算出にのみ使い、拡縮はしない。紙面 mm (Y-up) を返す。
    """
    points = [p for stroke in strokes for p in stroke]
    if not points:
        return []
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    glyph_cx = (min(xs) + max(xs)) / 2.0
    max_y = max(ys)

    scale = cell_size  # サイズ正規化なし: セル正規化座標をそのまま cell 寸法へ
    cell_cx = origin_x + cell_size / 2.0
    baseline_y = top_y - cell_size * baseline  # 字面下端 (max_y) を揃える紙面 Y-up の高さ

    return [
        [(cell_cx + (x - glyph_cx) * scale, baseline_y + (max_y - y) * scale) for x, y in stroke]
        for stroke in strokes
    ]
