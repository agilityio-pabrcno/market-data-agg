"""CLI to test market_data_agg API routers and provider streams.

Usage:
  poetry run test-routers health
  poetry run test-routers stocks quote AAPL
  poetry run test-routers stream crypto bitcoin --messages 5
"""
import argparse
import asyncio
import json
import sys

import httpx


def print_json(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


def cmd_health(client: httpx.Client, _: argparse.Namespace) -> int:
    r = client.get("/")
    r.raise_for_status()
    print_json(r.json())
    return 0


def cmd_stocks_quote(client: httpx.Client, args: argparse.Namespace) -> int:
    r = client.get(f"/stocks/{args.symbol}")
    r.raise_for_status()
    print_json(r.json())
    return 0


def cmd_stocks_history(client: httpx.Client, args: argparse.Namespace) -> int:
    r = client.get(f"/stocks/{args.symbol}/history", params={"days": args.days})
    r.raise_for_status()
    data = r.json()
    print(f"Found {len(data)} history points for {args.symbol}")
    print_json(data[: args.head] if args.head else data)
    return 0


def cmd_stocks_refresh(client: httpx.Client, _: argparse.Namespace) -> int:
    r = client.post("/stocks/refresh")
    r.raise_for_status()
    print_json(r.json())
    return 0


def cmd_crypto_quote(client: httpx.Client, args: argparse.Namespace) -> int:
    r = client.get(f"/crypto/{args.symbol}")
    r.raise_for_status()
    print_json(r.json())
    return 0


def cmd_crypto_history(client: httpx.Client, args: argparse.Namespace) -> int:
    r = client.get(f"/crypto/{args.symbol}/history", params={"days": args.days})
    r.raise_for_status()
    data = r.json()
    print(f"Found {len(data)} history points for {args.symbol}")
    print_json(data[: args.head] if args.head else data)
    return 0


def cmd_crypto_refresh(client: httpx.Client, _: argparse.Namespace) -> int:
    r = client.post("/crypto/refresh")
    r.raise_for_status()
    print_json(r.json())
    return 0


def cmd_polymarket_list(client: httpx.Client, args: argparse.Namespace) -> int:
    params = {"active": not args.inactive, "limit": args.limit}
    if args.tag_id:
        params["tag_id"] = args.tag_id
    r = client.get("/polymarket/markets", params=params)
    r.raise_for_status()
    data = r.json()
    print(f"Found {len(data)} markets")
    print_json(data[: args.head] if args.head else data)
    return 0


def cmd_polymarket_get(client: httpx.Client, args: argparse.Namespace) -> int:
    r = client.get(f"/polymarket/markets/{args.market_id}")
    r.raise_for_status()
    print_json(r.json())
    return 0


def cmd_polymarket_refresh(client: httpx.Client, _: argparse.Namespace) -> int:
    r = client.post("/polymarket/refresh")
    r.raise_for_status()
    print_json(r.json())
    return 0


def cmd_markets_overview(client: httpx.Client, args: argparse.Namespace) -> int:
    params = {
        "include_stocks": not args.no_stocks,
        "include_crypto": not args.no_crypto,
        "include_polymarket": not args.no_polymarket,
        "polymarket_limit": args.polymarket_limit,
    }
    r = client.get("/markets/overview", params=params)
    r.raise_for_status()
    data = r.json()
    print(f"Overview: {len(data)} quotes")
    print_json(data[: args.head] if args.head else data)
    return 0


def cmd_markets_top_movers(client: httpx.Client, args: argparse.Namespace) -> int:
    params = {"limit": args.limit}
    if args.source:
        params["source"] = args.source
    r = client.get("/markets/top-movers", params=params)
    r.raise_for_status()
    data = r.json()
    print(f"Top movers: {len(data)} results")
    print_json(data)
    return 0


def cmd_markets_trends(client: httpx.Client, _: argparse.Namespace) -> int:
    r = client.get("/markets/trends")
    r.raise_for_status()
    print_json(r.json())
    return 0


def _stream_run(
    provider_name: str,
    symbols: list[str],
    duration: float | None,
    max_messages: int | None,
) -> int:
    """Run a provider's stream() and print StreamMessages."""
    from market_data_agg.providers import (
        CoinGeckoProvider,
        PolymarketProvider,
        YFinanceProvider,
    )

    providers = {
        "stocks": YFinanceProvider,
        "crypto": CoinGeckoProvider,
        "polymarket": PolymarketProvider,
    }
    cls = providers[provider_name]
    count = 0

    async def run() -> None:
        nonlocal count
        async with cls() as provider:
            print(
                f"Streaming {provider_name} for {symbols} "
                f"(duration={duration}s, max_messages={max_messages or '∞'})",
                file=sys.stderr,
            )
            try:
                async for msg in provider.stream(symbols):
                    count += 1
                    print_json(msg.model_dump(mode="json"))
                    if max_messages and count >= max_messages:
                        return
            except asyncio.CancelledError:
                pass

    async def run_with_timeout() -> None:
        if duration and duration > 0:
            try:
                await asyncio.wait_for(run(), timeout=duration)
            except asyncio.TimeoutError:
                print(f"Stopped after {duration}s ({count} messages)", file=sys.stderr)
        else:
            await run()

    try:
        asyncio.run(run_with_timeout())
    except KeyboardInterrupt:
        print(f"\nStopped by user ({count} messages)", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Stream error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_stream_stocks(_client: httpx.Client | None, args: argparse.Namespace) -> int:
    symbols = [s.upper() for s in args.symbols]
    return _stream_run(
        "stocks",
        symbols,
        getattr(args, "duration", None),
        getattr(args, "messages", None),
    )


def cmd_stream_crypto(_client: httpx.Client | None, args: argparse.Namespace) -> int:
    return _stream_run(
        "crypto",
        args.symbols,
        getattr(args, "duration", None),
        getattr(args, "messages", None),
    )


def cmd_stream_polymarket(_client: httpx.Client | None, args: argparse.Namespace) -> int:
    return _stream_run(
        "polymarket",
        args.symbols,
        getattr(args, "duration", None),
        getattr(args, "messages", None),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test market_data_agg API routers and provider streams.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds (default: 30)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command")

    # health
    subparsers.add_parser("health", help="GET / health check")

    # stocks
    stocks = subparsers.add_parser("stocks", help="Stock routes (/stocks)")
    stocks_sub = stocks.add_subparsers(dest="stocks_cmd", required=True)
    p = stocks_sub.add_parser("quote", help="GET /stocks/{symbol}")
    p.add_argument("symbol", help="Ticker (e.g. AAPL, MSFT)")
    p = stocks_sub.add_parser("history", help="GET /stocks/{symbol}/history")
    p.add_argument("symbol", help="Ticker")
    p.add_argument("--days", type=int, default=30, help="Days of history (default: 30)")
    p.add_argument("--head", type=int, default=0, help="Show only first N points (0 = all)")
    stocks_sub.add_parser("refresh", help="POST /stocks/refresh")

    # crypto
    crypto = subparsers.add_parser("crypto", help="Crypto routes (/crypto)")
    crypto_sub = crypto.add_subparsers(dest="crypto_cmd", required=True)
    p = crypto_sub.add_parser("quote", help="GET /crypto/{symbol}")
    p.add_argument("symbol", help="CoinGecko ID (e.g. bitcoin, ethereum)")
    p = crypto_sub.add_parser("history", help="GET /crypto/{symbol}/history")
    p.add_argument("symbol", help="CoinGecko ID")
    p.add_argument("--days", type=int, default=30, help="Days of history (default: 30)")
    p.add_argument("--head", type=int, default=0, help="Show only first N points (0 = all)")
    crypto_sub.add_parser("refresh", help="POST /crypto/refresh")

    # polymarket
    poly = subparsers.add_parser("polymarket", help="Polymarket routes (/polymarket)")
    poly_sub = poly.add_subparsers(dest="polymarket_cmd", required=True)
    p = poly_sub.add_parser("list", help="GET /polymarket/markets")
    p.add_argument("--limit", type=int, default=10, help="Max markets (default: 10)")
    p.add_argument("--inactive", action="store_true", help="Include inactive markets")
    p.add_argument("--tag-id", default=None, help="Filter by tag ID")
    p.add_argument("--head", type=int, default=0, help="Show only first N (0 = all)")
    p = poly_sub.add_parser("get", help="GET /polymarket/markets/{market_id}")
    p.add_argument("market_id", help="Market slug or condition ID")
    poly_sub.add_parser("refresh", help="POST /polymarket/refresh")

    # markets
    markets = subparsers.add_parser("markets", help="Aggregated markets (/markets)")
    markets_sub = markets.add_subparsers(dest="markets_cmd", required=True)
    p = markets_sub.add_parser("overview", help="GET /markets/overview")
    p.add_argument("--no-stocks", action="store_true", help="Exclude stocks")
    p.add_argument("--no-crypto", action="store_true", help="Exclude crypto")
    p.add_argument("--no-polymarket", action="store_true", help="Exclude polymarket")
    p.add_argument("--polymarket-limit", type=int, default=5, help="Max polymarket (default: 5)")
    p.add_argument("--head", type=int, default=0, help="Show only first N (0 = all)")
    p = markets_sub.add_parser("top-movers", help="GET /markets/top-movers")
    p.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    p.add_argument("--source", choices=["stock", "crypto", "polymarket"], default=None, help="Filter by source")
    markets_sub.add_parser("trends", help="GET /markets/trends")

    # stream (provider streams; no server required)
    stream_parser = subparsers.add_parser(
        "stream",
        help="Test provider streams (stocks/crypto=polling, polymarket=WebSocket)",
    )
    stream_sub = stream_parser.add_subparsers(dest="stream_cmd", required=True)
    for name, help_text in [
        ("stocks", "YFinance stream (polling)"),
        ("crypto", "CoinGecko stream (polling)"),
        ("polymarket", "Polymarket CLOB WebSocket stream"),
    ]:
        p = stream_sub.add_parser(name, help=help_text)
        p.add_argument(
            "symbols",
            nargs="+",
            help="Symbols to stream (e.g. AAPL MSFT, or bitcoin ethereum, or condition IDs)",
        )
        p.add_argument(
            "--duration",
            type=float,
            default=None,
            metavar="SECS",
            help="Stop after SECS seconds (default: run until Ctrl+C)",
        )
        p.add_argument(
            "--messages",
            type=int,
            default=None,
            metavar="N",
            help="Stop after N messages (default: no limit)",
        )

    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    handlers = {
        "health": cmd_health,
        "stocks": {
            "quote": cmd_stocks_quote,
            "history": cmd_stocks_history,
            "refresh": cmd_stocks_refresh,
        },
        "crypto": {
            "quote": cmd_crypto_quote,
            "history": cmd_crypto_history,
            "refresh": cmd_crypto_refresh,
        },
        "polymarket": {
            "list": cmd_polymarket_list,
            "get": cmd_polymarket_get,
            "refresh": cmd_polymarket_refresh,
        },
        "markets": {
            "overview": cmd_markets_overview,
            "top-movers": cmd_markets_top_movers,
            "trends": cmd_markets_trends,
        },
        "stream": {
            "stocks": cmd_stream_stocks,
            "crypto": cmd_stream_crypto,
            "polymarket": cmd_stream_polymarket,
        },
    }

    cmd = args.command
    if cmd == "health":
        handler = handlers["health"]
    elif cmd == "stream":
        sub = getattr(args, "stream_cmd", None)
        if sub is None:
            parser.error("Missing subcommand for stream")
        handler = handlers["stream"][sub]
        try:
            return handler(None, args)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        sub = getattr(args, f"{cmd}_cmd", None)
        if sub is None:
            parser.error(f"Missing subcommand for {cmd}")
        handler = handlers[cmd][sub]

    try:
        with httpx.Client(base_url=base_url, timeout=args.timeout) as client:
            return handler(client, args)
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code}", file=sys.stderr)
        if e.response.content:
            try:
                print(e.response.json(), file=sys.stderr)
            except Exception:
                print(e.response.text, file=sys.stderr)
        return 1
    except httpx.RequestError as e:
        print(f"Request error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
