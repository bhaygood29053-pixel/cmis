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

## Accepted live checks

`.github/workflows/solana-token2022-live-verify.yml` binds the live probe to the exact fixture and exercises only read-only provider/runtime paths:

- `getTokenSupply` succeeds for the exact mint;
- `getAccountInfo(jsonParsed)` verifies the canonical Token-2022 owner/program identity;
- decimals agree across canonical supply and mint-state observations;
- Token-2022 extension names are preserved when the RPC returns them;
- production CMIS `asset_lookup` preserves exact mint and Token-2022 program identity;
- production CMIS `tokenomics` preserves verified total supply and its existing partial/unavailable boundaries;
- `getTokenLargestAccounts` is additionally exercised when a dedicated RPC secret is configured and remains explicitly bounded to largest token accounts only.

## Boundaries

This fixture does **not** mean:

- PYUSD is a canonical market benchmark for Solana;
- Token-2022 implies safety;
- CMIS verified holder or beneficial-owner identity;
- provider labels become CMIS risk conclusions;
- Solana pre-trade is implemented;
- any transaction may be prepared, signed, broadcast, executed, or moved autonomously.

The fixture exists only to make one Token-2022 live readiness check reproducible. CMIS remains read-only and fail-closed outside the exact evidence it verifies.
