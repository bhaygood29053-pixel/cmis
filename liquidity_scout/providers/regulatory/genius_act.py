"""Live primary-source producer for GENIUS Act Regulatory Evidence v1.

This producer is deliberately narrow. It fetches a CMIS-owned registry of
authoritative U.S. government sources, verifies source identity markers, derives
only the bounded rulemaking state encoded by those sources, and emits one
canonical regulatory_evidence/v1 record for the exact X1 USDC.X mint.

It never decides issuer/asset legal compliance, gives legal advice, promotes
risk, or authorizes execution.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from html import unescape
import re
from typing import Any
from urllib.request import Request, urlopen

from liquidity_scout.services.cmis_regulatory_evidence import (
    validate_regulatory_evidence_record,
)


X1_USDCX_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
LAW_ID = "Public Law 119-27"
JURISDICTION = "US"
FRAMEWORK = "GENIUS Act"

DEFAULT_HTTP_TIMEOUT_SECONDS = 20.0
DEFAULT_USER_AGENT = "CMIS-Regulatory-Evidence/1.0"

GENIUS_ACT_SOURCE_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "source_id": "genius-act-public-law-119-27",
        "authority_class": "primary_law",
        "publisher": "U.S. Government Publishing Office",
        "title": "Public Law 119-27 — GENIUS Act",
        "url": "https://www.govinfo.gov/app/details/PLAW-119publ27",
        "published_on": "2025-07-18",
        "required_markers": (
            "Public Law 119-27",
            "Guiding and Establishing National Innovation",
            "July 18, 2025",
        ),
    },
    {
        "source_id": "treasury-genius-state-similarity-nprm-2026-04-01",
        "authority_class": "primary_regulator",
        "publisher": "U.S. Department of the Treasury",
        "title": (
            "Treasury Seeks Public Comment on GENIUS Act Notice of Proposed "
            "Rulemaking Concerning State-Level Regulatory Regimes"
        ),
        "url": "https://home.treasury.gov/news/press-releases/sb0428",
        "published_on": "2026-04-01",
        "rulemaking_status": "proposed_rule",
        "required_markers": (
            "GENIUS Act",
            "notice of proposed rulemaking",
            "April 1, 2026",
        ),
    },
    {
        "source_id": "treasury-genius-illicit-finance-nprm-2026-04-08",
        "authority_class": "primary_regulator",
        "publisher": "U.S. Department of the Treasury",
        "title": (
            "Treasury Proposes Rule to Implement the GENIUS Act’s "
            "Requirements to Counter Illicit Finance"
        ),
        "url": "https://home.treasury.gov/news/press-releases/sb0435",
        "published_on": "2026-04-08",
        "rulemaking_status": "proposed_rule",
        "required_markers": (
            "GENIUS Act",
            "proposed rule",
            "April 8, 2026",
        ),
    },
    {
        "source_id": "treasury-genius-section-3-nprm-2026-08-17",
        "authority_class": "primary_regulator",
        "publisher": "U.S. Department of the Treasury",
        "title": "Treasury Seeks Public Comment on GENIUS Act Proposed Rulemaking",
        "url": "https://home.treasury.gov/news/press-releases/sb0605",
        "published_on": "2026-08-17",
        "rulemaking_status": "proposed_rule",
        "required_markers": (
            "GENIUS Act",
            "Notice of Proposed Rulemaking",
            "August 17, 2026",
        ),
    },
)

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


class RegulatoryEvidenceProductionError(RuntimeError):
    """Live primary-source evidence could not satisfy the CMIS contract."""


def _normalized_text(value: str) -> str:
    return _SPACE_RE.sub(" ", unescape(_TAG_RE.sub(" ", value))).strip()


def _default_fetcher(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
        },
        method="GET",
    )
    with urlopen(request, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS) as response:
        body = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    return body.decode(charset, errors="replace")


def _now(clock: Callable[[], Any] | None) -> datetime:
    value = datetime.now(timezone.utc) if clock is None else clock()
    if isinstance(value, bool):
        raise RegulatoryEvidenceProductionError("clock must return time")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if not isinstance(value, datetime):
        raise RegulatoryEvidenceProductionError(
            "clock must return datetime or numeric epoch"
        )
    if value.tzinfo is None:
        raise RegulatoryEvidenceProductionError(
            "clock datetime must include timezone"
        )
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _source_specs(
    source_registry: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    raw = GENIUS_ACT_SOURCE_REGISTRY if source_registry is None else source_registry
    if (
        not isinstance(raw, Sequence)
        or isinstance(raw, (str, bytes, bytearray))
        or not raw
    ):
        raise RegulatoryEvidenceProductionError(
            "regulatory source registry must be a non-empty sequence"
        )

    result: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise RegulatoryEvidenceProductionError(
                f"source_registry[{index}] must be a mapping"
            )
        spec = deepcopy(dict(item))
        url = str(spec.get("url") or "").strip()
        if not url.startswith("https://"):
            raise RegulatoryEvidenceProductionError(
                f"source_registry[{index}].url must use https"
            )
        if spec.get("authority_class") not in {"primary_law", "primary_regulator"}:
            raise RegulatoryEvidenceProductionError(
                f"source_registry[{index}] authority_class is unsupported"
            )
        markers = spec.get("required_markers")
        if (
            not isinstance(markers, Sequence)
            or isinstance(markers, (str, bytes, bytearray))
            or not markers
            or any(not isinstance(marker, str) or not marker.strip() for marker in markers)
        ):
            raise RegulatoryEvidenceProductionError(
                f"source_registry[{index}] requires source identity markers"
            )
        published_on = str(spec.get("published_on") or "").strip()
        try:
            datetime.fromisoformat(published_on)
        except ValueError as exc:
            raise RegulatoryEvidenceProductionError(
                f"source_registry[{index}].published_on must be ISO date"
            ) from exc
        if spec["authority_class"] == "primary_regulator":
            status = spec.get("rulemaking_status")
            if status not in {"proposed_rule", "final_rule", "effective"}:
                raise RegulatoryEvidenceProductionError(
                    f"source_registry[{index}] regulator status is unsupported"
                )
        result.append(spec)

    if not any(item["authority_class"] == "primary_law" for item in result):
        raise RegulatoryEvidenceProductionError(
            "regulatory source registry requires primary law"
        )
    if not any(item["authority_class"] == "primary_regulator" for item in result):
        raise RegulatoryEvidenceProductionError(
            "regulatory source registry requires primary regulator evidence"
        )
    return result


def _verify_source_content(
    spec: Mapping[str, Any],
    body: Any,
) -> None:
    if not isinstance(body, str) or not body.strip():
        raise RegulatoryEvidenceProductionError(
            f"empty source body: {spec.get('source_id')}"
        )
    normalized = _normalized_text(body).casefold()
    missing = [
        marker
        for marker in spec["required_markers"]
        if str(marker).casefold() not in normalized
    ]
    if missing:
        raise RegulatoryEvidenceProductionError(
            "authoritative source identity markers missing for "
            f"{spec.get('source_id')}: {missing!r}"
        )


def _current_regulatory_state(
    regulator_specs: Sequence[Mapping[str, Any]],
    *,
    as_of: datetime,
) -> dict[str, Any]:
    latest = max(
        regulator_specs,
        key=lambda item: (
            str(item["published_on"]),
            str(item.get("source_id") or ""),
        ),
    )
    status = str(latest["rulemaking_status"])
    final_rule_verified = status in {"final_rule", "effective"}
    effective_now_verified = status == "effective"

    effective_on = latest.get("effective_on")
    if status == "final_rule" and effective_on is not None:
        try:
            effective_date = datetime.fromisoformat(str(effective_on)).date()
        except ValueError as exc:
            raise RegulatoryEvidenceProductionError(
                "regulator effective_on must be ISO date"
            ) from exc
        if as_of.date() >= effective_date:
            status = "effective"
            effective_now_verified = True

    return {
        "rulemaking_status": status,
        "final_rule_verified": final_rule_verified,
        "effective_now_verified": effective_now_verified,
        "status_as_of": _timestamp(as_of),
    }


def produce_genius_act_usdcx_regulatory_record(
    *,
    fetcher: Callable[[str], str] | None = None,
    clock: Callable[[], Any] | None = None,
    source_registry: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Fetch authoritative sources and return one validated canonical record."""

    specs = _source_specs(source_registry)
    fetch = _default_fetcher if fetcher is None else fetcher
    if not callable(fetch):
        raise RegulatoryEvidenceProductionError("fetcher must be callable")

    as_of = _now(clock)
    retrieved_at = _timestamp(as_of)
    sources: list[dict[str, Any]] = []
    regulator_specs: list[dict[str, Any]] = []

    for spec in specs:
        try:
            body = fetch(str(spec["url"]))
        except Exception as exc:
            raise RegulatoryEvidenceProductionError(
                "authoritative source fetch failed for "
                f"{spec.get('source_id')}: {type(exc).__name__}: {exc}"
            ) from exc
        _verify_source_content(spec, body)

        source = {
            "authority_class": spec["authority_class"],
            "publisher": str(spec["publisher"]),
            "title": str(spec["title"]),
            "url": str(spec["url"]),
            "published_on": str(spec["published_on"]),
            "retrieved_at": retrieved_at,
        }
        sources.append(source)
        if spec["authority_class"] == "primary_regulator":
            regulator_specs.append(spec)

    state = _current_regulatory_state(regulator_specs, as_of=as_of)
    record = {
        "service": "regulatory_evidence",
        "contract": "regulatory_evidence/v1",
        "jurisdiction": JURISDICTION,
        "framework": FRAMEWORK,
        "legal": {
            "law_id": LAW_ID,
            "enacted_on": "2025-07-18",
            "status": "enacted",
            "effective_date_rule": {
                "type": "earlier_of",
                "fixed_date": "2027-01-18",
                "days_after_final_rules": 120,
            },
        },
        "current_regulatory_state": state,
        "asset": {
            "asset_id": "USDC.X",
            "chain": "x1",
            "asset_id_kind": "mint",
            "chain_scoped_asset_id": X1_USDCX_MINT,
            "representation_type": "bridged",
            "underlying_asset": "USDC",
            "bridge_dependency": True,
            "custody_dependency": True,
        },
        "issuer": {
            "name": "Circle",
            "identity_status": "PROVIDER_REPORTED",
        },
        "applicability": "INSUFFICIENT_EVIDENCE",
        "sources": sources,
        "retrieved_at": retrieved_at,
        "limitations": [
            (
                "Current rulemaking state is bounded to the verified CMIS primary-"
                "source registry and may require a registry update when a new "
                "authoritative implementation source is published."
            ),
            "Issuer licensing and compliance are not established by this record.",
            (
                "Underlying USDC evidence does not establish USDC.X bridge, custody, "
                "liquidity, or redemption safety."
            ),
        ],
        "read_only": True,
        "compliance_conclusion_authorized": False,
        "compliance_conclusion": None,
        "execution_authorized": False,
    }

    try:
        return validate_regulatory_evidence_record(
            record,
            expected_jurisdiction=JURISDICTION,
            expected_framework=FRAMEWORK,
            expected_asset="USDC.X",
        )
    except Exception as exc:
        raise RegulatoryEvidenceProductionError(
            f"produced regulatory record failed canonical validation: {exc}"
        ) from exc


__all__ = [
    "DEFAULT_HTTP_TIMEOUT_SECONDS",
    "DEFAULT_USER_AGENT",
    "FRAMEWORK",
    "GENIUS_ACT_SOURCE_REGISTRY",
    "JURISDICTION",
    "LAW_ID",
    "RegulatoryEvidenceProductionError",
    "X1_USDCX_MINT",
    "produce_genius_act_usdcx_regulatory_record",
]
