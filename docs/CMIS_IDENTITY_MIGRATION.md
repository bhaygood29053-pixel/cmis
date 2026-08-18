# CMIS Project Identity Migration

## Decision

The canonical project identity is **CMIS — Cross-Chain Market Intelligence Service**.

The historical **Liquidity Scout** name no longer describes the repository's primary architectural role. CMIS is the deterministic intelligence backend used by chain-specific Scouts, including X1 Scout and Solana Scout, which return verified information and evidence to Roberta.

Canonical architecture:

```text
User / transport
      ↓
Roberta — Oracle / Coordinator / user-facing voice
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

## Stage 1 — Project identity and repository rename

Target GitHub repository slug:

```text
bhaygood29053-pixel/cmis
```

The project-facing name should be **CMIS** rather than Liquidity Scout.

This stage intentionally does **not** rename the Python package namespace. The existing package remains:

```text
liquidity_scout
```

until a separately tested compatibility migration is accepted.

## Stage 2 — Documentation and deployment identity cleanup

After the GitHub repository rename:

- update README branding and clone/install examples to `cmis`;
- update Roberta documentation to refer to the CMIS repository;
- update repository links in contracts, deployment docs, CI documentation, and operational instructions where the repository slug is embedded;
- keep `liquidity_scout` import/module paths unchanged during this stage;
- verify CMIS and Roberta deterministic test suites and integration contracts.

## Stage 3 — Optional Python namespace migration

Only after Stage 1 and Stage 2 are stable, consider moving the implementation namespace from:

```text
liquidity_scout
```

to a canonical CMIS namespace.

That migration must be a separate milestone because it can affect imports, tests, module entry points, GitHub Actions, systemd commands, deployment scripts, and Roberta integration fixtures.

A temporary compatibility namespace may be retained if needed so existing operational commands do not break abruptly.

## Naming boundary

**CMIS** owns deterministic market facts, tokenomics, evidence, verification, proof quality, risk, historical intelligence, bounded pre-trade analysis, and chain-provider normalization.

**Chain Scouts** own chain-specific investigation and interpretation.

**Roberta** owns user intent, policy, coordination, and final user-facing synthesis.

The repository name should reflect the CMIS role rather than the original Liquidity Scout prototype identity.

## Safety boundary

This identity migration does not add transaction construction, signing, broadcasting, custody, trading, autonomous execution, or value movement.
