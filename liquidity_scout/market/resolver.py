"""Asset and pool resolution for the XDEX catalog."""

import re
from typing import Any, Dict, Iterable, List, Optional

STOPWORDS = {
    "WHAT", "IS", "THE", "OF", "DOING", "TODAY", "PRICE", "LIQUIDITY",
    "VOLUME", "SHOW", "ME", "TELL", "ABOUT", "FIND", "HOW", "DOES", "HAVE",
    "POOL", "POOLS", "ON", "XDEX", "RIGHT", "NOW", "CURRENT", "CURRENTLY",
    "MARKET", "CAP", "HOLDERS", "SAFETY", "TOKEN", "COIN", "ASSET",
    "BUY", "SELL", "HOLD", "SIGNAL", "PLEASE", "WHATS", "WHAT'S",
}


class AmbiguousAssetError(ValueError):
    """Raised when an exact human-facing identifier maps to multiple mints."""

    def __init__(self, term: str, asset_keys: Iterable[str]):
        self.term = str(term or "").strip()
        self.asset_keys = tuple(sorted({str(key) for key in asset_keys if key}))
        joined = ", ".join(self.asset_keys) or "multiple assets"
        super().__init__(
            f"Ambiguous XDEX asset identifier '{self.term}' matches {joined}. "
            "Use the mint address or another unique identifier."
        )


def _s(value) -> str:
    return str(value or "").strip()


def _n(value, default=0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def token_fields(token: Dict[str, Any]) -> List[str]:
    if not isinstance(token, dict):
        return []
    return [
        _s(token.get("symbol")),
        _s(token.get("name")),
        _s(token.get("mint")),
        _s(token.get("address")),
    ]


def pool_address(pool: Dict[str, Any]) -> str:
    return _s(pool.get("address") or pool.get("poolAddress") or pool.get("id"))


def pair_name(pool: Dict[str, Any]) -> str:
    base = pool.get("baseToken") or {}
    quote = pool.get("quoteToken") or {}
    return f"{_s(base.get('symbol'))}/{_s(quote.get('symbol'))}"


def normalize_text(text) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", " ", _s(text)).strip()


def candidate_terms(question) -> List[str]:
    clean = normalize_text(question)
    words = [word for word in clean.split() if word]
    candidates: List[str] = []

    for size in (3, 2):
        for index in range(len(words) - size + 1):
            phrase = " ".join(words[index:index + size])
            if phrase.upper() not in STOPWORDS:
                candidates.append(phrase)

    for word in words:
        if word.upper() in STOPWORDS:
            continue
        if len(word) >= 2:
            candidates.append(word)

    seen = set()
    output = []
    for candidate in candidates:
        key = candidate.lower()
        if key not in seen:
            seen.add(key)
            output.append(candidate)
    return output


def exact_token_match(token: Dict[str, Any], query) -> bool:
    q = _s(query).lower()
    if not q:
        return False
    fields = [field.lower() for field in token_fields(token) if field]
    return q in fields


def partial_token_match(token: Dict[str, Any], query) -> bool:
    q = _s(query).lower()
    if len(q) < 3:
        return False
    fields = [field.lower() for field in token_fields(token) if field]
    return any(q in field for field in fields)


def find_matches_for_term(term, pools: Iterable[Dict[str, Any]]):
    matches = []
    term_lower = _s(term).lower()

    for pool in pools:
        base = pool.get("baseToken") or {}
        quote = pool.get("quoteToken") or {}
        address = pool_address(pool)

        if term_lower == address.lower():
            matches.append((pool, "pool", None, 100))
            continue

        if exact_token_match(base, term):
            matches.append((pool, "base", base, 90))
        elif exact_token_match(quote, term):
            matches.append((pool, "quote", quote, 90))
        elif partial_token_match(base, term):
            matches.append((pool, "base", base, 60))
        elif partial_token_match(quote, term):
            matches.append((pool, "quote", quote, 60))

    return matches


def asset_key(token: Dict[str, Any]) -> Optional[str]:
    if not isinstance(token, dict):
        return None

    mint = _s(token.get("mint") or token.get("address"))
    symbol = _s(token.get("symbol"))
    name = _s(token.get("name"))

    if mint:
        return mint
    if symbol:
        return f"symbol:{symbol.upper()}"
    if name:
        return f"name:{name.lower()}"
    return None


def _exact_match_asset_keys(matches) -> set:
    """Return distinct token identities represented by exact token matches."""
    keys = set()

    for _pool, side, asset, quality in matches:
        if quality < 90 or side == "pool" or not asset:
            continue
        key = asset_key(asset)
        if key:
            keys.add(key)

    return keys


def _reject_ambiguous_term(term, matches) -> None:
    keys = _exact_match_asset_keys(matches)
    if len(keys) > 1:
        raise AmbiguousAssetError(term, keys)


def _sort_matches(matches) -> None:
    matches.sort(
        key=lambda item: (
            item[3],
            _n(item[0].get("liquidity")),
            _n(item[0].get("volume24h")),
        ),
        reverse=True,
    )


def resolve_asset(question, pools):
    """Return one exact catalog identity; reject identifiers shared by mints."""
    for term in candidate_terms(question):
        matches = [
            match
            for match in find_matches_for_term(term, pools)
            if match[3] >= 90
        ]

        if matches:
            _reject_ambiguous_term(term, matches)
            _sort_matches(matches)
            return term, matches

    return None, []


def explicitly_requests_multiple_assets(question) -> bool:
    q = f" {_s(question).lower()} "
    return any(
        marker in q
        for marker in (
            " compare ",
            " compared ",
            " versus ",
            " vs ",
            " vs. ",
            " between ",
        )
    )


def resolve_multiple_assets(question, pools, max_assets: int = 4):
    terms = candidate_terms(question)
    found = []
    seen_assets = set()

    for term in terms:
        matches = [
            match
            for match in find_matches_for_term(term, pools)
            if match[3] >= 90
        ]
        if not matches:
            continue

        _reject_ambiguous_term(term, matches)
        _sort_matches(matches)

        pool, _side, asset, _quality = matches[0]
        if not asset:
            asset = pool.get("baseToken") or {}

        key = asset_key(asset) or f"term:{term.lower()}"
        if key in seen_assets:
            continue

        seen_assets.add(key)
        found.append((term, matches))

        if len(found) >= max_assets:
            break

    return found
