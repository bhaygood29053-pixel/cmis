# CMIS Pre-Trade Trade-Size Policy

Status: **accepted and active read-only analysis policy**

This policy is analysis only. It does not authorize transaction construction, signing, simulation for execution, broadcasting, custody, swaps, or autonomous value movement.

## Policy identity

- Policy contract: `pre_trade_liquidity` v2.0
- Production X1 operating policy: `cmis_x1_trade_size_conservative` v1.0
- Generic service-core policy: `cmis_pre_trade_unconfigured` v1.0
- Input ratio: `verified requested USD notional / verified asset-wide USD liquidity`

The reusable service core remains uncalibrated: it can calculate a verified notional/liquidity ratio without silently converting that ratio into a warning or block. At the production X1 CMIS gateway, an omitted `params.pre_trade_policy` selects the named conservative X1 profile. An explicitly supplied policy remains authoritative and does not silently inherit production thresholds.

The X1 thresholds are deliberate CMIS policy choices, not universal market truth. Every evaluated result preserves the policy name/version, thresholds, verified liquidity, requested notional, and calculated ratio used.

## Default production X1 classification bands

| Ratio to verified asset-wide liquidity | Classification | Analytical action |
| --- | --- | --- |
| `< 2%` | `LOW` | `PASS` unless another pre-trade/risk gate is worse |
| `>= 2% and < 5%` | `MODERATE` | `PASS` unless another gate is worse |
| `>= 5% and < 10%` | `HIGH` | `WARN` |
| `>= 10%` | `VERY_HIGH` | `BLOCK` |

Custom thresholds remain validated and auditable. They cannot weaken missing-evidence gates by manufacturing liquidity or execution estimates.

## Fail-closed liquidity rules

A sized trade is not classified from a provider number merely because the number exists. The upstream CMIS risk result must mark liquidity as verified.

If liquidity is missing, conflicting, stale under the applicable evidence contract, or unverified, the ratio/classification are withheld and the production X1 policy fails closed.

A zero verified-liquidity result also blocks; CMIS never substitutes a fake denominator.

BUY and SELL use the same market-size ratio policy. That ratio says how large the proposed notional is relative to verified market liquidity. It does **not** claim buy-side and sell-side route depth are identical.

## Route-evidence boundary

CMIS now has a hardened **internal route-evidence seam** for selected pre-trade capabilities. This is narrower than a generic quote or reserve payload.

Route evidence can be used only when all accepted gates pass, including:

- exact token-in mint;
- exact token-out mint;
- exact pool;
- exact AMM config;
- accepted CMIS route-evidence producer/source;
- explicit freshness window and valid evaluation time;
- accepted capability semantic;
- exact unit contract;
- exact accepted proof basis;
- valid capability-specific value shape.

The public X1 HTTP gateway does not accept arbitrary caller-supplied `route_evidence` as a way to promote unverified claims.

### Price impact

Route-scoped price impact may be usable when independently verified against the exact accepted pool/config/reserve evidence and the route-evidence contract passes.

This does not establish global route quality or asset-wide execution behavior.

### Fees

For an exact accepted scope, the route-evidence seam may expose a bounded fee record containing only:

- independently verified AMM trade-fee rate; and
- the matching bounded historical execution-model fee rate.

The currently accepted pinned XENCAT/native-XNT historical execution evidence strongly corroborates the 2800-ppm / 0.28% execution model for its tested sequence.

The XDEX backend's observed 3000-ppm / 0.30% zero-slippage quote behavior is **not** inserted into the execution-fee record. Its private implementation/business reason remains unavailable, and it must not be mislabeled as a hidden router/platform/protocol fee.

### Slippage

XDEX quote `slippage` percent units and minimum-received-style behavior have been verified/corroborated for tested quote scope, but **quote slippage tolerance is not expected execution slippage**.

Expected execution slippage remains unavailable unless a separately accepted route-execution observation contract proves it.

### Still unavailable unless separately proven

- route quality / route optimality;
- fill quality;
- bridge dependency where route representation is not proven;
- transaction simulation;
- generic execution quality;
- universal XDEX execution semantics.

Missing execution evidence is never reported as zero. If a caller explicitly requires a capability that remains unavailable, pre-trade fails closed.

## Example using the reported AGI liquidity scenario

With verified asset-wide liquidity of `$3,380`:

- `$50 / $3,380 = 1.479...%` → `LOW`;
- `$150 / $3,380 = 4.437...%` → `MODERATE`;
- `$250 / $3,380 = 7.396...%` → `HIGH` / `WARN`;
- `$500 / $3,380 = 14.792...%` → `VERY_HIGH` / `BLOCK`;
- `$2,000 / $3,380 = 59.171...%` → `VERY_HIGH` / `BLOCK`.

These classifications apply only when the liquidity observation is verified under the CMIS evidence contract. If the evidence becomes stale, conflicting, unavailable, or unverified, the numeric classification is withheld.

## Structured output for Roberta

`pre_trade_check.data.trade_size` exposes the already-computed decision basis, including:

- assessment/classification;
- evidence status;
- notional;
- notional-to-liquidity ratio;
- threshold notionals;
- policy contract/name/version;
- classification bands and warning/block ratios.

Where accepted route evidence is available, `route_analysis` / `execution_capabilities` may expose only the exact verified/bounded fields that passed their route-evidence gates. Unsupported fields remain unavailable/null.

Roberta may explain these results but must not recompute or override them.

## Provenance requirement

The upstream market/risk envelope remains responsible for source, venue/pool, observation time, evidence scope, disagreements, and verification metadata. Route evidence additionally preserves exact route identity, source, observation time, age/freshness policy, semantic, and proof basis.

Pre-trade adds deterministic policy/evidence classification. It must not erase, broaden, or strengthen upstream provenance.

## Execution boundary

Every current pre-trade result preserves the equivalent of:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` means only that the checks actually performed did not produce a warning/block. It is not a statement that a trade is safe and it is never authorization to prepare, sign, broadcast, or execute a transaction.
