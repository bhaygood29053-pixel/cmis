# X1 Oracle V2 Live Evidence — 2026-08-27

Status: **STRUCTURAL CONTRACT VERIFIED / CURRENT PRICE USE NOT AUTHORIZED**

Tracking issue: **#272**

Verification PR: **#274**

Upstream source snapshot: `jacklevin74/oracle-v2@97177f772689e44ca4eed9bb95be32ffdf0c5e66`

Live evidence workflow run: `33036569142`

Sanitized artifact:
- artifact ID: `9632210085`
- name: `x1-oracle-v2-evidence-33036569142`
- digest: `sha256:0bb8466a7f554db73216d869ba99cd129c941d4f3733b5812e96cd3a1b10c735`

Observed at: **2026-08-27T03:30:40.558913Z**

## Structural verification result

The live read-only X1 RPC probe returned `verified_contract_shape`.

Verified live facts from X1 RPC:

- program `9mPmjK8NxJadYDiHiYAQH4WFCnKJr7ZV8ria63ZkMtv2` exists;
- the program account is executable;
- program-account owner is `BPFLoaderUpgradeab1e11111111111111111111111`;
- program observation context slot was `74524059`;
- state PDA `8XZBqbKhFXHqNGzxV3Tt6gEs9r8ZrNghsRg7zBwLMGJf` exists;
- state-account owner is the expected Oracle V2 program;
- state-account observation context slot was `74524060`;
- the declared PDA independently derives from seed `oracle_vault_v1` with bump `255`;
- state account length is exactly `618` bytes;
- Anchor `OracleState` discriminator is `619c9dbdc249080f`;
- decoded decimals are `6`;
- decoded bump is `255`;
- the exact six-asset × five-relay-slot layout decodes successfully;
- all 30 observed slots contained positive timestamps and non-zero stored prices at this observation;
- the live stored Oracle Ed25519 public key matches the default Transit public key encoded in the pinned relay client:
  `8tJv+C6x1PKBtzapaR2Zx8TM8YqeDGzStfVspLBgw1w=`.

This establishes that the repository-declared deployed Oracle V2 contract shape is currently present on X1 and matches the reviewed source layout.

It does **not** establish current price correctness, upstream Pyth/CEX provenance for each stored value, source independence, or CMIS promotion.

## Timestamp / freshness finding

The decoded relay timestamps were not current.

Across the five relay slots, the embedded Unix-ms timestamps ranged from:

- earliest: **2026-03-27T08:33:39.350Z**
- latest: **2026-03-27T08:34:16.170Z**

The live probe ran on **2026-08-27T03:30:40.558913Z**.

Therefore the newest stored relay timestamp was approximately:

- `13,200,984,389 ms` old;
- about **152.789 days** old.

No CMIS freshness threshold was applied by this tracer bullet. Because freshness has not been accepted and the observations are roughly five months old, **current price use remains unauthorized**.

The probe must remain fail-closed:

```text
structurally valid price/timestamp
    != fresh
    != current CMIS market fact
    != CMIS-price-eligible
```

## Upstream freshness / replay constraint

The pinned Oracle V2 program requires:

- `timestamp > 0`;
- `price >= 0`.

The reviewed program does not enforce a maximum timestamp age or monotonic timestamp progression before writing a relay slot.

Consequences for CMIS evidence handling:

- recent account write or transaction recency must not substitute for embedded timestamp freshness;
- old signed price messages are not rejected by a freshness/monotonicity rule solely because their signed timestamp is old;
- CMIS must apply its own explicit freshness policy before any slot can become price-eligible;
- zero prices must remain ineligible even though the upstream program accepts them.

This is an evidence-safety constraint, not an execution claim.

## Independence constraint

The five relay slots remain one Oracle V2 system's relay redundancy.

The reviewed relay clients consume a common aggregated price-feed server, so:

```text
five relay slots
    != five independent market sources
```

Relay agreement may be useful as same-system consistency evidence, but source independence must be proven separately.

## Current CMIS decision

```text
deployment_verified = true
contract_shape_verified = true
account_layout_verified = true
current_price_use_authorized = false
freshness_policy_applied = false
source_independence_verified = false
price_correctness_verified = false
cmis_provider_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

## Next gate

Before Oracle V2 can supply live CMIS price evidence:

1. define and accept an explicit deterministic freshness policy;
2. require eligible slots to pass that policy;
3. compute a deterministic median only from eligible fresh slots;
4. establish exact same-fact identity/unit/time gates for comparison with existing X1 evidence;
5. keep relay redundancy separate from source-independence proof;
6. add Evidence Receipt / Proof Score integration only after the above passes;
7. complete normal CI and the independent Spec/Contract, Code/Architecture, and Authority/Evidence Safety review gates.

No signing, submission, transaction construction, broadcast, custody, or execution authority is introduced by this verification.
