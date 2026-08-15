"""MoltGrid entrypoint wired to reusable Liquidity Scout services.

This is a migration seam for the current v0.12 listener. It keeps the legacy
MoltGrid transport, AI routing, conversation state, and non-tokenomics RPC
behavior intact while replacing reusable market intelligence and tokenomics
lookups at runtime.

Run with:
    python -m liquidity_scout.integrations.moltgrid
"""

import re
from decimal import Decimal, InvalidOperation
from importlib import import_module
from collections.abc import Mapping

from liquidity_scout.cmis import CMISGateway
from liquidity_scout.integrations.moltgrid_asset_cmis import (
    cmis_asset_service,
    format_cmis_asset_answer,
)
from liquidity_scout.market import (
    AmbiguousAssetError,
    XDEXCatalog as CoreXDEXCatalog,
    resolve_asset as core_resolve_asset,
    resolve_multiple_assets as core_resolve_multiple_assets,
)
from liquidity_scout.services import (
    FIELD_ORDER as CORE_FIELD_ORDER,
    build_market_report,
    build_verified_market_context,
    format_historical_comparison as core_format_historical_comparison,
    format_field_line as core_format_field_line,
    format_market_comparison,
    full_snapshot_lines as core_full_snapshot_lines,
    liquidity_depth_label,
    price_movement_label,
    requested_asset_fields as core_requested_asset_fields,
    volume_activity_label,
    wants_token_address as core_wants_token_address,
)
from liquidity_scout.tokenomics import (
    X1RPCError,
    get_mint_info as core_get_mint_info,
    get_token_supply as core_get_token_supply,
)


_CMIS_GATEWAY = None
_BUY_RE = re.compile(r"\b(?:buy|buying|purchase|purchasing)\b", re.IGNORECASE)
_SELL_RE = re.compile(r"\b(?:sell|selling)\b", re.IGNORECASE)
_USD_NOTIONAL_RE = re.compile(
    r"(?:\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)|"
    r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:usd|dollars?))",
    re.IGNORECASE,
)


class MoltGridXDEXCatalog(CoreXDEXCatalog):
    """Core XDEX catalog with the legacy listener's refresh status output."""

    def refresh(self):
        super().refresh()
        print(self.status_text())
        return self


def resolve_asset(question, pools):
    """Legacy-compatible adapter over the mint-aware core resolver.

    Ambiguous human-facing identifiers fail closed instead of crashing the
    listener loop or silently choosing one mint.
    """
    try:
        return core_resolve_asset(question, pools)
    except AmbiguousAssetError:
        return None, []


def resolve_multiple_assets(question, pools, max_assets=4):
    """Legacy-compatible multi-asset adapter that fails closed on ambiguity."""
    try:
        return core_resolve_multiple_assets(
            question,
            pools,
            max_assets=max_assets,
        )
    except AmbiguousAssetError:
        return []


def parse_cmis_trade_context(question):
    """Parse explicit buy/sell intent and optional USD notional deterministically.

    The parser does not infer a side when both buy and sell are present. Dollar
    notional is recognized only from an explicit ``$`` amount or USD/dollars
    suffix; bare numbers are not silently treated as dollars.
    """
    text = str(question or "").strip()
    if not text:
        return None

    buy = bool(_BUY_RE.search(text))
    sell = bool(_SELL_RE.search(text))
    if buy == sell:
        return None

    trade = {
        "side": "buy" if buy else "sell",
        "chain": "x1",
    }

    match = _USD_NOTIONAL_RE.search(text)
    if match:
        raw = (match.group(1) or match.group(2) or "").replace(",", "")
        try:
            amount = Decimal(raw)
        except InvalidOperation:
            amount = None
        if amount is not None and amount > 0:
            trade["notional_usd"] = float(amount)

    return trade


def wants_cmis_pre_trade(question):
    """Return True when MoltGrid can build a deterministic pre-trade request."""
    return parse_cmis_trade_context(question) is not None


def _gateway_instance(gateway=None):
    if gateway is not None:
        return gateway

    global _CMIS_GATEWAY
    if _CMIS_GATEWAY is None:
        _CMIS_GATEWAY = CMISGateway()
    return _CMIS_GATEWAY


def build_cmis_trade_analysis(question, asset, *, gateway=None):
    """Run market, risk, and pre-trade services through the public CMIS gateway."""
    trade = parse_cmis_trade_context(question)
    if trade is None:
        return None

    asset_text = str(asset or "").strip()
    client = _gateway_instance(gateway)

    market = client.dispatch({
        "service": "market_report",
        "chain": "x1",
        "asset": asset_text,
        "params": {},
    })
    risk = client.dispatch({
        "service": "risk_check",
        "chain": "x1",
        "asset": asset_text,
        "params": {},
    })
    pre_trade = client.dispatch({
        "service": "pre_trade_check",
        "chain": "x1",
        "asset": asset_text,
        "params": {"trade": trade},
    })

    return {
        "asset_query": asset_text,
        "trade": trade,
        "market_report": market,
        "risk_check": risk,
        "pre_trade_check": pre_trade,
    }


def _service_messages(envelope):
    messages = []
    if not isinstance(envelope, Mapping):
        return messages
    for field in ("errors", "warnings"):
        records = envelope.get(field)
        if not isinstance(records, list):
            continue
        for record in records:
            if isinstance(record, Mapping):
                message = str(record.get("message") or record.get("code") or "").strip()
            else:
                message = str(record or "").strip()
            if message and message not in messages:
                messages.append(message)
    return messages


def format_cmis_pre_trade_answer(listener_module, question, asset, *, gateway=None):
    """Format one deterministic CMIS pre-trade result for MoltGrid.

    The answer deliberately separates CMIS risk findings from execution-size
    checks that are not implemented. It never turns PASS into authorization.
    """
    analysis = build_cmis_trade_analysis(question, asset, gateway=gateway)
    if analysis is None:
        return (
            "Liquidity Scout reply:\n"
            "CMIS could not determine one explicit buy or sell side from that request."
        )

    market = analysis["market_report"]
    risk = analysis["risk_check"]
    pre_trade = analysis["pre_trade_check"]
    trade = analysis["trade"]

    market_asset = market.get("asset") if isinstance(market, Mapping) else {}
    pre_asset = pre_trade.get("asset") if isinstance(pre_trade, Mapping) else {}
    identity = pre_asset if isinstance(pre_asset, Mapping) and pre_asset else market_asset
    identity = identity if isinstance(identity, Mapping) else {}
    symbol = str(identity.get("symbol") or asset or "Unknown").strip()

    lines = [
        "Liquidity Scout reply:",
        f"CMIS pre-trade analysis — {symbol}",
    ]

    side = str(trade.get("side") or "").upper()
    notional = trade.get("notional_usd")
    if notional is not None:
        lines.append(f"Proposed trade: {side} {listener_module.format_usd(notional)}")
    else:
        lines.append(f"Proposed trade: {side} — USD notional not specified")

    if isinstance(market, Mapping):
        lines.append(f"Market service: {str(market.get('status') or 'unknown').upper()}")
        data = market.get("data")
        data = data if isinstance(data, Mapping) else {}
        completeness = data.get("completeness")
        completeness = completeness if isinstance(completeness, Mapping) else {}

        price = data.get("price_usd")
        if completeness.get("price") is True and price is not None:
            lines.append(f"Verified price: {listener_module.format_usd(price)}")
        else:
            lines.append("Verified price: unavailable")

        liquidity = data.get("liquidity_usd")
        if completeness.get("liquidity") is True and liquidity is not None:
            lines.append(f"Verified asset-wide liquidity: {listener_module.format_usd(liquidity)}")
        else:
            lines.append("Verified asset-wide liquidity: unavailable or incomplete")

        volume = data.get("volume_24h_usd")
        if completeness.get("volume_24h") is True and volume is not None:
            lines.append(f"Verified 24h volume: {listener_module.format_usd(volume)}")
        else:
            lines.append("Verified 24h volume: unavailable or incomplete")

        lp_count = data.get("#LPs")
        if lp_count is None:
            lp_count = data.get("lp_count")
        if lp_count is not None:
            lines.append(f"#LPs: {lp_count}")

    risk_result = risk.get("risk") if isinstance(risk, Mapping) else None
    risk_result = risk_result if isinstance(risk_result, Mapping) else {}
    risk_recommendation = str(risk_result.get("recommendation") or "UNAVAILABLE")
    lines.append(f"CMIS risk result: {risk_recommendation}")

    confidence = risk_result.get("confidence")
    if isinstance(confidence, Mapping):
        verified = confidence.get("verified_checks")
        total = confidence.get("total_checks")
        if isinstance(verified, int) and isinstance(total, int):
            lines.append(f"Risk evidence verified: {verified}/{total} checks")

    reasons = risk_result.get("reasons")
    if isinstance(reasons, list) and reasons:
        lines.append("Risk findings:")
        for reason in reasons[:6]:
            text = str(reason or "").strip()
            if text:
                lines.append(f"• {text}")

    pre_result = pre_trade.get("risk") if isinstance(pre_trade, Mapping) else None
    pre_result = pre_result if isinstance(pre_result, Mapping) else {}
    pre_recommendation = str(pre_result.get("recommendation") or "UNAVAILABLE")
    lines.append(f"Pre-trade result: {pre_recommendation}")

    if not pre_result:
        for message in _service_messages(pre_trade)[:4]:
            lines.append(f"• {message}")

    scope = pre_result.get("assessment_scope")
    scope = scope if isinstance(scope, Mapping) else {}
    not_included = scope.get("not_yet_included")
    if isinstance(not_included, list) and not_included:
        lines.append(
            "Not yet evaluated: "
            + ", ".join(str(item).replace("_", " ") for item in not_included)
            + "."
        )

    if notional is not None:
        lines.append(
            f"The {listener_module.format_usd(notional)} notional is carried as context, "
            "but CMIS does not yet calculate whether that trade size is safe for execution."
        )

    lines.append("Analysis only. Execution authorized: NO.")
    return "\n".join(lines)


def _value_or_zero(value):
    """Preserve the v0.12 presentation contract at the integration boundary."""
    return 0 if value is None else value


def compact_asset_snapshot(listener_module, term, matches, catalog):
    """Adapt the structured market report to the legacy v0.12 snapshot shape."""
    report = build_market_report(term, matches, catalog)

    symbol = report["symbol"]
    name = report.get("name") or ""
    if symbol.upper() == "XNT":
        title = "XNT"
    else:
        title = symbol
        if name and name.upper() != symbol.upper():
            title += f" ({name})"

    safety_text = report.get("safety_grade") or "N/A"
    safety_score = report.get("safety_score")
    if safety_score is not None and safety_score > 0:
        safety_text += f" ({safety_score:g}/100)"

    # The structured service preserves holder disagreement as uncertainty.
    # The legacy listener expects an integer, so keep its historical max-pool
    # compatibility behavior here until presentation is migrated separately.
    holders = report.get("holders")
    if holders is None:
        holders = report.get("holders_observed_max")

    primary_pool = report["primary_pool"]

    return {
        "title": title,
        "symbol": symbol,
        "token_address": report.get("mint") or "",
        "price": listener_module.format_usd(
            _value_or_zero(report.get("price_usd"))
        ),
        "price_usd_value": _value_or_zero(report.get("price_usd")),
        "age": listener_module.format_age(report.get("created_at")),
        "holders": int(_value_or_zero(holders)),
        "txns24": int(_value_or_zero(report.get("transactions_24h"))),
        "vol24": _value_or_zero(report.get("volume_24h_usd")),
        "change1": _value_or_zero(report.get("price_change_1h_pct")),
        "change24": _value_or_zero(report.get("price_change_24h_pct")),
        "liquidity": _value_or_zero(report.get("liquidity_usd")),
        "primary_liquidity": _value_or_zero(primary_pool.get("liquidity_usd")),
        "pool_count": report.get("lp_count", 0),
        "market_cap": _value_or_zero(report.get("market_cap_usd_reported")),
        "fdv": _value_or_zero(report.get("fdv_usd_reported")),
        "safety": safety_text,
        "pool": primary_pool.get("pair") or "",
        "pool_address": primary_pool.get("address") or "",
        # Private integration metadata. Presentation code ignores this key;
        # verified AI context uses it to avoid compatibility zero-coercion.
        "_market_report": report,
    }


def _legacy_verified_snapshot_context(listener_module, snap, fields):
    """Preserve v0.12 context behavior for externally supplied legacy snapshots."""
    lines = [f"Token: {snap['title']}"]

    for field in fields:
        if field == "price":
            lines.append(f"Price: {snap['price']}")

        elif field == "age":
            lines.append(f"Age: {snap['age']}")

        elif field == "holders":
            lines.append(f"Holders: {snap['holders']:,}")

        elif field == "txns24":
            lines.append(f"Transactions 24h: {snap['txns24']:,}")

        elif field == "volume24":
            lines.append(
                f"Volume 24h: {listener_module.format_usd(snap['vol24'])}"
            )
            lines.append(
                f"Volume classification: {volume_activity_label(snap['vol24'])}"
            )

        elif field == "change1h":
            lines.append(f"Change 1h: {snap['change1']:+.2f}%")

        elif field == "change24h":
            lines.append(f"Change 24h: {snap['change24']:+.2f}%")
            lines.append(
                "24h price-movement classification: "
                f"{price_movement_label(snap['change24'])}"
            )

        elif field == "liquidity":
            lines.append(
                f"Liquidity: {listener_module.format_usd(snap['liquidity'])}"
            )
            lines.append(
                f"Liquidity classification: {liquidity_depth_label(snap['liquidity'])}"
            )

        elif field == "market_cap":
            lines.append(
                "Market Cap: Not verified — "
                "circulating supply unavailable from verified data"
            )

        elif field == "safety":
            lines.append(f"Tokenomics Safety: {snap['safety']}")

        elif field == "pool_address":
            lines.append(f"Pool address: {snap['pool_address'] or 'N/A'}")

    return "\n".join(lines)


def verified_snapshot_context(listener_module, snap, fields):
    """Build verified AI context from structured facts when available."""
    report = snap.get("_market_report") if isinstance(snap, dict) else None
    if isinstance(report, dict):
        return build_verified_market_context(
            report,
            fields,
            format_usd=listener_module.format_usd,
            format_age=listener_module.format_age,
        )
    return _legacy_verified_snapshot_context(listener_module, snap, fields)


def get_token_total_supply(listener_module, mint):
    """Legacy total-supply shape backed by the reusable X1 tokenomics core."""
    mint = str(mint or "").strip()
    if not mint:
        return None

    try:
        record = core_get_token_supply(
            mint,
            rpc_url=listener_module.SETTINGS.x1_rpc_url,
        )
    except (X1RPCError, ValueError) as exc:
        print(f"X1 RPC getTokenSupply failed: {exc}")
        return None

    if not isinstance(record, dict) or not record.get("supply_verified"):
        return None

    return record.get("total_supply")


def get_token_mint_info(listener_module, mint):
    """Legacy mint-info shape backed by verified reusable tokenomics facts.

    Fail closed when the mint-authority field was not actually present in the
    parsed RPC response. Public max-supply presentation must never translate an
    unavailable authority field into a false claim that minting is revoked.
    """
    mint = str(mint or "").strip()
    if not mint:
        return None

    try:
        record = core_get_mint_info(
            mint,
            rpc_url=listener_module.SETTINGS.x1_rpc_url,
        )
    except (X1RPCError, ValueError) as exc:
        print(f"X1 RPC getAccountInfo failed: {exc}")
        return None

    if not isinstance(record, dict):
        return None

    if not record.get("mint_authority_verified"):
        return None

    return {
        "mint_authority": record.get("mint_authority"),
        "freeze_authority": record.get("freeze_authority"),
        "supply": record.get("total_supply"),
        "raw_supply": record.get("raw_supply") or "",
        "decimals": (
            record.get("decimals")
            if record.get("decimals") is not None
            else 0
        ),
    }


def format_historical_comparison_answer(
    listener_module,
    question,
    term,
    matches,
    catalog,
):
    """Route recognized historical comparisons through the public CMIS gateway."""
    from liquidity_scout.integrations.moltgrid_historical_cmis import (
        format_cmis_historical_answer,
    )

    return format_cmis_historical_answer(
        listener_module,
        question,
        term,
        gateway=_gateway_instance(),
    )


def format_multi_asset_answer(listener_module, question, resolved_assets, catalog):
    """Format a multi-asset comparison through the reusable comparison service."""
    snapshots = [
        compact_asset_snapshot(listener_module, term, matches, catalog)
        for term, matches in resolved_assets
    ]
    fields = requested_asset_fields(listener_module, question)

    return format_market_comparison(
        question,
        snapshots,
        fields=fields,
        format_usd=listener_module.format_usd,
        format_field_line=lambda field, snap: format_field_line(
            listener_module,
            field,
            snap,
        ),
        include_token_addresses=core_wants_token_address(question),
    )


def requested_asset_fields(listener_module, question):
    """Adapt listener routing predicates to the pure field-selection service."""
    historical_comparison = bool(
        listener_module.history.parse_historical_comparison(question)
    )
    volume_rank = bool(listener_module.wants_volume_rank(question))
    historical_liquidity = bool(
        listener_module.wants_historical_liquidity(question)
    )
    return core_requested_asset_fields(
        question,
        historical_comparison=historical_comparison,
        volume_rank=volume_rank,
        historical_liquidity=historical_liquidity,
    )


def format_field_line(listener_module, field, snap):
    """Format a public field through reusable market and tokenomics services."""
    return core_format_field_line(
        field,
        snap,
        format_usd=listener_module.format_usd,
        get_total_supply=listener_module.get_token_total_supply,
        get_mint_info=listener_module.get_token_mint_info,
    )


def full_snapshot_lines(listener_module, snap):
    """Format the stable default public snapshot through the service layer."""
    return core_full_snapshot_lines(
        snap,
        format_usd=listener_module.format_usd,
        get_total_supply=listener_module.get_token_total_supply,
        get_mint_info=listener_module.get_token_mint_info,
    )


def _multi_asset_adapter(listener_module):
    def adapter(question, resolved_assets, catalog):
        return format_multi_asset_answer(
            listener_module,
            question,
            resolved_assets,
            catalog,
        )

    return adapter


def _historical_comparison_adapter(listener_module):
    def adapter(question, term, matches, catalog):
        return format_historical_comparison_answer(
            listener_module,
            question,
            term,
            matches,
            catalog,
        )

    return adapter


def _snapshot_adapter(listener_module):
    def adapter(term, matches, catalog):
        return compact_asset_snapshot(listener_module, term, matches, catalog)

    return adapter


def _context_adapter(listener_module):
    def adapter(snap, fields):
        return verified_snapshot_context(listener_module, snap, fields)

    return adapter


def _requested_fields_adapter(listener_module):
    def adapter(question):
        return requested_asset_fields(listener_module, question)

    return adapter


def _field_line_adapter(listener_module):
    def adapter(field, snap):
        return format_field_line(listener_module, field, snap)

    return adapter


def _full_snapshot_adapter(listener_module):
    def adapter(snap):
        return full_snapshot_lines(listener_module, snap)

    return adapter


def _total_supply_adapter(listener_module):
    def adapter(mint):
        return get_token_total_supply(listener_module, mint)

    return adapter


def _mint_info_adapter(listener_module):
    def adapter(mint):
        return get_token_mint_info(listener_module, mint)

    return adapter


def _ordinary_asset_question(listener_module, question):
    history = getattr(listener_module, "history", None)
    parse_history = getattr(history, "parse_historical_comparison", None)
    if callable(parse_history) and parse_history(question):
        return False

    wants_asset_rank = getattr(listener_module, "wants_asset_rank", None)
    if callable(wants_asset_rank) and wants_asset_rank(question):
        return False

    wants_historical_liquidity = getattr(
        listener_module,
        "wants_historical_liquidity",
        None,
    )
    if callable(wants_historical_liquidity) and wants_historical_liquidity(question):
        return False

    return True


def wire_market_core(listener_module):
    """Replace legacy globals with reusable market, tokenomics, and CMIS routes."""
    legacy_wants_asset_analysis = getattr(
        listener_module,
        "_cmis_legacy_wants_asset_analysis",
        listener_module.wants_asset_analysis,
    )
    legacy_format_asset_analysis_answer = getattr(
        listener_module,
        "_cmis_legacy_format_asset_analysis_answer",
        listener_module.format_asset_analysis_answer,
    )
    legacy_format_pool_answer = getattr(
        listener_module,
        "_cmis_legacy_format_pool_answer",
        getattr(listener_module, "format_pool_answer", None),
    )
    legacy_looks_like_general_question = getattr(
        listener_module,
        "_cmis_legacy_looks_like_general_question",
        getattr(listener_module, "looks_like_general_question", None),
    )
    listener_module._cmis_legacy_wants_asset_analysis = legacy_wants_asset_analysis
    listener_module._cmis_legacy_format_asset_analysis_answer = legacy_format_asset_analysis_answer
    if callable(legacy_format_pool_answer):
        listener_module._cmis_legacy_format_pool_answer = legacy_format_pool_answer
    if callable(legacy_looks_like_general_question):
        listener_module._cmis_legacy_looks_like_general_question = legacy_looks_like_general_question

    def routed_wants_asset_analysis(question):
        return wants_cmis_pre_trade(question) or legacy_wants_asset_analysis(question)

    def routed_looks_like_general_question(question):
        wants_global_rank = getattr(listener_module, "wants_global_xdex_ranking", None)
        if callable(wants_global_rank) and wants_global_rank(question):
            return True
        if callable(legacy_looks_like_general_question):
            return bool(legacy_looks_like_general_question(question))
        return False

    def routed_format_asset_analysis_answer(question, term, matches, catalog):
        if wants_cmis_pre_trade(question):
            print(f"CMIS Gateway: PRE-TRADE | asset: {term}")
            return format_cmis_pre_trade_answer(
                listener_module,
                question,
                term,
            )
        return legacy_format_asset_analysis_answer(question, term, matches, catalog)

    def routed_format_pool_answer(question, term, matches, catalog):
        if not _ordinary_asset_question(listener_module, question):
            return legacy_format_pool_answer(question, term, matches, catalog)
        service = cmis_asset_service(question)
        print(f"CMIS Gateway: {service.upper()} | asset: {term}")
        return format_cmis_asset_answer(
            listener_module,
            question,
            term,
            gateway=_gateway_instance(),
        )

    listener_module.XDEXCatalog = MoltGridXDEXCatalog
    listener_module.resolve_asset = resolve_asset
    listener_module.resolve_multiple_assets = resolve_multiple_assets
    listener_module.compact_asset_snapshot = _snapshot_adapter(listener_module)
    listener_module.format_multi_asset_answer = _multi_asset_adapter(listener_module)
    listener_module.format_historical_comparison_answer = _historical_comparison_adapter(listener_module)
    listener_module.liquidity_depth_label = liquidity_depth_label
    listener_module.volume_activity_label = volume_activity_label
    listener_module.price_movement_label = price_movement_label
    listener_module.verified_snapshot_context = _context_adapter(listener_module)
    listener_module.FIELD_ORDER = list(CORE_FIELD_ORDER)
    listener_module.requested_asset_fields = _requested_fields_adapter(listener_module)
    listener_module.format_field_line = _field_line_adapter(listener_module)
    listener_module.full_snapshot_lines = _full_snapshot_adapter(listener_module)
    listener_module.wants_token_address = core_wants_token_address
    listener_module.get_token_total_supply = _total_supply_adapter(listener_module)
    listener_module.get_token_mint_info = _mint_info_adapter(listener_module)
    listener_module.wants_asset_analysis = routed_wants_asset_analysis
    listener_module.format_asset_analysis_answer = routed_format_asset_analysis_answer
    if callable(legacy_looks_like_general_question):
        listener_module.looks_like_general_question = routed_looks_like_general_question
    if callable(legacy_format_pool_answer):
        listener_module.format_pool_answer = routed_format_pool_answer
    return listener_module


def load_listener():
    """Import the legacy listener and wire it to Liquidity Scout services."""
    listener = import_module("moltgrid_signal_v12_ollama")
    return wire_market_core(listener)


def main():
    listener = load_listener()
    listener.main()


if __name__ == "__main__":
    main()
