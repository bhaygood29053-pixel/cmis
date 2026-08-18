# CMIS Phase 10 Completion — Solana Provider Read-Only Foundation

Status: **COMPLETE**

Completion date: 2026-08-18

Tracker: GitHub Issue #78

Final production-composition PR: #158

Merge commit: `c3228c036430efff5efe645b57f5eb6dba6be6c1`

## Purpose

Phase 10 added Solana beneath the existing Cross-Chain Market Intelligence Service (CMIS) contracts without duplicating the deterministic market-intelligence stack or weakening X1 behavior.

The accepted architecture remains:

```text
Roberta / Chain Scout / Liquidity Scout
                 |
                 v
                CMIS
                 |
        +--------+--------+
        |                 |
        v                 v
    X1 provider      Solana provider
```

CMIS remains the deterministic evidence authority. Reasoning/orchestration layers may explain CMIS results but do not become the source of live chain truth.

## Accepted Phase 10 capabilities

### Provider boundary

- explicit chain/provider selection;
- no silent Solana → X1 fallback;
- unconfigured/unsupported capabilities fail closed;
- X1 behavior preserved through the shared runtime contract.

### Canonical Solana RPC foundation

Accepted read-only canonical facts include:

- exact mint-account identity through `getAccountInfo(jsonParsed)`;
- SPL Token and Token-2022 program identity checks;
- mint initialization state;
- decimals;
- total supply through `getTokenSupply`;
- mint authority;
- freeze authority;
- RPC slot/context provenance;
- optional `getTokenLargestAccounts` concentration evidence.

`getTokenLargestAccounts` is explicitly **largest-token-account concentration evidence only**. It must never be relabeled as total holder, wallet, or beneficial-owner coverage.

### Market/indexed source adapters

Read-only source adapters now exist for:

- Jupiter Price V3 / Tokens V2;
- Helius DAS indexed evidence;
- DEX Screener Solana token-pair observations.

Provider labels such as verified/organic/safe remain provider evidence, not final CMIS truth.

### Cross-source verification

Phase 10 includes deterministic evidence gates for:

- Jupiter ↔ DEX Screener price comparison with an explicit deployment tolerance;
- canonical Solana RPC ↔ Helius indexed supply comparison with an explicit maximum slot-lag policy.

Agreement does not automatically erase freshness or scope limitations. Conflict remains explicit conflict, and insufficient evidence remains insufficient evidence.

### Promoted CMIS service surface

The accepted Solana service boundary is intentionally narrower than X1.

Available in bounded/partial read-only form where prerequisites are configured:

- `asset_lookup`;
- `tokenomics`;
- `market_report`;
- `risk_check`;
- narrow `historical_compare` for same-source Jupiter price observations.

Still unavailable for Solana unless separately implemented/promoted:

- ranking;
- pre-trade execution analysis;
- trade verification;
- verified asset-wide activity;
- persisted verification-evidence lookup as a Solana service surface;
- signing/execution capabilities.

The authoritative machine-readable eligibility rules are documented in [`CMIS_CAPABILITY_CONTRACT.md`](./CMIS_CAPABILITY_CONTRACT.md).

## Historical evidence

Phase 10 added a provenance-safe Solana observation ledger that preserves:

- chain;
- exact mint;
- metric;
- source;
- scope;
- subject identity;
- pair dimensions where applicable;
- provider block/slot provenance;
- CMIS collection time;
- identity/semantics/freshness flags.

The first accepted Solana historical comparison is deliberately narrow: same-mint, same-source Jupiter Price V3 history under an explicit deployment-owned distance policy.

## Production runtime configuration

Solana is **disabled by default**.

Production enablement is environment-owned through:

```text
CMIS_SOLANA_PROVIDER_ENABLED=1
SOLANA_RPC_URL=
JUPITER_API_KEY=
HELIUS_API_KEY=
CMIS_SOLANA_PRICE_MAX_RELATIVE_DIFFERENCE=
CMIS_SOLANA_SUPPLY_MAX_INDEX_SLOT_LAG=
CMIS_SOLANA_HISTORY_MAX_DISTANCE_SECONDS=
CMIS_SOLANA_OBSERVATION_DB=
```

When enabled:

- canonical Solana RPC is constructed read-only;
- DEX Screener pair evidence is available as a public read-only source;
- a provenance-safe Solana observation ledger is created;
- Jupiter is constructed only when its API key is present;
- Helius is constructed only when its API key is present;
- dependent services fail closed when a required source/policy is absent.

Secrets are deployment configuration only and are not accepted through external CMIS request parameters or returned as provenance.

## Acceptance evidence

Phase 10 was closed only after both acceptance gates passed on the final production-runtime change:

- Liquidity Scout deterministic/X1 regression suite — **SUCCESS** (Actions run `32097967028`);
- Solana read-only production-runtime live acceptance — **SUCCESS** (Actions run `32097967014`).

The live acceptance used a known mainnet USDC mint and exercised:

- canonical `getAccountInfo(jsonParsed)` mint/program identity;
- canonical `getTokenSupply` total supply;
- production `RuntimeCMISGateway` Solana `asset_lookup`;
- production `RuntimeCMISGateway` Solana `tokenomics`.

The first automated live attempt exposed an HTTP failure on `getTokenLargestAccounts` from Solana's shared public endpoint. That concentration-only method is not required by any promoted Phase 10 service. The required live gate therefore covers the canonical methods used by promoted services, while the full largest-account probe remains available when a dedicated RPC endpoint is configured.

## Safety boundary preserved

Phase 10 does **not** add or authorize:

- wallet custody;
- seed/private-key handling as part of CMIS intelligence;
- signing;
- transaction construction;
- simulation as an execution prerequisite;
- broadcasting;
- autonomous swaps;
- delegated execution authority;
- value movement.

Analysis capability does not imply execution authority.

## Roadmap note

`CMIS_PRODUCT_ROADMAP.md` is a long-term product/premium capability roadmap. Its numbered product sequence predates the later GitHub execution-phase numbering and should not be read as a one-to-one map to issue numbers.

The current execution milestone is unambiguous:

> **CMIS Phase 10 — Solana Provider read-only foundation: COMPLETE.**

No Phase 11 implementation is introduced by this completion record.
