# Wallet Relationship Intelligence Request v1

Status: public selector-only foundation for CMIS #631. This contract does not register a runtime service, advertise a capability, or authorize X1 Scout reliance.

## Purpose

`wallet_relationship_intelligence_request/v1` defines exactly what a caller may choose when asking CMIS to verify one direct X1 fungible-token transfer relationship:

- exact X1 transaction signature;
- exact fungible-token mint;
- exact sender wallet;
- exact recipient wallet.

The caller selects the evidence target. CMIS remains the authority for whether the transfer occurred and for every materialized fact.

## Request shape

```text
contract_version = wallet_relationship_intelligence_request/v1
chain = x1
transaction_signature = exact 64-byte base58 transaction signature
asset_mint = exact 32-byte base58 X1 public key
sender_wallet = exact 32-byte base58 X1 public key
recipient_wallet = exact 32-byte base58 X1 public key
```

Sender and recipient must be distinct.

## Caller trust boundary

The request must reject caller-supplied:

- parsed transaction or instruction material;
- token-account ownership claims;
- source/destination token-account facts;
- amount, decimals, direction, or transfer claims;
- `wa_`, `wr_`, or `wrs_` records/ids;
- wallet-activity or relationship evidence;
- provider/source assertions;
- Evidence Receipt or Proof Score material;
- ownership or beneficial-ownership labels;
- real-world identity;
- whale, insider, bot, market-maker, coordination, manipulation, fraud/scam, intent, causality, or risk labels;
- complete-history or complete-relationship-graph assertions;
- service-promotion or execution authority.

The validated request records that all such caller trust material is absent.

## Runtime dependency

The future protected runtime path remains:

```text
exact caller selectors
  -> protected canonical X1 transaction resolver
  -> x1_direct_wallet_transfer_materialization/v1
  -> wallet_relationship_intelligence/v1 response projection
```

The protected materialization dependency is CMIS #633 / `cmis-core` PR #51. It must receive executable private CI before runtime/capability promotion.

## Truth boundaries

A verified direct transfer is evidence only of an observed direct interaction. It is not evidence by itself of common ownership, beneficial ownership, a real-world person/entity, whale/insider/bot status, coordination, manipulation, intent, causality, or risk severity.

Missing evidence remains unknown. A bounded exact transaction does not prove complete wallet history or complete relationship-graph coverage.

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
complete_history_claimed = false
complete_graph_coverage_claimed = false
execution_authorized = false
```
