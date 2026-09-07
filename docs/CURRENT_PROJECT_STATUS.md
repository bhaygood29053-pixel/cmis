# Current CMIS Project Status

Current reconciliation: **2026-09-07 09:14 America/New_York**.

## Accepted platform

- current capability contract: `1.27.0`;
- current flagship scan: `instant_x1_scan/v6`;
- universal public response freshness: `cmis_response_freshness/v1` on every CMIS response;
- Burn, Discovery, WHAT CHANGED? upstream facts, history, identity, deterministic risk, pre-trade analysis, concentration intelligence, and field-scoped freshness remain accepted under their established contracts;
- Bridge-to-XDEX utilization and cross-chain provenance are promoted for X1 Scout reliance;
- `trade_price_impact_intelligence/v1` is accepted through CMIS #498 / PR #530 + protected `cmis-core` #33;
- `large_trade_discovery/v1` is promoted through public PRs #532/#533 + protected `cmis-core` #35;
- GENIUS Act `regulatory_evidence/v1` is promoted under CMIS 1.26 through public PR #540 + protected `cmis-core` #43;
- CMIS Web Discovery remains accepted as bounded discovery below the verification boundary; X1 Agents Radio source discovery is accepted via #564 / PR #566, `x1_agents_radio_structured_discovery/v1` via #568 / PR #569, `x1_agents_radio_rpc_corroboration/v1` via #571 / PR #572, and `x1_program_upgrade_semantic_verification/v1` via #574 / PR #576. CMIS can now distinguish ordinary program activity from exact BPF Upgradeable Loader deploy/upgrade semantics and verify current ProgramData slot/authority state, while application identity/IDL semantics remain unverified and no public/Scout promotion is implied.
- Dedicated XONE/XNT Conversion Intelligence is accepted internally via #575 / PR #578, and exact Ethereum XONE identity is now accepted via #580 / PR #581 under `ethereum_xone_identity/v1`. The verified Ethereum mainnet XONE contract is `0x4DCDa2274899d9BbA3Bb6f5A852C107Dd6E4fE1c`; exact creation/deployer, runtime bytecode, and ERC-20 metadata were proven by live multi-RPC evidence. Ethereum conversion/burn/migration semantics, X1 XNT issuance/vesting events, and cross-chain correlation remain unverified, with no public/Scout promotion and `execution_authorized=false`.

## Latest accepted live gate

### Ethereum XONE Exact Identity v1

**ACCEPTED.** Ethereum XONE Identity run #6 passed both deterministic and live jobs at PR #581 head `06525bdfe59e255e254901699768054156e9430b`; Liquidity Scout Tests run #1753 also passed. The live gate directly proved Ethereum mainnet chain ID, exact creation transaction/deployer, successful receipt to the exact XONE contract, 8,932-byte runtime code with SHA-256 `ad56471d77d0f1cf018de7aee79d711dc7ee8ca62154fac3f2300308763aff8e`, and ERC-20 name/symbol/decimals `XONE` / `XONE` / 18. Tenderly and Blast satisfied the required two-provider quorum, and 1RPC independently returned a third matching proof. PR #581 merged as `3e0373d15517fd3a0233c180341199e1a20c021c`; Issue #580 closed completed.

This gate verifies identity only. It does not prove a XONE→XNT conversion ratio or mechanism, burn/lock/snapshot requirements, XNT issuance/vesting/claim state, or Ethereum→X1 correlation.

### Previous accepted protected live gate — cmis-core #41 Large-Trade → #498 handoff

**ACCEPTED.** The exact dedicated live workflow passed on run #7 at protected head `9ff63bcac15d9bd7f46868489f444508ed126c06`. PR #41 then merged as `f659f53f3d565bd5886dfae3e1a12370100cddc9`, and Issue #40 closed completed.

The accepted proof covers:

`Large-Trade ranking -> returned result -> protected materializer -> exact wallet/direction/execution evidence -> public #498 composition -> stored tpi evidence -> rebuilt ready handoff -> same evidence resolves through #498`.

The proof remains provider-scoped, pool-local, read-only, and fail-closed. It does not establish real-world wallet identity, whole-market causality, every-X1-DEX coverage, automatic risk conclusions, recommendations, or execution authority.

## Regulatory state

CMIS owns the current freshness-aware regulatory evidence service. It preserves primary-law/regulator provenance, rulemaking state, jurisdiction/framework scope, exact X1 asset identity, and evidence freshness.

It does **not** authorize:

- legal advice;
- COMPLIANT / NON_COMPLIANT labels;
- automatic token/issuer risk conclusions;
- execution.

ROBERTA adoption remains a separate upstream consumer gate.

## Website / ROBERTA dependency

ROBERTA regulatory adoption is accepted end to end through public PR #368, protected `roberta-core` PR #69, and reconciliation PR #369. Website claims must remain synchronized to accepted ROBERTA capabilities and preserve X1 Scout → CMIS as the authority path.

## Parallel work

Provider-gap research, X1Scroll fallback qualification, delayed-departure research, Theo transport work, and historical provider investigations remain parallel unless a separately accepted roadmap gate promotes them.

`execution_authorized=false`
