from __future__ import annotations

import torch
import torch.nn as nn

from .config import INPUT_DIM, PEN_CLASSES, ModelConfig


class CharCondLSTMMDN(nn.Module):
    """char 埋め込みを各時刻入力へ連結する LSTM-MDN。

    入力 x: (B, T, 5) = (dx, dy, pen_onehot[3])
    char_id: (B,)
    出力: (B, T, M*6+3) の MDN ヘッド生出力。
    """

    def __init__(self, num_chars: int, config: ModelConfig) -> None:
        super().__init__()
        self.config = config
        self.num_chars = num_chars
        self.embedding = nn.Embedding(num_chars, config.emb_dim)
        self.lstm = nn.LSTM(
            input_size=INPUT_DIM + config.emb_dim,
            hidden_size=config.hidden,
            num_layers=config.layers,
            batch_first=True,
            dropout=config.dropout if config.layers > 1 else 0.0,
        )
        self.head = nn.Linear(config.hidden, config.mixtures * 6 + PEN_CLASSES)

    def _embed_input(self, x: torch.Tensor, char_id: torch.Tensor) -> torch.Tensor:
        emb = self.embedding(char_id)  # (B, E)
        emb = emb.unsqueeze(1).expand(-1, x.shape[1], -1)  # (B, T, E)
        return torch.cat([x, emb], dim=-1)

    def forward(
        self,
        x: torch.Tensor,
        char_id: torch.Tensor,
        lengths: torch.Tensor | None = None,
    ) -> torch.Tensor:
        inp = self._embed_input(x, char_id)
        if lengths is not None:
            packed = nn.utils.rnn.pack_padded_sequence(
                inp, lengths.cpu(), batch_first=True, enforce_sorted=False
            )
            out, _ = self.lstm(packed)
            out, _ = nn.utils.rnn.pad_packed_sequence(out, batch_first=True, total_length=x.shape[1])
        else:
            out, _ = self.lstm(inp)
        return self.head(out)

    def step(
        self,
        x_t: torch.Tensor,  # (1, 1, 5)
        char_id: torch.Tensor,  # (1,)
        state: tuple[torch.Tensor, torch.Tensor] | None,
    ) -> tuple[torch.Tensor, tuple[torch.Tensor, torch.Tensor]]:
        """生成用 1 ステップ。raw (1, 1, M*6+3) と次の LSTM 状態を返す。"""
        inp = self._embed_input(x_t, char_id)
        out, state = self.lstm(inp, state)
        return self.head(out), state
