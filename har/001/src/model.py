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
    """Lightweight 1D DSCNN for HAR. Input shape [B, T, C]."""

    def __init__(self, n_classes: int = 12, in_ch: int = 3):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(in_ch, 32, kernel_size=5, stride=1, padding=2),
            nn.BatchNorm1d(32),
            nn.ReLU(inplace=True),
            DepthwiseSeparableConv(32, 64, k=5, s=1),
            DepthwiseSeparableConv(64, 96, k=5, s=1),
        )
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.classifier = nn.Linear(96, n_classes)

    def forward(self, x):
        # x: [B, T, C] -> [B, C, T]
        x = x.permute(0, 2, 1)
        x = self.features(x)
        x = self.pool(x).squeeze(-1)
        return self.classifier(x)
