"""MoltGrid entrypoint wired to reusable Liquidity Scout services.

This is a migration seam for the current v0.12 listener. It keeps the legacy
MoltGrid transport, AI routing, RPC transport, and conversation state intact
while replacing market catalog/resolution, deterministic snapshot construction,
verified market-analysis context, and public market presentation at runtime.

Run with:
    python -m liquidity_scout.integrations.moltgrid
"""

from importlib import import_module

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



def format_historical_comparison_answer(
    listener_module,
    question,
    term,
    matches,
    catalog,
):
    """Format historical comparison through verified reusable service policy."""
    snapshot = compact_asset_snapshot(listener_module, term, matches, catalog)
    return core_format_historical_comparison(
        question,
        snapshot,
        history_backend=listener_module.history,
        get_total_supply=listener_module.get_token_total_supply,
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
    """Format a public field while leaving RPC transport in the listener."""
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


def wire_market_core(listener_module):
    """Replace legacy market globals with reusable core/service implementations."""
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
