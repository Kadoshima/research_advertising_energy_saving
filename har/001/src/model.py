from __future__ import annotations

import torch
import torch.nn as nn


class DepthwiseSeparableConv(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, k: int = 5, s: int = 1):
        super().__init__()
        pad = k // 2
        self.depthwise = nn.Conv1d(in_ch, in_ch, kernel_size=k, stride=s, padding=pad, groups=in_ch)
        self.pointwise = nn.Conv1d(in_ch, out_ch, kernel_size=1, stride=1, padding=0)
        self.bn = nn.BatchNorm1d(out_ch)
        self.act = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.depthwise(x)
        x = self.pointwise(x)
        x = self.bn(x)
        x = self.act(x)
        return x


class DSCNN(nn.Module):
    """1D DSCNN for HAR. Input shape [B, T, C].

    チャネル幅を可変にして Tiny 構成を試せるようにしつつ、
    デフォルト値は従来の幅広構成（48→96→128→160, FC=128）を保持する。
    """

    def __init__(
        self,
        n_classes: int = 12,
        in_ch: int = 3,
        *,
        stem_channels: int = 48,
        dw_channels: tuple[int, ...] | list[int] = (96, 128, 160),
        fc_hidden: int = 128,
        dropout: float = 0.3,
    ):
        super().__init__()
        dw_channels = list(dw_channels)

        layers = [
            nn.Conv1d(in_ch, stem_channels, kernel_size=5, stride=1, padding=2),
            nn.BatchNorm1d(stem_channels),
            nn.ReLU(inplace=True),
        ]
        prev = stem_channels
        for out_ch in dw_channels:
            layers.append(DepthwiseSeparableConv(prev, out_ch, k=5, s=1))
            prev = out_ch
        layers.append(nn.Dropout(dropout))
        self.features = nn.Sequential(*layers)

        self.pool = nn.AdaptiveAvgPool1d(1)
        classifier = [nn.Flatten()]
        if fc_hidden and fc_hidden > 0:
            classifier.extend(
                [
                    nn.Linear(prev, fc_hidden),
                    nn.ReLU(inplace=True),
                    nn.Dropout(dropout),
                    nn.Linear(fc_hidden, n_classes),
                ]
            )
        else:
            classifier.append(nn.Linear(prev, n_classes))
        self.classifier = nn.Sequential(*classifier)

    def forward(self, x):
        # x: [B, T, C] -> [B, C, T]
        x = x.permute(0, 2, 1)
        x = self.features(x)
        x = self.pool(x)
        return self.classifier(x)
