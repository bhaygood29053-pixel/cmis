# X1 Provider Gap Register

Status date: **2026-08-27**

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

Oracle V2 (`jacklevin74/oracle-v2`) remains tracked under issue #272 as non-promoted read-only X1 price evidence. CMIS has verified deployed program/state identity, exact layout, stored key, Unix-ms timestamp semantics, and the explicit freshness policy. The latest live run classified all 30 observed relay slots stale, so current-price use and price correctness remain unavailable/unverified. Relay-slot agreement must not be treated as five-source independence because the reviewed relays consume a common aggregated feed.

## Capability register

| ID | Capability | Status | Current evidence / next action |
|---|---|---|---|
| X1-RPC-01 | Core X1 RPC coverage | VERIFIED | Existing X1 RPC path is active; preserve provenance/tests. |
| X1-RPC-02 | Historical transaction RPC | PARTIAL | Historical comparison contracts are accepted; still requires live independent retention/finality/reconnect/backfill evidence. |
| X1-RPC-03 | RPC redundancy / failover | PARTIAL | Official RPC is accepted; self-hosted read-only node verification is the next bounded redundancy task. Methods, retention, errors, latency, failover, and independence claims remain to be proven. |
| X1-IDX-01 | General transaction / wallet indexer | PARTIAL | X1.Ninja indexing exists, but complete wallet/indexer semantics remain unproven. |
| X1-DEX-01 | Pool catalog / liquidity / volume | VERIFIED | CMIS has accepted provider/direct XDEX paths within their exact scopes. |
| X1-DEX-02 | Pool detail / reserves | VERIFIED (POOL-SPECIFIC) | XENCAT/XNT pool proof is accepted only for its exact pool/identity/unit scope. |
| X1-DEX-03 | Holder data | PARTIAL | Same-run observational probe completed; disagreement remains insufficient evidence. Do not relabel token accounts/authorities as holders or beneficial owners. |
| X1-HIST-01 | X1.Ninja trade history | PARTIAL | Structure/transport exists; deeper semantic/finality/pagination coverage remains bounded. |
| X1-HIST-02 | X1.Ninja OHLCV | PARTIAL | Contract tests exist; semantics remain field/scope specific. |
| X1-HIST-03 | Direct XDEX chart/history | BLOCKED/PARTIAL | Some field semantics are bounded/verified; remaining pair/volume/history semantics stay unpromoted where not proven. |
| X1-QUOTE-01 | Direct XDEX read-only quote | PARTIAL | Exact route/config and selected price-impact/slippage parameter semantics are bounded; expected execution slippage/route quality remain unavailable. |
| X1-STREAM-01 | X1.Ninja real-time trades | PARTIAL / ACCESS DENIED CURRENTLY | Bounded handshake probe completed with HTTP 403/access_denied for current credential. No stream semantics promoted. |
| X1-STREAM-02 | General chain real-time stream | PARTIAL | Official/self-hosted X1 PubSub is the next bounded candidate; commitment/finality/reconnect/order/duplicate/gap/backfill semantics remain to be validated. |
| X1-XCHECK-01 | Same-fact independent verification | VERIFIED (FRAMEWORK) | Framework is accepted; each fact still requires proven source independence and fact-specific gates. |
| X1-ORACLE-01 | Oracle V2 on-chain price evidence | CANDIDATE / CURRENTLY STALE | Issue #272. Deployment identity/layout, timestamp unit, and freshness policy are verified. Latest live evidence found all 30 slots stale, so no current-price median is eligible; price correctness/source independence/promotion remain false. Relay redundancy is not source independence. |
| X1-BRIDGE-01 | Bridge operational state | MISSING | Exact-URL provenance gate exists, but no approved machine-readable operational endpoint is accepted yet. |
| X1-BRIDGE-02 | Supported bridged assets / representations | PARTIAL | Canonical representation modeling exists; exact machine-readable bridge configuration remains to be verified. |
| X1-BRIDGE-03 | Bridge fees / route capacity | MISSING | No verified machine-readable contract. |
| X1-BRIDGE-04 | Bridge transfer state / history | MISSING | No accepted authoritative lifecycle source. |
| X1-BRIDGE-05 | Guardian set / health | PARTIAL | UI concepts exist; machine-readable source/identity/freshness contract remains unproven. |
| X1-BRIDGE-06 | Bridge-flow / TVL cross-check | CANDIDATE | Independent candidate only until provenance/API semantics are verified. |
| X1-ALT-01 | Self-hosted X1 read-only node history / streaming redundancy | MISSING / NEXT | Verify the official read-only node configuration and bounded history/PubSub semantics. Treat node redundancy separately from independent market-source evidence. |
| X1-ALT-02 | FortiBlox explorer / RPC ecosystem | ARCHIVED / UNVERIFIED | PR #227 closed as candidate research; no reproducible provider-owned endpoint/response contract is accepted. Reopen only with new exact evidence. |

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

1. **Self-hosted X1 read-only node verification** — prove exact configuration/identity plus bounded history and PubSub behavior for redundancy without claiming independent market-price evidence.
2. **Holder semantics evidence** — investigate counted-entity and coverage semantics; do not repeat the already-completed observational comparison unless new evidence/source conditions justify it.
3. **Deeper Solana field maturity** — strengthen exact field/source/freshness semantics under shared CMIS contracts.
4. **Oracle V2 #272 conditional recheck** — only when new policy-eligible live slots appear, rerun freshness and then exact same-fact price-correctness/source-independence gates.
5. **Warp Bridge** — remains missing/not currently verifiable until an exact provenance-approved machine-readable read contract appears.
6. **X1.Ninja SSE** — current credential access is denied; only after authenticated access is established should event schema/order/finality/reconnect/backfill semantics be tested.

All work remains read-only/fail-closed and does not authorize execution.
