# BTC_STM

Sprint 0 del sistema seguro de trading para Binance Spot (**paper-only**).

## Seguridad por defecto

- `TRADING_MODE=paper` por defecto.
- `ENABLE_LIVE_TRADING=false` por defecto.
- Si `TRADING_MODE=live` y no se activa `ENABLE_LIVE_TRADING=true`, la app falla en validación de configuración.
- No hay implementación de órdenes reales ni conexión a endpoints privados de Binance.

## Configuración

1. Copiar variables:

```bash
cp .env.example .env
```

2. Editar `.env` solo para entorno local.

> `.env` está ignorado por git para evitar exponer secrets.

## Dominio Sprint 0

Modelos implementados:

- `SignalAction`
- `OrderSide`
- `OrderType`
- `Signal`
- `OrderIntent`
- `PortfolioState`
- `RiskDecision`
- `SymbolFilters`

## Risk Manager

`RiskManager` centraliza validaciones de riesgo y filtros tipo Binance Spot:

- stop-loss obligatorio.
- pérdida diaria máxima.
- kill switch.
- máximo de posiciones abiertas.
- riesgo máximo por trade.
- `PRICE_FILTER`.
- `LOT_SIZE`.
- `MIN_NOTIONAL`.
- máximo notional por posición.

## Desarrollo

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
mypy .
```
