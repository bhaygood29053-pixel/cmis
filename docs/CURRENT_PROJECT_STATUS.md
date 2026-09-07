# Current CMIS Project Status

Current reconciliation: **2026-09-07 14:26 America/New_York**.

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
- Dedicated XONE/XNT Conversion Intelligence is accepted internally through #575 / PR #578 (web discovery), #580 / PR #581 (exact Ethereum identity), #583 / PR #584 (bounded canonical events), #586 / PR #587 (burn/redeemer semantics), #589 / PR #590 (exact Ethereum candidate discovery), #592 / PR #593 (X1 XNT rule/account discovery), #595 / PR #596 (exact X1 binding discovery), #604 / PR #605 (`ethereum_xone_snapshot_registry/v1`), #607 / PR #608 (`xone_snapshot_provenance_expansion/v1`), and #610 / PR #611 (`xone_snapshot_archival_source_recovery/v1`). The **current primary target remains the Ethereum XONE holder snapshot/registry**, not MoonParty. Archival Recovery run #4 had 9/9 CDX queries available, discovered 93 captures, successfully replayed 11 bounded host/time-diversified captures, and produced 0 stable primary URLs / 0 archival provenance candidates / 0 authoritative exact snapshot blocks. Replay/index availability failures remain explicit and this does not disprove a private/unpublished/deleted-unarchived snapshot. CMIS can reconstruct and multi-RPC corroborate the full XONE holder ledger immediately once an authoritative exact block is identified. Snapshot→XNT allocation binding, XNT issuance/vesting/unlock, October 6 applicability and cross-chain correlation remain unverified, with no public/Scout promotion and `execution_authorized=false`.

## Latest accepted live gate

### XONE Snapshot Archival Source Recovery v1

**ACCEPTED INTERNAL FOUNDATION.** XONE Snapshot Archival Source Recovery run #4 passed deterministic and live jobs at PR #611 head `105f7e9dd55c372afc7756a911ef79b9ab548ef9`; Liquidity Scout Tests run #1806 also passed. PR #611 merged as `aa216ee6e49cc28ed969e990fd637577214a432c`; Issue #610 closed completed.

The live archive gate had **9/9 CDX queries available**, discovered **93 distinct captures**, and successfully replayed **11** bounded captures after the replay selector was hardened to distribute its budget across original hosts and historical time rather than spending it on one root site. CDX coverage included `xen.network`, `x1.xyz`, `next.x1.xyz`, and `docs.x1.xyz`. The XspaceGPT Jack Levin index was available with XONE historical context but no explicit snapshot term; TwStalker returned HTTP 403. Several selected Wayback replays, including XEN captures, encountered transient connection-refused failures; these are preserved as availability limitations and are not interpreted as negative content evidence.

The accepted result was **0 stable primary URLs, 0 archival provenance candidates, 0 direct primary archival candidates, and 0 authoritative exact snapshot blocks**. Evidence artifact id: `10029502671`; digest: `sha256:136d96e7aba8d5f50b4d694add915537cf171d9d6ab7efa9f0f55fd0b22db69d`.

No holder-ledger reconstruction was triggered because no authoritative exact block emerged. The correct interpretation remains fail-closed: `private_or_unpublished_snapshot_absence_proven=false`, `official_xone_snapshot_verified=false`, `official_registry_artifact_verified=false`, `xone_snapshot_eligibility_verified=false`, `xone_snapshot_xnt_allocation_binding_verified=false`, `xnt_issuance_verified=false`, `xnt_vesting_or_unlock_verified=false`, `october_6_unlock_applies_to_xone_verified=false`, `xone_xnt_conversion_verified=false`, `cross_chain_correlation_verified=false`, and `execution_authorized=false`.

**Current next gate:** archived asset-graph / primary-source resolution — enumerate historical XEN/X1 page outlinks, JavaScript bundles, manifests, JSON/static assets and stable X/X Spaces identifiers, then search those preserved assets for XONE/snapshot/holder/registry/allocation/XNT semantics.

### Previous accepted live gate — XONE Snapshot Provenance Expansion v1

**ACCEPTED INTERNAL FOUNDATION.** XONE Snapshot Provenance Expansion run #6 passed deterministic and live jobs at PR #608 head `beedae86c92d4919abccdc975f84094a3ebc9de0`; Liquidity Scout Tests run #1799 also passed. The accepted live corpus covered both FairCrypto repositories, `x1-labs/xenblocks-airdrop`, 4 available official X1 targets, 13 available ranked X1 Report pages and 1 available indexed Jack Levin historical surface.

The refined extractor intentionally rejected ordinary XONE ABI/config JSON as snapshot provenance. The accepted result was **0 provenance candidates, 0 direct primary snapshot-source candidates, 0 snapshot-artifact candidates, 0 indexed-mirror candidates and 0 authoritative exact snapshot blocks**. The evidence artifact id is `10028368038` with digest `sha256:bd3db1a9804a070e1a8017fd660db4bad3eb0802ad114d3de0ebc5d54fa1af88`.

The one available indexed Jack surface contained XONE historical material but no explicit snapshot term. No direct-chain reconstruction was triggered because no authoritative exact block existed. This remains a scoped public-provenance miss only; `private_or_unpublished_snapshot_absence_proven=false`. `official_xone_snapshot_verified=false`, `official_registry_artifact_verified=false`, `xone_snapshot_eligibility_verified=false`, `xone_snapshot_xnt_allocation_binding_verified=false`, `xnt_issuance_verified=false`, `xnt_vesting_or_unlock_verified=false`, `october_6_unlock_applies_to_xone_verified=false`, `xone_xnt_conversion_verified=false`, `cross_chain_correlation_verified=false`, and `execution_authorized=false`. PR #608 merged as `ff0648a3768ce1f4f1307dc66e24baa8c920746a`; Issue #607 closed completed.

**Current next gate:** deeper primary-source/archival snapshot recovery — direct/stable Jack historical source links or archives, archived X1/FairCrypto/XEN pages, registry/CSV/JSON/IPFS/Arweave references, Merkle roots, holder-export artifacts and X1 allocation records keyed by Ethereum addresses.

### Previous accepted live gate — Ethereum XONE Snapshot / Registry v1

**ACCEPTED INTERNAL FOUNDATION.** Ethereum XONE Snapshot Registry run #1 passed deterministic and live bounded-source jobs at PR #605 head `d8dbb8bf8bc225517bd1637ceed98b00073107c6`; Liquidity Scout Tests run #1790 also passed. The live corpus had 8 available FairCrypto source/history targets, 4 available official X1 targets, and 13 available ranked X1 Report pages. It produced **0 explicit XONE snapshot/registry claims, 0 official snapshot candidates, and 0 authoritative exact snapshot-block candidates**. The evidence artifact digest is `sha256:49dcea6f8ce5d412a3e09fe59ef8e2f55591c05b72c29e515812a0bad2f5cc36`.

Because no authoritative exact block was found, no live holder-ledger reconstruction was triggered. That is the correct fail-closed result: CMIS did not invent a snapshot date or use X1 launch/October 6/MoonParty/validator rules as a substitute. The accepted contract is ready to reconstruct canonical XONE balances from creation block `18,609,736` through a future authoritative snapshot block, cross-check historical `totalSupply()`, verify deterministic `balanceOf()` samples, compute a canonical registry SHA-256, and require two distinct Ethereum RPC transports to agree before official snapshot promotion.

The live architecture analogue also confirmed that public `x1-labs/xenblocks-airdrop` contains ETH-address-keyed native-XNT airdrop machinery but **no XONE reference**, so it remains architecture evidence only and is not the XONE registry. `official_xone_snapshot_verified=false`, `official_registry_artifact_verified=false`, `xone_snapshot_eligibility_verified=false`, `xone_snapshot_xnt_allocation_binding_verified=false`, `xnt_issuance_verified=false`, `xnt_vesting_or_unlock_verified=false`, `october_6_unlock_applies_to_xone_verified=false`, `xone_xnt_conversion_verified=false`, `cross_chain_correlation_verified=false`, and `execution_authorized=false`. PR #605 merged as `ef6b52cb54c058bece72a8e04fb726997e9c1c00`; Issue #604 closed completed.

**Current next gate:** snapshot provenance expansion — direct Jack/X1 historical posts or archives, XONE/X1 release artifacts, registry/CSV/JSON/IPFS references, Merkle roots, archived holder files and X1 allocation lists keyed by Ethereum addresses. MoonParty is not the current XONE/XNT priority.

### Previous accepted live gate — MoonParty Deployment Verification v1

**ACCEPTED BOUNDED FOUNDATION.** MoonParty Deployment Verification run #2 passed deterministic and live jobs at PR #602 head `b6396af0052a68f4bfe5db1dea099df2e333b000`; Liquidity Scout Tests run #1786 also passed. The live source gate retrieved 4/4 pinned FairCrypto sources, 6/6 current `xen.network` / `preview.xen.network` frontend targets, and 26/28 same-host JavaScript chunks. Across 35 inspected documents, the exact MoonParty candidate extractor produced 0 deployment-address candidates. The evidence artifact digest is `sha256:56198255749d41ddba7d5bb7f65eac874b4eddd3191737fd8adebd4888fc9a68`.

The accepted interpretation is strictly scoped: this corpus did not expose the exact deployment address needed to run the direct Ethereum runtime/`XONE()`/two-RPC qualification gate. It does not prove MoonParty was never deployed. `moonparty_deployment_verified=false`, `moonparty_deployment_chain_verified=false`, `moonparty_runtime_compatible=false`, `moonparty_xone_binding_verified=false`, `xnt_credit_to_native_xnt_equivalence_verified=false`, `xnt_issuance_verified=false`, `xnt_vesting_or_unlock_verified=false`, `october_6_unlock_applies_to_xone_verified=false`, `xone_xnt_conversion_verified=false`, `cross_chain_correlation_verified=false`, and `execution_authorized=false`. PR #602 merged as `2b73ec07c775eebe7ea86ff54155e29b866d0d9a`; Issue #601 closed completed.

### Previous accepted live gate — XONE/XNT MoonParty Source Semantics v1

**ACCEPTED.** XONE XNT MoonParty Source Semantics run #1 passed deterministic and live pinned-source jobs at PR #599 head `57912a8204c9e919722a3bbec8dd7c7d78efc610`; Liquidity Scout Tests run #1781 also passed. The live gate retrieved all required artifacts from pinned FairCrypto/x1-app commit `abf168fad119e91a8da0773625fd6115e8756cb4` and FairCrypto/XONE commit `267bfeaabd69bf81f272cfd52aa5082333cd317a`. The evidence artifact digest is `sha256:4f8474b99e43cea59e52b15886d1e383d9c993c7e4605608f97ae96df26a24ea`.

The accepted source-semantic proof directly verifies that the FairCrypto MoonParty design includes XONE participation/redemption, the XONE-compatible burn/redeemer callback surface, and per-user/aggregate XNT-credit allocation accounting through `allocateXNTCredits` and `totalAllocatedXNTCredits`. This is source-level design evidence, not deployment or native-XNT issuance proof. `moonparty_deployment_verified=false`, `xnt_credit_to_native_xnt_equivalence_verified=false`, `xnt_issuance_verified=false`, `xone_xnt_conversion_verified=false`, `cross_chain_correlation_verified=false`, and `execution_authorized=false`. PR #599 merged as `751d90207c2a852880d4e86617fec4a948f8d439`; Issue #598 closed completed.

### Previous accepted live gate — XONE/XNT X1 Binding Discovery v1

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
