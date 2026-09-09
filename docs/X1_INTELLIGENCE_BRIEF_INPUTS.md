# X1 Intelligence Brief Inputs v1

Status: foundation-only / non-promoted  
Contract: `x1_intelligence_brief_inputs/v1`  
Issue: #635

## Purpose

Provide ROBERTA with deterministic, bounded, machine-readable X1 intelligence inputs assembled only from already accepted CMIS service responses.

CMIS owns source facts and evidence. X1 Scout preserves the accepted contract. ROBERTA owns the eventual human explanation.

This contract is not a news scraper, whole-network index, risk engine, or execution surface.

## Authority path

```text
User
  -> ROBERTA
    -> X1 Scout
      -> CMIS x1_intelligence_brief_inputs/v1
        -> accepted CMIS component services
```

No provider bypass is authorized.

## V1 supported component services

The initial fact-time-safe source set is:

- `concentration_warning_intelligence/v1`
- `large_trade_discovery/v1`
- `discovery_intelligence/v1`

Additional sources require an explicit source adapter proving which source field is the event/fact time. An envelope collection timestamp must not silently become event time.

## Request boundary

The internal composer receives:

- one or more exact canonical X1 mint subjects;
- an exact canonical UTC `window_start`;
- an exact canonical UTC `window_end`;
- an explicit requested service set;
- trusted CMIS component responses produced inside the CMIS authority boundary.

V1 window semantics:

```text
window_start <= fact_time < window_end
```

The end is exclusive. Window duration must be greater than zero and no more than 86,400 seconds.

The subject × requested-service response matrix must be complete. An unavailable component is represented by an explicit unavailable CMIS response rather than by omission or a zero value.

## Source-specific fact time

### Concentration Warning

Use the latest preserved `observations[-1].after_observed_at` fact time.

`WATCH` may map to presentation priority `persistent_warning`. `CLEAR` remains informational.

Warning level is not risk severity.

### Large-Trade Discovery

Create one brief item per accepted result using the exact ranked trade `block_time`.

The result must retain the accepted boundaries that prohibit:

- whole-X1 DEX ranking claims;
- real-world wallet-owner inference;
- whale/insider/manipulator labels;
- intent or coordination inference;
- market-wide price-impact causality;
- volume causality;
- automatic risk conclusions;
- trade recommendations.

### Discovery Intelligence

Use the most recent verified Discovery observation `fact_time_unix`.

The first verified observation remains only the first observation inside the bounded Discovery Ledger evidence. It is not token launch time, creation time, or complete-lifetime start.

Sparse Discovery observations do not prove continuous coverage or archive completeness.

## Deterministic priority

V1 supports presentation priorities:

```text
persistent_warning
large_verified_activity
new_verified_observation
informational
```

Priority determines brief ordering only.

```text
priority_is_risk_severity = false
```

Risk, where present in a source contract, remains preserved separately. Proof Score/evidence quality remains separate from risk.

## Duplicate handling

Exact duplicate component responses for the same subject/service pair are idempotently collapsed.

Conflicting component responses for the same subject/service pair fail closed.

Within Large-Trade Discovery, duplicate transaction signatures fail closed.

Brief items use deterministic content identities so identical replay produces identical output.

## Coverage contract

Every composed response records:

- requested subject count;
- resolved exact subject count;
- requested/evaluated service classes;
- partial service classes;
- unavailable service classes;
- error/ambiguous service classes;
- duplicate exact component responses collapsed;
- included item count;
- outside-window item count;
- exact window start/end;
- earliest/latest included fact time;
- `complete_x1_ecosystem_coverage_verified=false`.

An empty item set means only:

> no supported verified brief item fell inside this exact requested subject/service/window scope.

It must never be promoted to:

> nothing happened on X1.

Missing source coverage, subjects, services, values, or evidence are never zero-filled.

## Promotion boundary

This foundation does not register a public CMIS runtime service and does not authorize X1 Scout reliance.

Until a separate promotion gate is accepted:

```text
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

ROBERTA #412 remains downstream and must not treat this foundation as a callable capability until that promotion is explicit.
