"""Evidence-bound CMIS Phase 11 intelligence conclusions.

This module attaches already-built CMIS Evidence Receipts and their exact
recomputed Proof Scores to validated read-only intelligence facts. It does not
upgrade risk, infer behavior, promote provider assertions, or create a public
Scout service.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
import hashlib
import json
import re
from typing import Any

from liquidity_scout.cmis.concentration import build_top_account_concentration
from liquidity_scout.cmis.intelligence_history import build_history_observation
from liquidity_scout.cmis.proof_score import build_proof_score
from liquidity_scout.cmis.wallet_activity import (
    build_wallet_activity_observation,
    summarize_wallet_activity,
)


SCHEMA_VERSION = 1
CONCLUSION_TYPES = frozenset(
    {
        "top_account_concentration",
        "top_account_concentration_change",
        "wallet_activity_observation",
        "wallet_activity_summary",
        "history_observation",
        "historical_comparison",
    }
)
_RECEIPT_RE = re.compile(r"^er_[0-9a-f]{64}$")
_ALLOWED_EVIDENCE_CLASSES = frozenset(
    {"source_record", "reported_observation", "verifier_observation"}
)
_WALLET_VERIFICATION_FIELDS = (
    "wallet_identity_verified",
    "asset_identity_verified",
    "transaction_identity_verified",
    "amount_verified",
    "transfer_direction_verified",
    "trade_direction_verified",
    "lp_action_verified",
    "deployer_identity_verified",
    "token_account_ownership_verified",
    "quote_value_verified",
    "counterparty_verified",
)


def _text(name: str, value: Any, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    text = value.strip()
    if not text:
        if required:
            raise ValueError(f"{name} is required")
        return None
    return text


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _content_id(prefix: str, value: Mapping[str, Any]) -> str:
    return prefix + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _decimal_normalized(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("decimal value must be finite")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _canonical_z_datetime(name: str, value: Any) -> datetime:
    text = _text(name, value, required=True)
    assert text is not None
    if not text.endswith("Z"):
        raise ValueError(f"{name} must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{name} must be a canonical timestamp") from exc
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != text:
        raise ValueError(f"{name} must be canonical UTC")
    return parsed


def _validate_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        raise TypeError("evidence_receipt must be a mapping")
    record = deepcopy(dict(receipt))
    if record.get("schema_version") != 1:
        raise ValueError("unsupported evidence receipt schema")
    receipt_id = _text("receipt_id", record.get("receipt_id"), required=True)
    assert receipt_id is not None
    if not _RECEIPT_RE.fullmatch(receipt_id):
        raise ValueError("evidence receipt id is not content-addressed")
    for field in ("chain", "service", "service_status"):
        _text(f"evidence_receipt.{field}", record.get(field), required=True)
    if record.get("risk_included_in_proof") is not False:
        raise ValueError("evidence receipt must keep risk outside proof")

    verification = record.get("verification")
    if not isinstance(verification, Mapping):
        raise ValueError("evidence receipt verification object is required")
    if verification.get("provider_assertion_promoted") is not False:
        raise ValueError("provider assertions must not be promoted")
    independently_verified = verification.get("independently_verified")
    if independently_verified is not None and not isinstance(independently_verified, bool):
        raise ValueError("receipt independently_verified must be true, false, or null")

    sources = record.get("sources")
    if not isinstance(sources, list):
        raise ValueError("evidence receipt sources must be a list")
    for index, source in enumerate(sources):
        if not isinstance(source, Mapping):
            raise ValueError(f"evidence receipt sources[{index}] must be an object")
        evidence_class = source.get("evidence_class")
        if evidence_class not in _ALLOWED_EVIDENCE_CLASSES:
            raise ValueError(f"unsupported evidence_class: {evidence_class!r}")

    expected_id = _content_id(
        "er_", {key: value for key, value in record.items() if key != "receipt_id"}
    )
    if receipt_id != expected_id:
        raise ValueError("evidence receipt content-addressed id mismatch")
    return record


def _validate_proof_score(
    receipt: Mapping[str, Any], proof_score: Mapping[str, Any]
) -> dict[str, Any]:
    if not isinstance(proof_score, Mapping):
        raise TypeError("proof_score must be a mapping")
    expected = build_proof_score(receipt)
    supplied = deepcopy(dict(proof_score))
    if supplied != expected:
        raise ValueError("proof_score does not match the deterministic receipt score")
    if supplied.get("risk_considered") is not False or supplied.get("risk_separate") is not True:
        raise ValueError("proof score must remain separate from risk")
    return supplied


def _fraction(value: Any, *, name: str, signed: bool = False) -> Fraction:
    if not isinstance(value, Mapping) or set(value) != {"numerator", "denominator"}:
        raise ValueError(f"{name} must be an exact ratio object")
    try:
        numerator = int(value["numerator"])
        denominator = int(value["denominator"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain integer numerator/denominator") from exc
    if str(numerator) != str(value["numerator"]) or str(denominator) != str(value["denominator"]):
        raise ValueError(f"{name} must use canonical integer strings")
    if denominator <= 0:
        raise ValueError(f"{name}.denominator must be positive")
    if not signed and numerator < 0:
        raise ValueError(f"{name}.numerator must be non-negative")
    return Fraction(numerator, denominator)


def _fraction_decimal(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = 50
        return format(Decimal(value.numerator) / Decimal(value.denominator), "f")


def _validate_concentration(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise TypeError("concentration conclusion must be a mapping")
    supplied = deepcopy(dict(record))
    if supplied.get("identity_verified") is not True:
        raise ValueError("concentration conclusion requires verified identity")
    rebuilt = build_top_account_concentration(
        chain=supplied.get("chain"),
        asset_id=supplied.get("asset_id"),
        source=supplied.get("source"),
        supply_raw=supplied.get("supply_raw"),
        supply_decimals=supplied.get("decimals"),
        requested_account_limit=supplied.get("requested_account_limit"),
        accounts=supplied.get("accounts"),
        supply_identity_verified=True,
        account_identity_verified=True,
    )
    if rebuilt != supplied:
        raise ValueError("concentration conclusion is inconsistent with its deterministic contract")
    return rebuilt


def _validate_concentration_change(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise TypeError("concentration change conclusion must be a mapping")
    supplied = deepcopy(dict(record))
    if supplied.get("schema") != "cmis_top_account_concentration_change.v1":
        raise ValueError("unsupported concentration change schema")
    for field in ("chain", "asset_id", "source", "scope"):
        _text(field, supplied.get(field), required=True)
    if supplied.get("scope") != "observed_top_token_accounts":
        raise ValueError("unsupported concentration change scope")
    if supplied.get("identity_verified") is not True:
        raise ValueError("concentration change identity_verified must be true")
    for field in (
        "scope_complete",
        "holder_semantics_verified",
        "beneficial_owner_identity_verified",
        "behavioral_interpretation_verified",
        "cmis_promotable",
    ):
        if supplied.get(field) is not False:
            raise ValueError(f"concentration change {field} must remain false")

    try:
        requested_limit = int(supplied.get("requested_account_limit"))
        observed_count = int(supplied.get("observed_account_count"))
    except (TypeError, ValueError) as exc:
        raise ValueError("concentration change top-N fields must be integers") from exc
    if requested_limit <= 0 or observed_count <= 0 or observed_count > requested_limit:
        raise ValueError("concentration change top-N fields are inconsistent")

    before = _fraction(supplied.get("before_share_exact"), name="before_share_exact")
    after = _fraction(supplied.get("after_share_exact"), name="after_share_exact")
    delta = _fraction(supplied.get("delta_share_exact"), name="delta_share_exact", signed=True)
    if before > 1 or after > 1 or delta != after - before:
        raise ValueError("concentration change exact ratios are inconsistent")
    expected_direction = "INCREASE" if delta > 0 else "DECREASE" if delta < 0 else "NO_CHANGE"
    if supplied.get("direction") != expected_direction:
        raise ValueError("concentration change direction is inconsistent")
    expected_presentations = {
        "before_share": _fraction_decimal(before),
        "after_share": _fraction_decimal(after),
        "delta_share": _fraction_decimal(delta),
        "delta_bps": _fraction_decimal(delta * 10000),
    }
    for field, expected in expected_presentations.items():
        if supplied.get(field) != expected:
            raise ValueError(f"concentration change {field} is inconsistent")

    before_time = _canonical_z_datetime(
        "before_observed_at", supplied.get("before_observed_at")
    )
    after_time = _canonical_z_datetime(
        "after_observed_at", supplied.get("after_observed_at")
    )
    if after_time <= before_time:
        raise ValueError("concentration change observation times are not ordered")
    return supplied


def _validate_wallet_observation(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise TypeError("wallet activity observation must be a mapping")
    supplied = deepcopy(dict(record))
    verification = supplied.get("verification")
    if not isinstance(verification, Mapping) or set(verification) != set(_WALLET_VERIFICATION_FIELDS):
        raise ValueError("wallet activity verification object is invalid")
    activity = supplied.get("activity_type")
    rebuilt = build_wallet_activity_observation(
        chain=supplied.get("chain"),
        wallet=supplied.get("wallet"),
        activity_type=activity,
        transaction_signature=supplied.get("transaction_signature"),
        observed_at=supplied.get("observed_at"),
        source=supplied.get("source"),
        verification_method=supplied.get("verification_method"),
        evidence_scope=supplied.get("evidence_scope"),
        asset_id=supplied.get("asset_id"),
        block_slot=supplied.get("block_slot"),
        asset_amount=None if activity == "BALANCE_CHANGE" else supplied.get("asset_amount"),
        asset_unit=supplied.get("asset_unit"),
        quote_value=supplied.get("quote_value"),
        quote_unit=supplied.get("quote_unit"),
        counterparty=supplied.get("counterparty"),
        deployer_id=supplied.get("deployer_id"),
        token_account=supplied.get("token_account"),
        balance_before=supplied.get("balance_before"),
        balance_after=supplied.get("balance_after"),
        limitations=supplied.get("limitations"),
        **{name: verification.get(name) for name in _WALLET_VERIFICATION_FIELDS},
    )
    if rebuilt != supplied:
        raise ValueError("wallet activity observation is inconsistent with its deterministic contract")
    return rebuilt


def _validate_wallet_summary(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise TypeError("wallet activity summary must be a mapping")
    supplied = deepcopy(dict(record))
    rebuilt = summarize_wallet_activity(
        chain=supplied.get("chain"),
        wallet=supplied.get("wallet"),
        observations=supplied.get("observations"),
    )
    if rebuilt != supplied:
        raise ValueError("wallet activity summary is inconsistent with its deterministic contract")
    return rebuilt


def _validate_history_observation(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise TypeError("history observation must be a mapping")
    supplied = deepcopy(dict(record))
    rebuilt = build_history_observation(
        chain=supplied.get("chain"),
        category=supplied.get("category"),
        subject_id=supplied.get("subject_id"),
        metric=supplied.get("metric"),
        value=supplied.get("value"),
        unit=supplied.get("unit"),
        observed_at=supplied.get("observed_at"),
        source=supplied.get("source"),
        verification_method=supplied.get("verification_method"),
        evidence_scope=supplied.get("evidence_scope"),
        block_slot=supplied.get("block_slot"),
        identity_verified=supplied.get("identity_verified"),
        semantics_verified=supplied.get("semantics_verified"),
        freshness_verified=supplied.get("freshness_verified"),
        scope_complete=supplied.get("scope_complete"),
        evidence_receipt_id=supplied.get("evidence_receipt_id"),
        proof_strength=supplied.get("proof_strength"),
        proof_percent=supplied.get("proof_percent"),
        proof_score_method=supplied.get("proof_score_method"),
        exact_ratio=supplied.get("exact_ratio"),
        limitations=supplied.get("limitations"),
    )
    if rebuilt != supplied:
        raise ValueError("history observation is inconsistent with its deterministic contract")
    return rebuilt


def _validate_historical_comparison(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise TypeError("historical comparison must be a mapping")
    supplied = deepcopy(dict(record))
    if supplied.get("status") != "OBSERVED_CHANGE":
        raise ValueError("evidence attachment currently requires an OBSERVED_CHANGE comparison")
    for field in (
        "continuous_coverage_proven",
        "archival_completeness_proven",
        "interpolation_performed",
        "missing_samples_filled",
    ):
        if supplied.get(field) is not False:
            raise ValueError(f"historical comparison {field} must remain false")
    first = _validate_history_observation(supplied.get("first_observation"))
    last = _validate_history_observation(supplied.get("last_observation"))
    for field in (
        "chain",
        "category",
        "subject_id",
        "metric",
        "unit",
        "evidence_scope",
        "source",
        "verification_method",
    ):
        if first.get(field) != last.get(field):
            raise ValueError(f"historical comparison has incompatible {field}")
    if last["observed_at_epoch"] <= first["observed_at_epoch"]:
        raise ValueError("historical comparison observation times are not ordered")
    if supplied.get("sample_count", 0) < 2:
        raise ValueError("historical comparison requires at least two samples")

    first_ratio = first.get("exact_ratio")
    last_ratio = last.get("exact_ratio")
    if (first_ratio is None) != (last_ratio is None):
        raise ValueError("historical comparison representation mismatch")
    if first_ratio is not None:
        before = _fraction(first_ratio, name="first.exact_ratio")
        after = _fraction(last_ratio, name="last.exact_ratio")
        delta = after - before
        exact_delta = {
            "numerator": str(delta.numerator),
            "denominator": str(delta.denominator),
        }
        absolute = _fraction_decimal(delta)
        percent = None if before == 0 else _fraction_decimal((delta / before) * 100)
        if supplied.get("exact_ratio_change") != exact_delta:
            raise ValueError("historical comparison exact ratio change is inconsistent")
    else:
        try:
            before_decimal = Decimal(first["value"])
            after_decimal = Decimal(last["value"])
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("historical comparison values are invalid") from exc
        if not before_decimal.is_finite() or not after_decimal.is_finite():
            raise ValueError("historical comparison values are invalid")
        delta_decimal = after_decimal - before_decimal
        absolute = _decimal_normalized(delta_decimal)
        percent = (
            None
            if before_decimal == 0
            else _decimal_normalized((delta_decimal / before_decimal) * Decimal(100))
        )
        if supplied.get("exact_ratio_change") is not None:
            raise ValueError("non-ratio historical comparison cannot claim exact ratio change")
    if supplied.get("absolute_change") != absolute or supplied.get("percent_change") != percent:
        raise ValueError("historical comparison change values are inconsistent")
    window = supplied.get("observed_window")
    if (
        not isinstance(window, Mapping)
        or window.get("start") != first["observed_at"]
        or window.get("end") != last["observed_at"]
    ):
        raise ValueError("historical comparison observed window is inconsistent")
    return supplied


def _validated_conclusion(
    conclusion_type: str, conclusion: Mapping[str, Any]
) -> dict[str, Any]:
    validators = {
        "top_account_concentration": _validate_concentration,
        "top_account_concentration_change": _validate_concentration_change,
        "wallet_activity_observation": _validate_wallet_observation,
        "wallet_activity_summary": _validate_wallet_summary,
        "history_observation": _validate_history_observation,
        "historical_comparison": _validate_historical_comparison,
    }
    return validators[conclusion_type](conclusion)


def _conclusion_bindings(
    conclusion_type: str, conclusion: Mapping[str, Any]
) -> tuple[str, set[str], set[str]]:
    if conclusion_type in {
        "top_account_concentration",
        "top_account_concentration_change",
    }:
        return (
            conclusion["chain"].lower(),
            {conclusion["source"]},
            {conclusion["asset_id"]},
        )
    if conclusion_type == "wallet_activity_observation":
        return (
            conclusion["chain"].lower(),
            {conclusion["source"]},
            {conclusion["asset_id"]},
        )
    if conclusion_type == "wallet_activity_summary":
        assets = {item["asset_id"] for item in conclusion["observations"]}
        return conclusion["chain"].lower(), set(conclusion["sources"]), assets
    if conclusion_type == "history_observation":
        assets = (
            set()
            if conclusion["category"] == "wallet"
            else {conclusion["subject_id"]}
        )
        return conclusion["chain"].lower(), {conclusion["source"]}, assets
    first = conclusion["first_observation"]
    assets = set() if first["category"] == "wallet" else {first["subject_id"]}
    return first["chain"].lower(), {first["source"]}, assets


def build_intelligence_evidence_bundle(
    *,
    conclusion_type: Any,
    conclusion: Mapping[str, Any],
    evidence_bundles: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind validated evidence receipts/proof scores to one exact conclusion.

    Evidence coverage is fail-closed: every conclusion source and every asset
    identity that can be deterministically extracted from the conclusion must be
    represented by the supplied receipts. The resulting bundle remains
    explicitly unpromoted for downstream Scout reliance.
    """

    type_text = _text("conclusion_type", conclusion_type, required=True)
    assert type_text is not None
    if type_text not in CONCLUSION_TYPES:
        raise ValueError(f"unsupported conclusion_type: {type_text!r}")
    if isinstance(evidence_bundles, (str, bytes, bytearray)) or not isinstance(
        evidence_bundles, Sequence
    ):
        raise TypeError("evidence_bundles must be a sequence")
    if not evidence_bundles:
        raise ValueError("at least one evidence bundle is required")
    if len(evidence_bundles) > 64:
        raise ValueError("evidence_bundles exceeds the bounded maximum of 64")

    safe_conclusion = _validated_conclusion(type_text, conclusion)
    chain, conclusion_sources, conclusion_assets = _conclusion_bindings(
        type_text, safe_conclusion
    )

    normalized_bundles: list[dict[str, Any]] = []
    seen_receipts: set[str] = set()
    receipt_sources: set[str] = set()
    receipt_assets: set[str] = set()
    source_records: list[dict[str, Any]] = []
    reported_observations: list[dict[str, Any]] = []
    verifier_observations: list[dict[str, Any]] = []
    independently_verified = False

    for index, bundle in enumerate(evidence_bundles):
        if not isinstance(bundle, Mapping):
            raise TypeError(f"evidence_bundles[{index}] must be a mapping")
        if set(bundle) != {"evidence_receipt", "proof_score"}:
            raise ValueError(
                "each evidence bundle must contain only evidence_receipt and proof_score"
            )
        receipt = _validate_receipt(bundle["evidence_receipt"])
        proof = _validate_proof_score(receipt, bundle["proof_score"])
        if receipt["chain"].lower() != chain:
            raise ValueError("evidence receipt chain does not match the conclusion")
        receipt_id = receipt["receipt_id"]
        if receipt_id in seen_receipts:
            raise ValueError("duplicate evidence receipt")
        seen_receipts.add(receipt_id)

        for source in receipt["sources"]:
            source_name = source.get("source")
            if isinstance(source_name, str) and source_name.strip():
                receipt_sources.add(source_name.strip())
            evidence_class = source["evidence_class"]
            copied = deepcopy(dict(source))
            if evidence_class == "source_record":
                source_records.append(copied)
            elif evidence_class == "reported_observation":
                reported_observations.append(copied)
            elif evidence_class == "verifier_observation":
                verifier_observations.append(copied)

        asset = receipt.get("asset")
        if isinstance(asset, Mapping):
            for field in ("canonical_id", "mint", "address"):
                value = asset.get(field)
                if isinstance(value, str) and value.strip():
                    receipt_assets.add(value.strip())
        verification = receipt["verification"]
        independently_verified = (
            independently_verified
            or verification["independently_verified"] is True
        )
        normalized_bundles.append(
            {"evidence_receipt": receipt, "proof_score": proof}
        )

    missing_sources = sorted(conclusion_sources - receipt_sources)
    if missing_sources:
        raise ValueError(
            f"evidence receipts do not cover conclusion sources: {missing_sources!r}"
        )
    missing_assets = sorted(conclusion_assets - receipt_assets)
    if missing_assets:
        raise ValueError(
            f"evidence receipts do not cover conclusion assets: {missing_assets!r}"
        )

    if (
        type_text == "history_observation"
        and safe_conclusion.get("evidence_receipt_id") is not None
    ):
        embedded_id = safe_conclusion["evidence_receipt_id"]
        matching = [
            item
            for item in normalized_bundles
            if item["evidence_receipt"]["receipt_id"] == embedded_id
        ]
        if len(matching) != 1:
            raise ValueError(
                "history observation evidence_receipt_id is not present exactly once"
            )
        embedded = matching[0]["proof_score"]
        expected_percent = _decimal_normalized(
            Decimal(str(embedded["proof_percent"]))
        )
        if safe_conclusion.get("proof_strength") != embedded["proof_strength"]:
            raise ValueError(
                "history observation proof_strength does not match attached proof"
            )
        if safe_conclusion.get("proof_percent") != expected_percent:
            raise ValueError(
                "history observation proof_percent does not match attached proof"
            )
        if safe_conclusion.get("proof_score_method") != embedded["method"]:
            raise ValueError(
                "history observation proof_score_method does not match attached proof"
            )

    conclusion_fingerprint = _content_id("ic_", safe_conclusion)
    base = {
        "schema_version": SCHEMA_VERSION,
        "conclusion_type": type_text,
        "conclusion_fingerprint": conclusion_fingerprint,
        "conclusion": safe_conclusion,
        "evidence_bundles": normalized_bundles,
        "binding": {
            "chain_verified": True,
            "source_coverage_verified": True,
            "asset_coverage_verified": True if conclusion_assets else None,
            "independent_verification_present": independently_verified,
            "conclusion_sources": sorted(conclusion_sources),
            "conclusion_assets": sorted(conclusion_assets),
        },
        "source_classes": {
            "source_records": source_records,
            "reported_observations": reported_observations,
            "verifier_observations": verifier_observations,
        },
        "proof_strength_separate_from_risk": True,
        "risk_reinterpreted": False,
        "behavioral_interpretation_added": False,
        "provider_assertion_promoted": False,
        "scout_reliance_promoted": False,
        "public_service_promoted": False,
        "execution_authorized": False,
    }
    return {"intelligence_evidence_id": _content_id("ie_", base), **base}


__all__ = [
    "CONCLUSION_TYPES",
    "SCHEMA_VERSION",
    "build_intelligence_evidence_bundle",
]
