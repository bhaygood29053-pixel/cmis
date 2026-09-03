# Warp on-chain account inventory v1

Issue: #419  
Parent: #407

## Purpose

Discover the Warp Bridge's independently verifiable on-chain state surface
without guessing private `bridge-api.x1.xyz` paths.

The exact Warp program id is:

```text
6JbPTuxVuoTgyQeXFb9MH8C8nUY8NBbLP1Lu4B13JfMD
```

The same program identity is observed on Solana and X1. This slice inventories
accounts owned by that program on both chains through read-only
`getProgramAccounts`.

## First-pass boundary

The first live inventory requests:

```json
{
  "encoding": "base64",
  "commitment": "confirmed",
  "dataSlice": {"offset": 0, "length": 0},
  "withContext": true
}
```

No account bytes are intentionally requested.

CMIS records only:

- account pubkey;
- exact owner;
- account space/data length when supplied;
- lamports;
- executable flag;
- rent epoch when supplied;
- RPC context slot when supplied;
- deterministic inventory fingerprints.

## What account ownership proves

An account returned with exact owner equal to the Warp program can be treated
as a Warp-program-owned account observation.

It does **not** prove the account is:

- bridge configuration;
- guardian state;
- a route;
- a mint authority;
- a custody vault;
- a transfer record;
- a fee/cap record.

Account size is structural evidence only. Two accounts with the same size do
not inherit the same role.

## Cross-chain comparison

The v1 comparison reports:

- unique Warp-owned account count on Solana;
- unique Warp-owned account count on X1;
- account-size distributions;
- exact pubkey overlap;
- per-chain inventory fingerprints.

No role equivalence is inferred from size, ordering, lamports, or overlap.

## Promotion state

This discovery slice always preserves:

```text
account_binary_layout_verified = false
config_account_identity_verified = false
guardian_account_identity_verified = false
route_semantics_verified = false
semantic_contract_accepted = false
cmis_promotable = false
public_service_promoted = false
scout_reliance_promoted = false
read_only = true
execution_authorized = false
```

## Accepted live evidence

Exact-head live evidence from merged PR #423 / workflow run 33731432570 established:

- Solana context slot: `443921036`;
- Solana Warp-owned accounts: `11036`;
- X1 context slot: `76214846`;
- X1 Warp-owned accounts: `10983`;
- exact cross-chain pubkey overlap: `49`;
- Solana size families: 49×6, 106×3965, 107×3, 113×785, 116×6267, 170×7, 236×1, 321×1, 335×1;
- X1 size families: 49×1, 106×6275, 107×8, 113×705, 116×3984, 170×7, 236×1, 321×1, 335×1.

The matching counts for the rare 170/236/321/335-byte families are discovery
signals only. They do not establish account-role or layout equivalence.

## Next gate

If live inventory succeeds, classify stable account-size families and select
bounded candidates for a second read-only capture. The next slice may request a
small prefix/full body only for reviewed account families, fingerprint the raw
bytes, and compare state changes against known bridge configuration changes.

Any binary-layout or semantic interpretation requires a separate acceptance PR.
