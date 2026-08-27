# X1 Provider Gap Register

Status date: **2026-08-26**

This register tracks capability gaps beneath CMIS for the X1 Provider. It is a planning and verification document, not a source of live market facts.

```text
Roberta
  -> X1 Scout
    -> CMIS
      -> X1 Provider
        -> X1 RPC / X1.Ninja / XDEX / other verified X1 sources
```

Provider-specific endpoint discovery, contract verification, and transport logic remain beneath CMIS. Roberta and X1 Scout do not call provider endpoints directly.

## Current accepted checkpoint

The X1 trust layer includes deterministic evidence/provenance, content-addressed evidence storage and lookup, pool-specific reserve verification, holder concentration/enumeration semantic gates, bounded SSE access classification, chain-first activity evidence, and fail-closed historical comparison/redundancy contracts.

Recent bounded live observations completed two probes that were previously listed as pending:

- the accepted X1.Ninja `/v1/stream/trades` handshake probe returned HTTP `403` / `access_denied` for the current repository credential; no event body was consumed and no schema/order/finality/reconnect/backfill/freshness semantics were inferred;
- a same-run XENCAT holder-looking comparison observed provider candidate `116`, RPC token-account candidate `180`, and unique token-account-authority candidate `174`; the result remains `INSUFFICIENT_EVIDENCE` because enumeration completeness, holder semantics, wallet identity, and beneficial ownership are unverified.

Those observations are non-promotional. They prove neither current stream usability nor holder totals.

Warp Bridge remains unpromoted because no exact provenance-approved machine-readable operational read URL/contract has been accepted.

Oracle V2 (`jacklevin74/oracle-v2`) is now tracked under issue #272 as a candidate read-only X1 price-evidence source. Public repository evidence describes a multi-source price feed, five signed relay submissions, and an X1 Oracle Vault program/state PDA, but CMIS has not independently verified the current deployed program/state, account layout, slot freshness, or signing-key identity. Relay-slot agreement must not be treated as five-source independence because the reviewed relays consume a common aggregated feed.

## Capability register

| ID | Capability | Status | Current evidence / next action |
|---|---|---|---|
| X1-RPC-01 | Core X1 RPC coverage | VERIFIED | Existing X1 RPC path is active; preserve provenance/tests. |
| X1-RPC-02 | Historical transaction RPC | PARTIAL | Historical comparison contracts are accepted; still requires live independent retention/finality/reconnect/backfill evidence. |
| X1-RPC-03 | RPC redundancy / failover | PARTIAL | Candidate redundant sources exist; independence, methods, retention, errors, latency, and failover remain to be proven. |
| X1-IDX-01 | General transaction / wallet indexer | PARTIAL | X1.Ninja indexing exists, but complete wallet/indexer semantics remain unproven. |
| X1-DEX-01 | Pool catalog / liquidity / volume | VERIFIED | CMIS has accepted provider/direct XDEX paths within their exact scopes. |
| X1-DEX-02 | Pool detail / reserves | VERIFIED (POOL-SPECIFIC) | XENCAT/XNT pool proof is accepted only for its exact pool/identity/unit scope. |
| X1-DEX-03 | Holder data | PARTIAL | Same-run observational probe completed; disagreement remains insufficient evidence. Do not relabel token accounts/authorities as holders or beneficial owners. |
| X1-HIST-01 | X1.Ninja trade history | PARTIAL | Structure/transport exists; deeper semantic/finality/pagination coverage remains bounded. |
| X1-HIST-02 | X1.Ninja OHLCV | PARTIAL | Contract tests exist; semantics remain field/scope specific. |
| X1-HIST-03 | Direct XDEX chart/history | BLOCKED/PARTIAL | Some field semantics are bounded/verified; remaining pair/volume/history semantics stay unpromoted where not proven. |
| X1-QUOTE-01 | Direct XDEX read-only quote | PARTIAL | Exact route/config and selected price-impact/slippage parameter semantics are bounded; expected execution slippage/route quality remain unavailable. |
| X1-STREAM-01 | X1.Ninja real-time trades | PARTIAL / ACCESS DENIED CURRENTLY | Bounded handshake probe completed with HTTP 403/access_denied for current credential. No stream semantics promoted. |
| X1-STREAM-02 | General chain real-time stream | PARTIAL | PubSub/candidate sources require commitment/finality/reconnect/order/backfill validation. |
| X1-XCHECK-01 | Same-fact independent verification | VERIFIED (FRAMEWORK) | Framework is accepted; each fact still requires proven source independence and fact-specific gates. |
| X1-ORACLE-01 | Oracle V2 on-chain price evidence | CANDIDATE | Issue #272. Repository-declared program/PDA and 6-asset × 5-slot layout are documented; current X1 deployment/account identity/layout/freshness must be RPC-verified before any CMIS use. Relay redundancy is not source independence. |
| X1-BRIDGE-01 | Bridge operational state | MISSING | Exact-URL provenance gate exists, but no approved machine-readable operational endpoint is accepted yet. |
| X1-BRIDGE-02 | Supported bridged assets / representations | PARTIAL | Canonical representation modeling exists; exact machine-readable bridge configuration remains to be verified. |
| X1-BRIDGE-03 | Bridge fees / route capacity | MISSING | No verified machine-readable contract. |
| X1-BRIDGE-04 | Bridge transfer state / history | MISSING | No accepted authoritative lifecycle source. |
| X1-BRIDGE-05 | Guardian set / health | PARTIAL | UI concepts exist; machine-readable source/identity/freshness contract remains unproven. |
| X1-BRIDGE-06 | Bridge-flow / TVL cross-check | CANDIDATE | Independent candidate only until provenance/API semantics are verified. |
| X1-ALT-01 | Secondary archival RPC / streaming redundancy | MISSING | X1Scroll is removed from CMIS integration scope after credential-backed verification could not run without an available API key. Any future secondary provider requires a new explicit contract/evidence gate. |
| X1-ALT-02 | FortiBlox explorer / RPC ecosystem | CANDIDATE | Verify each endpoint independently before any promotion. |

## Promotion rules

Before any PARTIAL, CANDIDATE, BLOCKED, or MISSING capability is promoted:

1. bind exact source/endpoint/account identity and observation time;
2. fail closed on malformed/stale/ambiguous data or undocumented units;
3. preserve chain + verified address identity separately from symbols/names;
4. preserve scope/completeness/uncertainty and never replace missing values with zero;
5. add deterministic contract tests and opt-in live verification where freshness/provider behavior matters;
6. preserve source role and timestamps in CMIS envelopes;
7. prove actual source independence for cross-checks and define deterministic disagreement behavior;
8. never promote sparse historical observations into archival/retention claims;
9. do not convert provider/UI claims into CMIS truth without accepted verification.

## Immediate work order

1. **Warp Bridge source discovery** — obtain one exact provenance-approved machine-readable read URL and bounded response contract.
2. **Oracle V2 read-contract verification (#272)** — verify the repository-declared X1 program/state through X1 RPC, prove the exact account layout/timestamp semantics, and define fail-closed freshness/median behavior before any provider implementation or promotion.
3. **Historical redundancy live evidence** — prove source independence and retention/finality/reconnect/backfill behavior for a selected secondary source.
4. **Holder semantics evidence** — investigate counted-entity and coverage semantics; do not repeat the already-completed observational comparison unless new evidence/source conditions justify it.
5. **SSE access remediation / alternate source** — current credential access is denied; only after authenticated access is established should event schema/order/finality/reconnect/backfill semantics be tested.
6. **Independent bridge cross-check** — evaluate candidates only after their own machine-readable provenance/contracts are verified.

All work remains read-only/fail-closed and does not authorize execution.
