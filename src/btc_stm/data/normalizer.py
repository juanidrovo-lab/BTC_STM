"""Normalization helpers for public market data."""

from __future__ import annotations


def normalize_symbol(symbol: str) -> str:
    """Normalize common Binance symbol spellings to the compact uppercase form."""
    return symbol.upper().strip().replace("/", "").replace("-", "")
