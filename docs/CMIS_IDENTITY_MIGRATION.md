# CMIS Project Identity Migration

## Decision

The canonical project identity is **CMIS — Cross-Chain Market Intelligence Service**.

The historical **Liquidity Scout** name describes the original prototype, but it no longer describes the repository's primary architectural role. CMIS is the deterministic intelligence backend used by chain-specific Scouts, including X1 Scout and Solana Scout, which return verified information and evidence to Roberta.

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

## Stage 1 — Project identity and repository rename ✅ Complete

The GitHub repository is now:

```text
bhaygood29053-pixel/cmis
```

The canonical project-facing name is **CMIS**.

This stage intentionally did **not** rename the Python package namespace. The existing package remains:

```text
liquidity_scout
```

for compatibility with existing imports, tests, runtime module paths, deployment commands, and integration fixtures.

## Stage 2 — Documentation and deployment identity cleanup 🚧 In progress

Stage 2 normalizes project-facing references while preserving the working runtime namespace.

Accepted Stage 2 rules:

- README branding and clone/install examples use `cmis`;
- Roberta documentation refers to the separate **CMIS repository**, not the Liquidity Scout repository;
- repository links and operational documentation should use the new GitHub slug where the repository identity is intended;
- `liquidity_scout` import/module paths remain unchanged during this stage;
- historical references may retain the Liquidity Scout name when describing the original prototype or historical artifact;
- no runtime behavior changes are required merely to complete the identity migration.

A broader stale-reference sweep may be completed incrementally because historical issues, PRs, old filenames, and compatibility package paths are not automatically renamed.

## Stage 3 — Optional Python namespace migration ⬜ Not started

Only after Stage 1 and Stage 2 are stable should the implementation namespace be considered for migration from:

```text
liquidity_scout
```

to a canonical CMIS namespace.

This must be a separate tested milestone because it can affect:

- imports;
- tests;
- module entry points;
- GitHub Actions;
- systemd commands;
- deployment scripts;
- Roberta integration fixtures;
- local operational instructions.

A temporary compatibility namespace may be retained if needed so existing operational commands do not break abruptly.

## Naming boundary

**CMIS** owns deterministic market facts, tokenomics, evidence, verification, proof quality, risk, historical intelligence, bounded pre-trade analysis, and chain-provider normalization.

**Chain Scouts** own chain-specific investigation and interpretation.

**Roberta** owns user intent, policy, coordination, and final user-facing synthesis.

The GitHub repository name now reflects CMIS's architectural role rather than the original Liquidity Scout prototype identity.

## Safety boundary

This identity migration does not add transaction construction, signing, broadcasting, custody, trading, autonomous execution, or value movement.
