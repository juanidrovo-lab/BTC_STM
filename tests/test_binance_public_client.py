import math

import pytest
import httpx

from btc_stm.data.binance_public import BinancePublicClient, VALID_DEPTH_LIMITS


def make_depth_response() -> dict[str, object]:
    return {
        "lastUpdateId": 100,
        "bids": [["50000.00", "0.10"]],
        "asks": [["50001.00", "0.20"]],
    }


def test_binance_public_client_uses_public_depth_endpoint() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=make_depth_response(),
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
            json=make_depth_response(),
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


def test_binance_public_client_invalid_limit_raises_without_request() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, json=make_depth_response())

    client = BinancePublicClient(
        http_client=httpx.Client(
            base_url="https://api.binance.com",
            transport=httpx.MockTransport(handler),
        )
    )

    with pytest.raises(ValueError, match="valid depth limits"):
        client.get_order_book_snapshot("BTCUSDT", limit=999)

    assert request_count == 0


def test_binance_public_client_accepts_all_valid_depth_limits() -> None:
    requested_limits: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_limits.append(request.url.params["limit"])
        return httpx.Response(200, json=make_depth_response())

    client = BinancePublicClient(
        http_client=httpx.Client(
            base_url="https://api.binance.com",
            transport=httpx.MockTransport(handler),
        )
    )

    for limit in sorted(VALID_DEPTH_LIMITS):
        snapshot = client.get_order_book_snapshot("BTCUSDT", limit=limit)
        assert snapshot.last_update_id == 100

    assert requested_limits == [str(limit) for limit in sorted(VALID_DEPTH_LIMITS)]


def test_binance_public_client_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        BinancePublicClient(timeout_seconds=0)
    with pytest.raises(ValueError, match="timeout_seconds"):
        BinancePublicClient(timeout_seconds=-1)


def test_binance_public_client_rejects_non_finite_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        BinancePublicClient(timeout_seconds=math.nan)
    with pytest.raises(ValueError, match="timeout_seconds"):
        BinancePublicClient(timeout_seconds=math.inf)


def test_binance_public_client_respects_custom_base_url_with_mock_transport() -> None:
    requested_url: httpx.URL | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requested_url
        requested_url = request.url
        return httpx.Response(200, json=make_depth_response())

    client = BinancePublicClient(
        base_url="https://data.example.test",
        http_client=httpx.Client(
            base_url="https://data.example.test",
            transport=httpx.MockTransport(handler),
        ),
    )

    client.get_order_book_snapshot("BTCUSDT")

    assert requested_url is not None
    assert requested_url.host == "data.example.test"
    assert requested_url.path == "/api/v3/depth"


def test_binance_public_client_rest_snapshot_uses_single_receive_timestamp() -> None:
    client = BinancePublicClient(
        http_client=httpx.Client(
            base_url="https://api.binance.com",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=make_depth_response())
            ),
        )
    )

    snapshot = client.get_order_book_snapshot("BTCUSDT")

    assert snapshot.event_time == snapshot.local_receive_time


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
