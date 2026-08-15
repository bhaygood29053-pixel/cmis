import argparse
import os
from decimal import Decimal, ROUND_HALF_UP

from dotenv import load_dotenv

from liquidity_scout.market import XDEXCatalog, resolve_asset
from liquidity_scout.providers.x1.activity_scanner import (
    X1ActivityScanner,
    collect_signature_window,
    open_activity_db,
)
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, X1RPCProvider
from liquidity_scout.tokenomics import get_mint_info as core_get_mint_info
from liquidity_scout.tokenomics.activity import extract_token_events

load_dotenv()

RPC = os.getenv("X1_RPC_URL", DEFAULT_X1_RPC_URL).strip()
DB_FILE = "x1_burn_scan.db"

BASE58 = set(
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    "abcdefghijkmnopqrstuvwxyz"
)


def round_token_amount(value):
    """Round to nearest whole token; .5 and above rounds up."""
    return int(
        Decimal(str(value)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def _rpc_provider(*, retries=5):
    """Build the X1 RPC provider used by this legacy compatibility CLI."""
    return X1RPCProvider(
        rpc_url=RPC,
        retries=retries,
        timeout=30,
    )


def rpc(method, params, retries=5):
    """Compatibility RPC helper delegated to the X1 provider transport."""
    return _rpc_provider(retries=retries).request(method, params)


def looks_like_mint(value):
    value = value.strip()
    return (
        32 <= len(value) <= 50
        and all(ch in BASE58 for ch in value)
    )


def resolve_token(value, catalog=None):
    """Resolve an XDEX symbol/name or direct X1 mint without guessing identity."""
    value = str(value or "").strip()
    if not value:
        raise ValueError("Token identifier is required.")

    if looks_like_mint(value):
        return value[:8] + "...", value

    if catalog is None:
        catalog = XDEXCatalog()
        catalog.refresh()

    term, matches = resolve_asset(value, catalog.pools)
    if not matches:
        raise RuntimeError(
            f"Token '{value}' was not found in the XDEX catalog."
        )

    _pool, side, asset, _quality = matches[0]
    if side == "pool" or not isinstance(asset, dict):
        raise RuntimeError(
            f"Could not determine X1 mint address for '{value}'."
        )

    mint = str(asset.get("mint") or asset.get("address") or "").strip()
    symbol = str(asset.get("symbol") or term or value).strip().upper()
    if not mint:
        raise RuntimeError(
            f"Could not determine X1 mint address for {symbol}."
        )

    return symbol, mint


def get_token_info(mint):
    """Return burn-scanner compatibility fields from provider-backed tokenomics."""
    record = core_get_mint_info(
        mint,
        rpc_url=RPC,
        retries=5,
        timeout=30,
    )

    if not isinstance(record, dict):
        raise RuntimeError("Mint account could not be parsed.")

    decimals = record.get("decimals")
    raw_supply = record.get("raw_supply")
    if decimals is None or raw_supply is None:
        raise RuntimeError(
            "Mint account supply/decimals could not be verified."
        )

    return {
        "decimals": decimals,
        "supply": raw_supply,
        "mint_authority": record.get("mint_authority"),
        "freeze_authority": record.get("freeze_authority"),
        "mint_authority_verified": bool(
            record.get("mint_authority_verified")
        ),
        "freeze_authority_verified": bool(
            record.get("freeze_authority_verified")
        ),
    }


def get_signatures(mint, max_signatures=None):
    """Compatibility view over the provider's bounded signature selection."""
    provider = _rpc_provider()
    selection = collect_signature_window(
        provider.request,
        mint,
        max_signatures=max_signatures,
    )
    return [
        {"signature": signature, "err": None}
        for signature in selection["signatures"]
    ]


def extract_burns(tx, mint):
    """Compatibility burn-only view over the shared deterministic event parser."""
    burns = []
    for event in extract_token_events(tx, mint):
        if event.get("kind") != "burn":
            continue
        burns.append(
            {
                "location": event.get("location"),
                "type": event.get("instruction_type"),
                "raw_amount": event.get("raw_amount"),
                "authority": event.get("authority") or "",
                "account": event.get("account") or "",
                "block_time": event.get("block_time"),
            }
        )
    return burns


def fetch_transaction(signature, mint):
    """Compatibility transaction fetch delegated to the X1 RPC provider."""
    tx = _rpc_provider().request(
        "getTransaction",
        [
            signature,
            {
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 0,
            },
        ],
    )
    return signature, extract_burns(tx, mint)


def print_summary(report, symbol, mint, decimals):
    """Print the legacy burn-focused summary from the provider scan report."""
    burned = report.get("burned_tokens_observed")
    burn_events = report.get("burn_events_observed", 0)
    scanned = (report.get("coverage") or {}).get("signatures_scanned", 0)

    print()
    print("============================================")
    print(" VERIFIED X1 BURN SUMMARY")
    print("============================================")
    print(f"Token:             {symbol}")
    print(f"Mint:              {mint}")
    print(f"Decimals:          {decimals}")
    print(f"Txs in window:     {scanned:,}")
    print(f"Burn instructions: {burn_events:,}")
    if burned is None:
        print("Burned tokens:     unavailable")
    else:
        amount = Decimal(str(burned))
        print(f"Burned tokens:     {amount:,.9f} {symbol}")
        print(f"Rounded burned:    {round_token_amount(amount):,} {symbol}")
    print(f"Coverage scope:    {report.get('coverage_scope')}")
    print("Lifetime coverage: UNVERIFIED")
    print("============================================")


def scan(
    symbol,
    mint,
    decimals,
    workers,
    max_signatures,
    *,
    db_file=DB_FILE,
):
    """Run the provider-owned X1 activity scanner through the legacy CLI seam."""
    # ``workers`` remains accepted for CLI compatibility. The deterministic
    # provider scanner controls retrieval order itself and does not currently
    # expose concurrent transaction fetching.
    _ = max(1, int(workers))

    provider = _rpc_provider()
    scanner = X1ActivityScanner(provider.request)
    db = open_activity_db(db_file)
    try:
        report = scanner.scan(
            mint=mint,
            decimals=decimals,
            db=db,
            max_signatures=max_signatures,
        )
    finally:
        db.close()

    print_summary(report, symbol, mint, decimals)
    return report


def run_token_scan(
    token,
    *,
    workers=6,
    max_signatures=None,
    db_file=DB_FILE,
):
    """Resolve a token, verify mint facts, and run the X1 provider scanner."""
    symbol, mint = resolve_token(token)
    token_info = get_token_info(mint)
    decimals = token_info["decimals"]

    print()
    print("============================================")
    print(" X1 GENERIC BURN SCANNER")
    print("============================================")
    print(f"Token:            {symbol}")
    print(f"Mint:             {mint}")
    print(f"Decimals:         {decimals}")

    mint_authority = token_info["mint_authority"]
    mint_authority_verified = token_info["mint_authority_verified"]
    if not mint_authority_verified:
        mint_authority_text = "UNAVAILABLE"
    elif mint_authority is None:
        mint_authority_text = "REVOKED"
    else:
        mint_authority_text = str(mint_authority)

    print("Mint authority:   " + mint_authority_text)
    print("============================================")
    print()

    return scan(
        symbol=symbol,
        mint=mint,
        decimals=decimals,
        workers=workers,
        max_signatures=max_signatures,
        db_file=db_file,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Scan verified standard token burns for any token on X1."
    )
    parser.add_argument(
        "token",
        help="XDEX symbol such as AGI/XENCAT or an X1 mint address",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help=(
            "Compatibility option retained from the legacy scanner; "
            "provider retrieval is deterministic"
        ),
    )
    parser.add_argument(
        "--max-signatures",
        type=int,
        default=None,
        help="Only inspect this many recent signature-history entries",
    )
    args = parser.parse_args()

    run_token_scan(
        args.token,
        workers=max(1, args.workers),
        max_signatures=args.max_signatures,
    )


if __name__ == "__main__":
    main()
