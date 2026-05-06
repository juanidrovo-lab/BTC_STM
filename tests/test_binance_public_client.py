import pytest

from btc_stm.data.binance_public import BinancePublicClient


def test_binance_public_client_has_no_order_methods() -> None:
    client = BinancePublicClient()

    for method_name in ("buy", "sell", "create_order", "cancel_order", "place_order"):
        assert not hasattr(client, method_name)


def test_binance_public_client_does_not_open_real_connections() -> None:
    client = BinancePublicClient()

    with pytest.raises(NotImplementedError):
        client.get_order_book_snapshot("BTCUSDT")

    with pytest.raises(NotImplementedError):
        next(client.stream_trades("BTCUSDT"))

    with pytest.raises(NotImplementedError):
        next(client.stream_order_book("BTCUSDT"))

    with pytest.raises(NotImplementedError):
        next(client.stream_klines("BTCUSDT", "1m"))
