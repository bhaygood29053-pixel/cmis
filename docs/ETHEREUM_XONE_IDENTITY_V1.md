# Ethereum XONE Exact Identity v1

Status: **IMPLEMENTATION FOR ISSUE #580 — NOT ACCEPTED UNTIL LIVE DUAL-RPC CI PASSES AND PR MERGES**

Contract:

`ethereum_xone_identity/v1`

## Scope

This is a deliberately narrow Ethereum mainnet verification contract for the XONE token used by the dedicated XONE/XNT conversion intelligence foundation. It is not a general Ethereum provider milestone.

Candidate under test:

- Ethereum contract: `0x4DCDa2274899d9BbA3Bb6f5A852C107Dd6E4fE1c`
- creation transaction: `0x6d2f0492d54b56044f03a3de5ad1889b6fe115914e9bcfc58e28950ddda6eea5`
- expected deployer: `0xc73fc08c931efe3fce850c09278472e8a81c2e05`
- expected ERC-20 name: `XONE`
- expected ERC-20 symbol: `XONE`
- expected decimals: `18`

These constants are acceptance expectations. The contract does not mark them verified unless live Ethereum JSON-RPC proves them.

## Direct-chain proof

For each RPC transport, the verifier requires:

1. `eth_chainId == 0x1`;
2. `eth_getTransactionByHash` returns the exact candidate creation transaction;
3. the transaction is contract creation (`to == null`) from the exact expected deployer;
4. `eth_getTransactionReceipt` reports success and the exact XONE contract address;
5. finalized `eth_getCode` returns non-empty runtime bytecode;
6. finalized `eth_call` returns `name() == XONE`, `symbol() == XONE`, and `decimals() == 18`.

Live acceptance requires at least two distinct HTTPS RPC transport hosts to return the same bounded identity facts and the same runtime-code SHA-256.

The workflow currently probes:

- Tenderly public gateway: `https://gateway.tenderly.co/public/mainnet`
- Blast public Ethereum: `https://eth-mainnet.public.blastapi.io`
- Merkle: `https://eth.merkle.io`
- dRPC: `https://eth.drpc.org`
- 1RPC: `https://public.1rpc.io/eth`

At least two successful matching proofs are required. The quorum intentionally includes several public transports because free RPC endpoints can differ in historical transaction/receipt retention and can fail transiently. Provider unavailability is reported as availability evidence, not an identity disagreement.

## Secondary explorer corroboration

Etherscan reports the same address as the XONE ERC-20, with 18 decimals and exact-match verified source code named `XONE`. It also shows the creation transaction from the address it labels `XEN Stake: Deployer`.

That explorer evidence is useful corroboration, but it does **not** replace the direct JSON-RPC gate.

## What this proves

If accepted, CMIS may say:

> The exact Ethereum mainnet XONE contract identity has been verified as
> `0x4DCDa2274899d9BbA3Bb6f5A852C107Dd6E4fE1c`.

It may also preserve the exact verified creation transaction, deployer, runtime-code digest, and ERC-20 metadata.

## What this does not prove

Identity verification does not establish:

- any XONE -> XNT conversion ratio;
- whether XONE must be burned, locked, transferred, or snapshotted;
- conversion eligibility;
- any conversion deadline;
- XNT allocation, minting, vesting, claim, or unlock state;
- that an Ethereum XONE event caused an X1 XNT event;
- source independence beyond the bounded transport-diversity statement;
- risk, recommendation, or execution authority.

Those require separate accepted contracts.

## Handoff to XONE/XNT conversion intelligence

`CMISXoneXntConversionIntelligenceService.verify_ethereum_xone_identity()` may consume one direct RPC proof.

`CMISXoneXntConversionIntelligenceService.corroborate_ethereum_xone_identity()` may require matching multi-RPC proofs.

Only `ethereum_xone_identity_verified` is elevated by this handoff. The service keeps:

```text
ethereum_event_verified = false
x1_event_verified = false
cross_chain_correlation_verified = false
cmis_verified = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

## Next slice after acceptance

Once the exact Ethereum XONE identity is accepted, the next implementation slice is a bounded XONE event observer for the verified contract. It should classify burns, transfers, locks/migration deposits, and holder-specific activity only from direct Ethereum evidence, while keeping any XNT-side consequence unverified until an exact X1 migration/distribution contract is identified.
