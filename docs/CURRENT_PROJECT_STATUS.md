# Current CMIS Project Status

Current reconciliation: **2026-09-07 11:19 America/New_York**.

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
- Dedicated XONE/XNT Conversion Intelligence is accepted internally through #575 / PR #578 (web discovery), #580 / PR #581 (exact Ethereum identity), #583 / PR #584 (bounded canonical events), #586 / PR #587 (burn/redeemer semantics), #589 / PR #590 (exact Ethereum candidate discovery), #592 / PR #593 (X1 XNT rule/account discovery), and #595 / PR #596 (`xone_xnt_x1_binding_discovery/v1`). Binding Discovery run #4 had 4/4 official X1 targets and 13/13 ranked X1 Report pages available but produced 0 explicit XONE/XNT conversion claims / 0 exact X1 binding candidates. That is scoped corpus evidence only, not proof of converter absence. Exact XONE→XNT account/program role binding, XNT issuance provenance, XONE-specific vesting/claim events, and cross-chain correlation remain unverified, with no public/Scout promotion and `execution_authorized=false`.

## Latest accepted live gate

### XONE/XNT X1 Binding Discovery v1

**ACCEPTED.** XONE XNT X1 Binding Discovery run #4 passed deterministic and live bounded-corpus jobs at PR #596 head `e84299c709da2ab3fbae27304eb039c0ef8e1813`; Liquidity Scout Tests run #1777 also passed. The live source gate had 4/4 official X1 targets available — X1 official, X1 Docs root, incentivized-testnet-rewards, and the X1 developer surface — plus 13/13 ranked X1 Report pages. The dedicated extractor produced 0 bounded explicit XONE/XNT conversion claims and therefore 0 exact X1/SVM binding candidates. The evidence artifact digest is `sha256:9fda946ffc0155dcf64f399a4dffc26fb35662493935e00f83c81f4e838e751b`.

The accepted interpretation is strictly scoped: this corpus did not expose an exact X1 account/program inside an explicit XONE/XNT binding statement. It does not prove no converter, claim program, allocation account, vesting account, or migration mechanism exists elsewhere. `x1_binding_identified=false`, `xnt_distribution_mechanism_identified=false`, `xnt_issuance_verified=false`, `xnt_vesting_or_unlock_verified=false`, `xone_xnt_conversion_verified=false`, `cross_chain_correlation_verified=false`, and `execution_authorized=false`. PR #596 merged as `e85a944b21aaf45cfceb428641ad5cbeb32b7e5e`; Issue #595 closed completed.

### Previous accepted live gate — X1 XNT Distribution / Vesting Mechanism Discovery v1

**ACCEPTED.** X1 XNT Distribution Mechanism Discovery run #1 passed deterministic and live official-source jobs at PR #593 head `34b3e7ac9d9d9370b38575c3a47883e351c2c5e9`; Liquidity Scout Tests run #1770 also passed. The official X1 incentivized-testnet-rewards page was retrieved as `text/markdown` and produced 17 bounded XNT mechanism claims. The live gate confirmed the current source wording around `50,000 credits = 1 XNT`, `10%`, `90%`, and `365 days` and found 0 exact 32-byte X1/SVM pubkey candidates. The evidence artifact digest is `sha256:bba687ec9235fee723c8fc945fe46f5f02e71a816418371f30630699c4c9957d`.

The accepted interpretation is narrow: CMIS can now distinguish the official validator-testnet reward/lock/vesting rules from the still-unproven XONE→XNT mechanism. The official page's lack of exact pubkeys does not prove no XNT distribution/vesting/claim account or program exists. `xnt_distribution_mechanism_identified=false`, `xnt_issuance_verified=false`, `xnt_vesting_or_unlock_verified=false`, `xone_xnt_conversion_verified=false`, `cross_chain_correlation_verified=false`, and `execution_authorized=false`. PR #593 merged as `afb752f2f1ea4084836921abc8505243b858abb5`; Issue #592 closed completed.

### Previous accepted live gate — XONE/XNT Conversion Candidate Discovery v1

**ACCEPTED.** XONE XNT Conversion Candidate Discovery run #2 passed deterministic and live jobs at PR #590 head `72b341c823af861e85b43cb12912efe148850f35`; Liquidity Scout Tests run #1766 also passed. The bounded live run inspected 13 ranked X1 Report sitemap pages. All 13 were available, but the dedicated extractor produced 0 XONE/XNT candidate claims and therefore 0 exact Ethereum address candidates. The evidence artifact digest is `sha256:68f9eb35c2bb2f77ba68f2f2c65bf7f4905e1cbbba5f9b764a88f68659d4477d`.

The accepted interpretation is strictly scoped: this run found no exact conversion-address candidate in the bounded X1 Report corpus it inspected. It does not prove no XONE→XNT converter, migration contract, burn-redeemer, claim contract, or allocation mechanism exists elsewhere. `migration_sink_identified=false`, `xone_xnt_conversion_verified=false`, `xnt_issuance_verified=false`, `cross_chain_correlation_verified=false`, and `execution_authorized=false`. PR #590 merged as `d34e83076b3a1cfd4dd5709c6c790aa89034bf6f`; Issue #589 closed completed.

### Previous accepted live gate — Ethereum XONE Migration Sink Semantics v1

**ACCEPTED.** Ethereum XONE Migration Sink Semantics run #1 passed deterministic and live jobs at PR #587 head `ed0ea9694b0ee0cb415541a3c1b23e7f95471253`; Liquidity Scout Tests run #1761 also passed. Tenderly and Blast satisfied the required direct-RPC quorum; dRPC and 1RPC also returned compatible burn-surface observations. Merkle was rate-limited on one identity receipt request and was not needed for acceptance. The evidence artifact digest is `sha256:e1a4b56476f87b733bfb71b4187758e1b3c8c31a74479075addb69d74ea5a808`.

The live gate directly verified the exact XONE `userBurns(address)` accounting surface. The two bounded probes — zero address and deployer `0xc73fc08c931efe3fce850c09278472e8a81c2e05` — each returned `0`. Those values apply only to those two addresses at the observed finalized state and do not establish zero lifetime/global XONE burns.

The accepted semantic result is intentionally fail-closed: XONE supports a burn/redeemer design in which a future conversion mechanism may use a callback contract; this gate does not require or identify a passive transfer sink. `migration_sink_identified=false`, `xone_xnt_conversion_verified=false`, `xnt_issuance_verified=false`, `cross_chain_correlation_verified=false`, and `execution_authorized=false`. PR #587 merged as `cdba7189c5d9faf0b24e7e0df7c1e12d0a41e501`; Issue #586 closed completed.

### Previous accepted live gate — Ethereum XONE Event Observer v1

**ACCEPTED.** Ethereum XONE Event Observer run #1 passed deterministic and live jobs at PR #584 head `742d83edee9986765e51a42fd285d23452b4bccb`; Liquidity Scout Tests run #1757 also passed. The live acceptance window was the exact XONE creation block `18,609,736` and was corroborated across multiple public Ethereum RPC transports. It contained one canonical ERC-20 `Transfer` classified as a mint: zero address → `0xc73fc08c931efe3fce850c09278472e8a81c2e05`, amount `500,000,000 XONE`, transaction `0x6d2f0492d54b56044f03a3de5ad1889b6fe115914e9bcfc58e28950ddda6eea5`, timestamp `1700443835`. Burn count in that exact window was zero. PR #584 merged as `3d344acd3964df77e3161abab6c1415659a50b4c`; Issue #583 closed completed.

This gate proves bounded canonical Ethereum XONE event observation. It does not prove lifetime supply, lifetime burn totals, any lock/migration/conversion sink, XNT issuance/vesting/claim state, or Ethereum→X1 correlation.

### Previous accepted live gate — Ethereum XONE Exact Identity v1

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
