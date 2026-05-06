import pytest
import httpx

from btc_stm.data.binance_public import BinancePublicClient


def test_binance_public_client_uses_public_depth_endpoint() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "lastUpdateId": 100,
                "bids": [["50000.00", "0.10"]],
                "asks": [["50001.00", "0.20"]],
            },
        )

    client = BinancePublicClient(
        http_client=httpx.Client(
            base_url="https://api.binance.com",
            transport=httpx.MockTransport(handler),
        )
    )

    snapshot = client.get_order_book_snapshot("btcusdt", limit=5)

    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.last_update_id == 100
    assert requests[0].url.path == "/api/v3/depth"
    assert requests[0].url.params["symbol"] == "BTCUSDT"
    assert requests[0].url.params["limit"] == "5"


def test_binance_public_client_sends_no_api_key_headers() -> None:
    captured_headers: httpx.Headers | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers
        captured_headers = request.headers
        return httpx.Response(
            200,
            json={
                "lastUpdateId": 100,
                "bids": [["50000.00", "0.10"]],
                "asks": [["50001.00", "0.20"]],
            },
        )

    client = BinancePublicClient(
        http_client=httpx.Client(
            base_url="https://api.binance.com",
            transport=httpx.MockTransport(handler),
        )
    )

    client.get_order_book_snapshot("BTCUSDT")

    assert captured_headers is not None
    assert "x-mbx-apikey" not in captured_headers


def test_binance_public_client_has_no_order_methods() -> None:
    client = BinancePublicClient()

    for method_name in ("buy", "sell", "create_order", "cancel_order", "place_order"):
        assert not hasattr(client, method_name)


def test_binance_public_client_does_not_open_real_connections() -> None:
    client = BinancePublicClient()

    with pytest.raises(NotImplementedError):
        next(client.stream_trades("BTCUSDT"))

    with pytest.raises(NotImplementedError):
        next(client.stream_order_book("BTCUSDT"))

    with pytest.raises(NotImplementedError):
        next(client.stream_klines("BTCUSDT", "1m"))
