# Solana cross-source price policy

Status: **accepted deployment-policy boundary**

Tracker: GitHub Issue #252

## Decision

CMIS does **not** define a default numerical tolerance for the Solana Jupiter Price V3 ↔ DEX Screener price cross-check.

The deployment/operator owns `CMIS_SOLANA_PRICE_MAX_RELATIVE_DIFFERENCE` and must set it explicitly as a unitless fraction in `[0, 1]` before Jupiter/DEX Screener market evidence is queried by the promoted Solana `market_report` path.

Examples such as `0.01` or `0.03` in deterministic tests are fixtures that exercise agreement/conflict behavior. They are not production recommendations and must not be promoted into a hidden readiness default.

## Why there is no CMIS default

The accepted source contracts do not publish one shared numerical error bound that would justify a universal Jupiter-versus-DEX-Screener tolerance.

- Jupiter Price V3 is a heuristics-based Solana price source that may suppress a price when its own reliability checks do not pass.
- DEX Screener exposes pair-scoped `priceUsd` observations. CMIS preserves those observations per eligible base-token pair and does not select a preferred pair or aggregate them into one canonical asset price.
- The two source contracts do not establish one shared observation timestamp/scope. Numerical agreement therefore does not establish a verified current canonical price.

CMIS must not convert a test fixture, one live observation, or model judgment into a production policy.

Source references:

- Jupiter Price API: https://developers.jup.ag/docs/price
- Jupiter Price V3 reference: https://developers.jup.ag/docs/api-reference/price
- DEX Screener API reference: https://docs.dexscreener.com/api/reference

## Deterministic contract

`CMIS_SOLANA_PRICE_MAX_RELATIVE_DIFFERENCE` is interpreted as a fraction:

```text
0.01 = 1%
0.03 = 3%
1    = 100%
```

CMIS validates the configured value in `[0, 1]` inclusive. Missing or invalid policy fails closed.

The verifier computes the symmetric relative difference for Jupiter versus every eligible DEX Screener base-token pair:

```text
abs(jupiter_price - pair_price) / max(abs(jupiter_price), abs(pair_price))
```

Structural validation has precedence over numerical classification. If any DEX Screener pair record is malformed, lacks a pair address, or duplicates another pair address, the verifier returns `INSUFFICIENT_EVIDENCE` with `dexscreener_pair_contract_invalid` and does not emit `AGREEMENT` or `CONFLICT`, even when another structurally valid pair could otherwise be compared.

For structurally valid pair lists, the evidence status is:

- `AGREEMENT` only when every eligible comparison is within the configured tolerance;
- `CONFLICT` when at least one eligible comparison is outside the configured tolerance;
- `INSUFFICIENT_EVIDENCE` when no eligible comparison remains or another accepted source/identity/price precondition cannot support a comparison.

CMIS does not average pair prices, cherry-pick an agreeing pair, or allow callers to override the deployment policy through request parameters.

## Promotion boundary

Even `AGREEMENT` remains non-promotable under the current contract:

```text
cmis_promotable = false
freshness_verified = false
observation_scope_verified = false
price_verified = false
```

The market report may therefore be `partial` while preserving the Jupiter source value and pair-scoped observations. The deterministic Solana risk path does not treat price agreement as verified current-price risk evidence. A conflict is preserved as context but is not assigned a new severity without a separately accepted calibrated risk rule.

## Production-readiness configuration

Before the configured Solana market/risk readiness lane can run, the deployment must explicitly set:

```text
CMIS_SOLANA_PROVIDER_ENABLED=1
SOLANA_RPC_URL=<deployment RPC>
JUPITER_API_KEY=<deployment secret>
CMIS_SOLANA_PRICE_MAX_RELATIVE_DIFFERENCE=<operator-owned value in [0,1]>
```

DEX Screener is a public read-only source and is composed automatically when the Solana provider is enabled.

The chosen numerical value is a deployment policy decision. It should be recorded in the operator's configuration/change record with the reason for that choice. CMIS validates and applies the value deterministically but does not choose it.

A secret-free runtime check is available through `build_solana_runtime_dependencies()`; readiness requires `price_crosscheck_policy_configured: True` before expecting the market/risk provider path to execute.

## Test coverage

The accepted contract is covered by:

- `tests/test_solana_market_verification.py`
  - explicit tolerance required;
  - `[0,1]` validation;
  - all-pair agreement;
  - one-outlier conflict;
  - structural-invalid pair-contract precedence over numerical conflict;
  - insufficient-evidence and exact-mint/price-subject boundaries;
  - non-promotion despite numerical agreement.
- `tests/test_cmis_solana_market_report.py`
  - missing policy fails closed before market providers are queried;
  - callers cannot supply a request-level tolerance;
  - invalid deployment tolerance is rejected;
  - agreement/conflict remain partial/non-verified.
- `tests/test_cmis_solana_runtime_config.py`
  - policy is environment/deployment-owned;
  - configuration status exposes only policy presence and never secrets.
- `tests/test_cmis_solana_risk_check.py`
  - agreement/conflict are preserved as context;
  - price cross-check does not become verified risk-price evidence.

## Safety boundary

This policy does not authorize Solana pre-trade, route selection, transaction construction, signing, broadcasting, custody, swaps, or autonomous value movement.

CMIS verifies and classifies the configured read-only evidence. It does not choose the operator's market-policy tolerance and it does not execute trades.
