"""Deterministic public market-report field selection and formatting.

This service owns presentation policy, not transport. X1 RPC lookups remain
injected by the integration layer so market presentation does not own RPC
clients or tokenomics scanning.
"""

from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any, Callable, Dict, Iterable, Optional


UsdFormatter = Callable[[Any], str]
SupplyLookup = Callable[[str], Optional[str]]
MintInfoLookup = Callable[[str], Optional[Dict[str, Any]]]

FIELD_ORDER = [
    "price",
    "age",
    "holders",
    "txns24",
    "volume24",
    "change1h",
    "change24h",
    "liquidity",
    "market_cap",
    "fdv",
    "total_supply_valuation",
    "safety",
]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number_or_zero(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _word(question: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", question) is not None


def requested_asset_fields(
    question: str,
    *,
    historical_comparison: bool = False,
    volume_rank: bool = False,
    historical_liquidity: bool = False,
):
    """Return explicitly requested public fields in stable v0.12 order.

    Route-specific predicates are supplied by the caller because historical
    storage/ranking interpretation remains outside this presentation service.
    """
    q = _text(question).lower()

    if historical_comparison:
        return []

    fields = []

    def add(field: str):
        if field not in fields:
            fields.append(field)

    if any(_word(q, x) for x in ("price", "worth", "cost")) or "trading at" in q:
        add("price")

    if _word(q, "age") or "how old" in q or _word(q, "created") or _word(q, "launched"):
        add("age")

    if _word(q, "holder") or _word(q, "holders"):
        add("holders")

    if any(_word(q, x) for x in ("transaction", "transactions", "txn", "txns")):
        add("txns24")

    if _word(q, "volume") and not volume_rank:
        add("volume24")

    one_hour_patterns = (
        r"\b1h\b",
        r"\b1\s*h\b",
        r"\b1hr\b",
        r"\b1\s*hr\b",
        r"\b1\s*hour\b",
        r"\bone hour\b",
        r"\bhourly\b",
    )
    day_24_patterns = (
        r"\b24h\b",
        r"\b24\s*h\b",
        r"\b24hr\b",
        r"\b24\s*hr\b",
        r"\b24\s*hour\b",
        r"\b24-hour\b",
        r"\btwenty[- ]four hour\b",
        r"\bdaily\b",
    )

    has_change = (
        _word(q, "change")
        or _word(q, "move")
        or _word(q, "performance")
        or "how much up" in q
        or "how much down" in q
    )

    if has_change and any(re.search(pattern, q) for pattern in one_hour_patterns):
        add("change1h")

    if has_change and any(re.search(pattern, q) for pattern in day_24_patterns):
        add("change24h")

    if has_change and "change1h" not in fields and "change24h" not in fields:
        add("change1h")
        add("change24h")

    if (_word(q, "liquidity") or _word(q, "liq")) and not historical_liquidity:
        add("liquidity")

    if (
        (
            "total supply" in q
            and "total supply valuation" not in q
            and "current supply valuation" not in q
        )
        or (
            "current supply" in q
            and "current supply valuation" not in q
        )
    ):
        add("total_supply")

    if (
        "current supply valuation" in q
        or "total supply valuation" in q
        or "supply valuation" in q
    ):
        add("total_supply_valuation")

    if (
        "circulating supply" in q
        or "circulating tokens" in q
        or "tokens circulating" in q
    ):
        add("circulating_supply")

    if "max supply" in q or "maximum supply" in q:
        add("max_supply")

    if (
        ("market cap" in q and "fully diluted market cap" not in q)
        or _word(q, "marketcap")
        or _word(q, "mcap")
    ):
        add("market_cap")

    if (
        _word(q, "fdv")
        or "fully diluted valuation" in q
        or "fully diluted market cap" in q
    ):
        add("fdv")

    if _word(q, "safety") or _word(q, "safe"):
        add("safety")

    if any(
        phrase in q
        for phrase in (
            "pool address",
            "pool contract address",
            "pool id",
            "pool identifier",
        )
    ):
        add("pool_address")

    ordered = [field for field in FIELD_ORDER if field in fields]

    if "total_supply" in fields:
        ordered.append("total_supply")
    if "circulating_supply" in fields:
        ordered.append("circulating_supply")
    if "max_supply" in fields:
        ordered.append("max_supply")
    if "pool_address" in fields:
        ordered.append("pool_address")

    return ordered


def wants_token_address(question: str) -> bool:
    """Only expose a token/mint address when explicitly requested."""
    q = _text(question).lower()
    return any(
        phrase in q
        for phrase in (
            "token address",
            "mint address",
            "token mint",
            "contract address",
        )
    )


def round_token_amount(value: Any) -> int:
    """Round to nearest whole token; .5 and above rounds up."""
    return int(
        Decimal(str(value)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def format_field_line(
    field: str,
    snap: Dict[str, Any],
    *,
    format_usd: UsdFormatter,
    get_total_supply: Optional[SupplyLookup] = None,
    get_mint_info: Optional[MintInfoLookup] = None,
) -> str:
    """Format one v0.12-compatible public field line.

    RPC-dependent values are resolved only through injected lookup callbacks.
    """
    if field == "circulating_supply":
        return "• Circulating Supply: Not available from verified data"

    if field == "total_supply":
        amount = (
            get_total_supply(snap.get("token_address"))
            if get_total_supply is not None
            else None
        )
        if amount:
            value = f"{round_token_amount(amount):,} {snap['symbol']}"
        else:
            value = "Not available from verified X1 RPC data"
        return f"• Total Supply: {value}"

    if field == "max_supply":
        info = (
            get_mint_info(snap.get("token_address"))
            if get_mint_info is not None
            else None
        )
        if not info:
            return "• Max Supply: Not available from verified X1 RPC data"
        if info.get("mint_authority") is None:
            return (
                "• Max Supply: Original maximum issuance not verified "
                "• Mint authority revoked"
            )
        return "• Max Supply: Not fixed • Mint authority active"

    if field == "market_cap":
        return (
            "• Market Cap: Not verified "
            "— circulating supply unavailable from verified data"
        )

    if field == "fdv":
        amount = (
            get_total_supply(snap.get("token_address"))
            if get_total_supply is not None
            else None
        )
        price = _number_or_zero(snap.get("price_usd_value"))

        current_valuation = None
        if amount and price > 0:
            current_valuation = Decimal(str(amount)) * Decimal(str(price))

        if current_valuation is not None:
            return (
                "• Fully Diluted Valuation (FDV): Not verified "
                "— maximum supply unavailable from verified data "
                f"• Current Supply Valuation: {format_usd(float(current_valuation))} "
                "• Current Supply Valuation is price × current total supply; "
                "it is not FDV unless current total supply equals maximum supply."
            )

        return (
            "• Fully Diluted Valuation (FDV): Not verified "
            "— maximum supply unavailable from verified data"
        )

    if field == "total_supply_valuation":
        amount = (
            get_total_supply(snap.get("token_address"))
            if get_total_supply is not None
            else None
        )
        price = _number_or_zero(snap.get("price_usd_value"))

        if not amount or price <= 0:
            return "• Current Supply Valuation: Not available from verified data"

        valuation = Decimal(str(amount)) * Decimal(str(price))
        return (
            "• Current Supply Valuation: "
            f"{format_usd(float(valuation))} "
            "• This is price × current total supply. "
            "It is not FDV unless current total supply equals maximum supply. "
            "Market Cap separately requires verified circulating supply."
        )

    labels = {
        "price": "Price",
        "age": "Age",
        "holders": "Holders",
        "txns24": "Transactions 24h",
        "volume24": "Volume 24h",
        "change1h": "Change 1h",
        "change24h": "Change 24h",
        "liquidity": "Liquidity",
        "safety": "Tokenomics Safety",
        "pool_address": "Pool Address",
    }

    if field not in labels:
        raise KeyError(field)

    values = {
        "price": snap["price"],
        "age": snap["age"],
        "holders": f"{snap['holders']:,}",
        "txns24": f"{snap['txns24']:,}",
        "volume24": format_usd(snap["vol24"]),
        "change1h": f"{snap['change1']:+.2f}%",
        "change24h": f"{snap['change24']:+.2f}%",
        "liquidity": format_usd(snap["liquidity"]),
        "safety": snap["safety"],
        "pool_address": snap.get("pool_address") or "N/A",
    }

    value = values[field]
    if field == "liquidity":
        return (
            f"• {labels[field]}: {value} "
            f"• Pools: {snap.get('pool_count', 1)}"
        )
    return f"• {labels[field]}: {value}"


def full_snapshot_lines(
    snap: Dict[str, Any],
    *,
    format_usd: UsdFormatter,
    get_total_supply: Optional[SupplyLookup] = None,
    get_mint_info: Optional[MintInfoLookup] = None,
) -> list[str]:
    """Format the stable default public market snapshot field set."""
    return [
        format_field_line(
            field,
            snap,
            format_usd=format_usd,
            get_total_supply=get_total_supply,
            get_mint_info=get_mint_info,
        )
        for field in FIELD_ORDER
    ]
