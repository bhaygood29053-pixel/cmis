"""CMIS v1.4.7 — cross-window vault-pair family attribution.

v1.4.6 intentionally treated a change in the single leading candidate pair
across 1h/6h/24h as a conflict. Live AGI/XNT evidence showed why that guard is
useful: a shorter window and a 24h window can select different leading vault
pairs even though both may be recurring candidates.

v1.4.7 does not weaken that guard. Instead it changes the question:

    Are there multiple recurring vault-pair families for the same pool?

For every candidate pair exposed by v1.4.3, this phase:
- tracks exact family identity across nested 1h/6h/24h windows;
- records rank/coverage/opposite-flow consistency per window;
- normalizes dominant BUY/SELL fingerprints to structural identity by removing
  only execution scope;
- reports structural-layout conflicts per family/direction;
- explains leading-pair changes only when the changing leaders are themselves
  recurrent family identities.

This phase does NOT prove that a recurring family is canonical, legitimate, or
the unique pool vault mapping. Exact pool-leg semantics remain unpromoted.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.directional_vault_fingerprints import (
    correlate_directional_vault_pairs,
)

VERSION = "1.4.7"
WINDOWS = (
    ("1h", 3600),
    ("6h", 21600),
    ("24h", 86400),
)


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _family_key(pair: Mapping[str, Any]):
    values = (
        _text(pair.get("asset_account")),
        _text(pair.get("counter_account")),
        _text(pair.get("counter_mint")),
        _text(pair.get("shared_owner")),
    )
    return values if all(values) else None


def _family_dict(key):
    if key is None:
        return None
    return {
        "asset_account": key[0],
        "counter_account": key[1],
        "counter_mint": key[2],
        "shared_owner": key[3],
    }


def _structural_key(fingerprint: Mapping[str, Any] | None):
    if not isinstance(fingerprint, Mapping):
        return None
    program = _text(fingerprint.get("program_id"))
    if not program:
        return None
    return (
        program,
        fingerprint.get("pool_position"),
        fingerprint.get("asset_position"),
        fingerprint.get("counter_position"),
    )


def _structural_dict(key):
    if key is None:
        return None
    return {
        "program_id": key[0],
        "pool_position": key[1],
        "asset_position": key[2],
        "counter_position": key[3],
    }


def _direction_observation(pair: Mapping[str, Any], direction: str):
    field = "buy_fingerprint" if direction == "BUY" else "sell_fingerprint"
    raw = pair.get(field)
    raw = raw if isinstance(raw, Mapping) else {}
    full = raw.get("dominant_instruction_fingerprint")
    full = full if isinstance(full, Mapping) else None
    structural = _structural_key(full)
    return {
        "direction": direction,
        "transaction_count": int(raw.get("transaction_count") or 0),
        "sufficient_sample": raw.get("sufficient_sample") is True,
        "full_fingerprint_stable": raw.get("fingerprint_stable") is True,
        "dominant_full_fingerprint": (
            dict(full) if isinstance(full, Mapping) else None
        ),
        "dominant_structural_fingerprint": _structural_dict(structural),
        "_structural_key": structural,
    }


def _candidate_pairs(report: Mapping[str, Any]):
    pairs = report.get("candidate_pairs")
    if not isinstance(pairs, Sequence) or isinstance(pairs, (str, bytes)):
        return []
    return [dict(item) for item in pairs if isinstance(item, Mapping)]


def evaluate_vault_pair_family_attribution(
    *,
    pool_address: str,
    asset_mint: str,
    end_epoch: float,
    pair: str | None = None,
    rpc_url: str | None = None,
    page_size: int = 1000,
    max_signatures: int = 5000,
    min_occurrences: int = 2,
    min_coverage_ratio: float = 0.50,
    min_opposite_direction_ratio: float = 0.95,
    min_direction_occurrences: int = 2,
    min_fingerprint_ratio: float = 0.95,
    min_dominance_margin: float = 0.10,
    min_family_evidence_windows: int = 2,
    min_family_occurrences: int = 2,
    min_family_opposite_direction_ratio: float = 0.95,
    directional_provider: Callable[..., Mapping[str, Any]] = (
        correlate_directional_vault_pairs
    ),
) -> dict[str, Any]:
    """Attribute all candidate pair identities across 1h/6h/24h."""

    if (
        isinstance(min_family_evidence_windows, bool)
        or not isinstance(min_family_evidence_windows, int)
        or min_family_evidence_windows < 2
        or min_family_evidence_windows > len(WINDOWS)
    ):
        raise ValueError("min_family_evidence_windows must be 2 or 3")
    if (
        isinstance(min_family_occurrences, bool)
        or not isinstance(min_family_occurrences, int)
        or min_family_occurrences < 1
    ):
        raise ValueError("min_family_occurrences must be an integer >= 1")
    if (
        isinstance(min_family_opposite_direction_ratio, bool)
        or not isinstance(
            min_family_opposite_direction_ratio, (int, float)
        )
        or not 0 <= min_family_opposite_direction_ratio <= 1
    ):
        raise ValueError(
            "min_family_opposite_direction_ratio must be between 0 and 1"
        )

    try:
        end_epoch = float(end_epoch)
    except (TypeError, ValueError):
        raise ValueError("end_epoch must be numeric")
    if end_epoch < 0:
        raise ValueError("end_epoch must be non-negative")

    family_windows: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    window_summaries = []
    leading_keys = []
    all_ranges_proven = True

    for label, duration in WINDOWS:
        kwargs = {
            "pool_address": pool_address,
            "asset_mint": asset_mint,
            "start_epoch": end_epoch - duration,
            "end_epoch": end_epoch,
            "pair": pair,
            "page_size": page_size,
            "max_signatures": max_signatures,
            "min_occurrences": min_occurrences,
            "min_coverage_ratio": min_coverage_ratio,
            "min_opposite_direction_ratio": min_opposite_direction_ratio,
            "min_direction_occurrences": min_direction_occurrences,
            "min_fingerprint_ratio": min_fingerprint_ratio,
            "min_dominance_margin": min_dominance_margin,
        }
        if rpc_url is not None:
            kwargs["rpc_url"] = rpc_url

        raw = directional_provider(**kwargs)
        report = dict(raw) if isinstance(raw, Mapping) else {}
        range_proven = report.get("range_proven") is True
        integrity_verified = report.get("integrity_verified") is True
        all_ranges_proven = (
            all_ranges_proven and range_proven and integrity_verified
        )

        pairs = _candidate_pairs(report)
        leading_key = _family_key(pairs[0]) if pairs else None
        if leading_key is not None:
            leading_keys.append((label, leading_key))

        window_candidates = []
        for rank, candidate in enumerate(pairs, start=1):
            key = _family_key(candidate)
            if key is None:
                continue
            occurrence_count = int(
                candidate.get("transaction_occurrence_count") or 0
            )
            opposite_ratio = float(
                candidate.get("opposite_direction_ratio") or 0.0
            )
            qualifying_family_evidence = bool(
                occurrence_count >= min_family_occurrences
                and opposite_ratio
                >= min_family_opposite_direction_ratio
            )

            buy = _direction_observation(candidate, "BUY")
            sell = _direction_observation(candidate, "SELL")
            observation = {
                "window": label,
                "rank": rank,
                "is_leading_candidate": rank == 1,
                "transaction_occurrence_count": occurrence_count,
                "recognized_pool_instruction_transaction_ratio": float(
                    candidate.get(
                        "recognized_pool_instruction_transaction_ratio"
                    )
                    or 0.0
                ),
                "opposite_direction_ratio": opposite_ratio,
                "stable_directional_pair_candidate": (
                    candidate.get(
                        "stable_directional_pair_candidate"
                    ) is True
                ),
                "stable_structural_directional_pair_candidate": (
                    candidate.get(
                        "stable_structural_directional_pair_candidate"
                    ) is True
                ),
                "qualifying_family_evidence": qualifying_family_evidence,
                "buy": buy,
                "sell": sell,
            }
            family_windows[key].append(observation)
            window_candidates.append(
                {
                    "family": _family_dict(key),
                    "rank": rank,
                    "is_leading_candidate": rank == 1,
                    "transaction_occurrence_count": occurrence_count,
                    "recognized_pool_instruction_transaction_ratio": (
                        observation[
                            "recognized_pool_instruction_transaction_ratio"
                        ]
                    ),
                    "opposite_direction_ratio": opposite_ratio,
                    "stable_directional_pair_candidate": (
                        observation["stable_directional_pair_candidate"]
                    ),
                    "stable_structural_directional_pair_candidate": (
                        observation[
                            "stable_structural_directional_pair_candidate"
                        ]
                    ),
                    "qualifying_family_evidence": (
                        qualifying_family_evidence
                    ),
                }
            )

        summary = report.get("summary")
        summary = summary if isinstance(summary, Mapping) else {}
        window_summaries.append(
            {
                "label": label,
                "duration_seconds": duration,
                "start_epoch": end_epoch - duration,
                "end_epoch": end_epoch,
                "range_proven": range_proven,
                "integrity_verified": integrity_verified,
                "candidate_pair_count": len(pairs),
                "stable_directional_pair_candidate_count": int(
                    summary.get(
                        "stable_directional_pair_candidate_count"
                    )
                    or 0
                ),
                "leading_family": _family_dict(leading_key),
                "candidates": window_candidates,
            }
        )

    families = []
    for key, observations in family_windows.items():
        qualifying = [
            item
            for item in observations
            if item["qualifying_family_evidence"]
        ]
        qualifying_windows = {
            item["window"] for item in qualifying
        }
        recurrent = (
            len(qualifying_windows) >= min_family_evidence_windows
        )

        directions = []
        any_structural_conflict = False
        for direction in ("BUY", "SELL"):
            evidence = []
            for item in observations:
                row = item[direction.lower()]
                structural_key = row["_structural_key"]
                if (
                    row["transaction_count"] > 0
                    and row["sufficient_sample"]
                    and structural_key is not None
                ):
                    evidence.append(
                        {
                            "window": item["window"],
                            "transaction_count": row[
                                "transaction_count"
                            ],
                            "full_fingerprint_stable": row[
                                "full_fingerprint_stable"
                            ],
                            "dominant_full_fingerprint": row[
                                "dominant_full_fingerprint"
                            ],
                            "dominant_structural_fingerprint": row[
                                "dominant_structural_fingerprint"
                            ],
                            "_structural_key": structural_key,
                        }
                    )

            structural_keys = {
                item["_structural_key"] for item in evidence
            }
            structural_conflict = len(structural_keys) > 1
            any_structural_conflict = (
                any_structural_conflict or structural_conflict
            )
            stable_key = (
                next(iter(structural_keys))
                if len(structural_keys) == 1
                else None
            )
            directions.append(
                {
                    "direction": direction,
                    "evidence_window_count": len(evidence),
                    "structural_layout_conflict_observed": (
                        structural_conflict
                    ),
                    "cross_window_dominant_structural_layout_consistent": (
                        len(evidence) >= min_family_evidence_windows
                        and not structural_conflict
                        and stable_key is not None
                    ),
                    "stable_dominant_structural_fingerprint": (
                        _structural_dict(stable_key)
                    ),
                    "observations": [
                        {
                            k: v
                            for k, v in item.items()
                            if k != "_structural_key"
                        }
                        for item in evidence
                    ],
                }
            )

        leader_window_count = sum(
            1 for item in observations if item["is_leading_candidate"]
        )
        families.append(
            {
                "family": _family_dict(key),
                "observed_window_count": len(
                    {item["window"] for item in observations}
                ),
                "qualifying_evidence_window_count": len(
                    qualifying_windows
                ),
                "min_family_evidence_windows": (
                    min_family_evidence_windows
                ),
                "recurrent_pair_family_observed": recurrent,
                "leader_window_count": leader_window_count,
                "structural_layout_conflict_observed": (
                    any_structural_conflict
                ),
                "directions": directions,
                "window_observations": [
                    {
                        k: (
                            {
                                kk: vv
                                for kk, vv in v.items()
                                if kk != "_structural_key"
                            }
                            if k in {"buy", "sell"}
                            else v
                        )
                        for k, v in item.items()
                    }
                    for item in observations
                ],
                "canonical_family_proven": False,
                "canonical_family_promoted": False,
            }
        )

    families.sort(
        key=lambda item: (
            item["recurrent_pair_family_observed"],
            item["leader_window_count"],
            item["qualifying_evidence_window_count"],
            item["observed_window_count"],
        ),
        reverse=True,
    )

    recurrent_families = [
        item
        for item in families
        if item["recurrent_pair_family_observed"]
    ]
    recurrent_keys = {
        _family_key(item["family"]) for item in recurrent_families
    }

    distinct_leading_keys = {key for _label, key in leading_keys}
    leading_family_changes = len(distinct_leading_keys) > 1
    leading_change_explained = bool(
        leading_family_changes
        and distinct_leading_keys
        and distinct_leading_keys.issubset(recurrent_keys)
    )
    family_structural_conflict = any(
        item["structural_layout_conflict_observed"]
        for item in recurrent_families
    )
    multiple_recurrent = len(recurrent_families) > 1

    status = (
        "multiple_recurrent_pair_families_observed"
        if (
            all_ranges_proven
            and multiple_recurrent
            and not family_structural_conflict
        )
        else "recurrent_pair_family_observed"
        if (
            all_ranges_proven
            and recurrent_families
            and not family_structural_conflict
        )
        else "family_structural_conflict_observed"
        if family_structural_conflict
        else "insufficient_family_evidence"
    )

    return {
        "service": "vault_pair_family_attribution",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "pair": pair,
        "asset_mint": asset_mint,
        "status": status,
        "shared_end_epoch": end_epoch,
        "thresholds": {
            "min_family_evidence_windows": min_family_evidence_windows,
            "min_family_occurrences": min_family_occurrences,
            "min_family_opposite_direction_ratio": (
                min_family_opposite_direction_ratio
            ),
        },
        "windows": window_summaries,
        "leading_family_history": [
            {
                "window": label,
                "family": _family_dict(key),
            }
            for label, key in leading_keys
        ],
        "families": families,
        "summary": {
            "all_requested_window_ranges_proven": all_ranges_proven,
            "recurrent_pair_family_count": len(recurrent_families),
            "multiple_recurrent_pair_families_observed": (
                multiple_recurrent
            ),
            "leading_family_changes_across_windows": (
                leading_family_changes
            ),
            "leading_change_explained_by_recurrent_families": (
                leading_change_explained
            ),
            "recurrent_family_structural_conflict_observed": (
                family_structural_conflict
            ),
            "vault_pair_family_model_observed": bool(
                recurrent_families
                and all_ranges_proven
                and not family_structural_conflict
            ),
            "vault_pair_family_model_promoted": False,
            "canonical_vault_mapping_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "interpretation": (
                "v1.4.7 attributes every observed candidate vault-pair "
                "identity across nested 1h, 6h, and 24h windows. A changing "
                "single-window leader is explained only when each changing "
                "leader independently recurs as a qualifying family. "
                "Dominant BUY/SELL layouts are compared structurally with "
                "execution scope excluded from layout identity. Recurrence "
                "does not prove canonical vault truth."
            ),
        },
    }


__all__ = [
    "VERSION",
    "WINDOWS",
    "evaluate_vault_pair_family_attribution",
]
