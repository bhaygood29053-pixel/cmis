# CMIS Project Identity Migration

## Decision

The canonical project identity is **CMIS — Cross-Chain Market Intelligence Service**.

The historical **Liquidity Scout** name describes the original prototype. It no longer describes the repository's primary architectural role or a separate normal user-facing product.

Canonical architecture:

```text
User / transport
      ↓
Roberta — coordinator / user-facing voice
      ↓
Chain Scouts
  ├── X1 Scout
  └── Solana Scout
      ↓
CMIS — Cross-Chain Market Intelligence Service
      ↓
Chain Providers
  ├── X1 / XDEX
  └── Solana
```

Authority flows downward:

```text
Roberta → Chain Scout → CMIS → Chain Provider
```

Verified information flows upward:

```text
Chain Provider → CMIS → Chain Scout → Roberta
```

## Stage 1 — Project identity and repository rename ✅ Complete

The GitHub repository is:

```text
bhaygood29053-pixel/cmis
```

The canonical project-facing name is **CMIS**.

Stage 1 intentionally did **not** rename the Python package namespace. The existing package remains:

```text
liquidity_scout
```

for compatibility with working imports, tests, runtime module paths, deployment commands, transport integrations, and Roberta fixtures.

## Stage 2 — Documentation and deployment identity cleanup ✅ Complete

Stage 2 was completed through the stale-reference sweep tracked by Issue #195 and PR #202.

Accepted Stage 2 rules now reflected in current documentation:

- README branding and clone/install examples use `cmis`;
- architecture documents use `Roberta → Chain Scout → CMIS → Chain Provider`;
- Roberta is the normal user-facing coordinator rather than a peer beside a current Liquidity Scout product;
- repository links and operational wording use the `bhaygood29053-pixel/cmis` identity where the repository is intended;
- `liquidity_scout` import/module paths remain unchanged;
- historical `Liquidity Scout` wording is retained only where it clearly describes the original prototype or an intentionally retained compatibility interface;
- compatibility names such as `liquidity-scout.service`, `LIQUIDITY_SCOUT_SERVICE_NAME`, and `liquidity_scout.*` may remain where renaming them would be a runtime migration rather than documentation cleanup;
- Scout/CMIS capability documentation is synchronized to the accepted CMIS `1.8.0` evidence/intelligence-foundation boundary;
- Solana documentation reflects the completed Phase 10 read-only provider/runtime foundation;
- CMIS Phase 11 read-only Verified Intelligence is distinguished from Roberta's separately named future Controlled Execution milestone;
- current pre-trade documentation reflects bounded route-scoped XDEX evidence without weakening execution safety boundaries.

Stage 2 changes project-facing identity/documentation only. It does not rename Python imports, systemd compatibility interfaces, or runtime modules.

## Stage 3 — Optional Python/runtime namespace migration ⬜ Not started

A future internal migration may consider moving from:

```text
liquidity_scout
```

to a canonical CMIS package namespace.

This is optional and must be a separate tested milestone because it can affect:

- imports;
- tests;
- module entry points;
- GitHub Actions;
- systemd unit/configuration names;
- deployment scripts;
- Roberta integration fixtures;
- local operational instructions.

A compatibility namespace/alias may need to remain for a transition period if this work is ever authorized.

Stage 3 must not be started merely to remove historical strings from the repository. Compatibility names are allowed until an explicit runtime migration is accepted.

## Naming boundary

**CMIS** owns deterministic market facts, tokenomics, evidence, verification, proof quality, risk, historical intelligence, bounded pre-trade analysis, and chain-provider normalization.

**Chain Scouts** own chain-specific investigation and interpretation.

**Roberta** owns user intent, policy, coordination, and final user-facing synthesis.

The GitHub repository identity reflects CMIS's architectural role. The compatibility `liquidity_scout` namespace reflects implementation history and does not alter authority ownership.

## Safety boundary

The identity migration adds no transaction construction, signing, broadcasting, custody, trading, autonomous execution, bridge transfer, or value movement.
