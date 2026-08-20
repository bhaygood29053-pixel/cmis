# Solana Token-2022 live readiness fixture

CMIS uses one repository-approved exact Solana Token-2022 mint for **read-only live contract verification**:

- Asset: PYUSD
- Mint: `2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo`
- Program kind: `token_2022`
- Canonical Token-2022 program id: `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb`
- Decimals: `6`
- Scope: `read_only_rpc_contract_probe`
- Execution authorized: `false`

## Provenance

The fixture is grounded in Solana's own documentation rather than symbol discovery or third-party token lists:

1. Solana, **A Technical Deep Dive into PYUSD on Solana**
   - https://solana.com/news/pyusd-paypal-solana-developer
   - identifies the exact PYUSD mint as `2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo`.

2. Solana, **How payments work on Solana**
   - https://solana.com/docs/payments/how-payments-work
   - maps the same PYUSD mint to the Token-2022 program and documents 6 decimals.

The repository constant lives in `liquidity_scout/providers/solana/live_fixture.py` so workflow and test code can share one accepted identity contract.

## Accepted core live checks

`.github/workflows/solana-token2022-live-verify.yml` binds the core live probe to the exact fixture and exercises only read-only provider/runtime paths:

- `getTokenSupply` succeeds for the exact mint;
- `getAccountInfo(jsonParsed)` verifies the canonical Token-2022 owner/program identity;
- decimals agree across canonical supply and mint-state observations;
- Token-2022 extension names are preserved when the RPC returns them;
- production CMIS `asset_lookup` preserves exact mint and Token-2022 program identity;
- production CMIS `tokenomics` preserves verified total supply and its existing partial/unavailable boundaries.

The workflow prefers a configured `SOLANA_RPC_URL` secret when available and otherwise uses Solana's public mainnet RPC.

## Remaining issue #244 live acceptance

`getTokenLargestAccounts` remains part of the final acceptance scope because CMIS must prove that the exact live fixture preserves the existing bounded `largest_token_accounts_only` semantics without implying holder or beneficial-owner identity.

GitHub-hosted validation showed that Solana's public mainnet RPC could complete the Token-2022 core methods but returned a transport HTTP error for `getTokenLargestAccounts`. Therefore the dedicated workflow does **not** silently downgrade or treat that method as proven. Final issue #244 closure requires a dedicated Solana RPC endpoint through `SOLANA_RPC_URL`, followed by a successful live run with `RUN_SOLANA_LARGEST_ACCOUNTS_LIVE_TESTS=1`.

Deterministic provider tests continue to enforce that largest-account results are token-account observations only, with `total_holder_count_verified=false`.

## Boundaries

This fixture does **not** mean:

- PYUSD is a canonical market benchmark for Solana;
- Token-2022 implies safety;
- CMIS verified holder or beneficial-owner identity;
- provider labels become CMIS risk conclusions;
- Solana pre-trade is implemented;
- any transaction may be prepared, signed, broadcast, executed, or moved autonomously.

The fixture exists only to make one Token-2022 live readiness check reproducible. CMIS remains read-only and fail-closed outside the exact evidence it verifies.
