# Liquidity Scout Trader v0.1

A safe first version of an X1/XDEX agent that:

- verifies an existing AgentID (read-only);
- reads XDEX pool + OHLCV data from X1.Ninja;
- calculates a simple trend/momentum/volume signal;
- applies hard liquidity and position risk rules;
- paper-trades BUY/SELL/HOLD decisions;
- persists portfolio state and trade history;
- queues important, non-secret events for later HXMP review;
- **never signs or sends a real transaction**.

## Safety boundary

v0.1 is intentionally paper-only. It does **not** read a private key, seed phrase, or HXMP encryption key. It does not execute swaps or write HXMP records on-chain.

Do not put a seed phrase/private key in `.env`.

## 1. Install

From WSL2:

```bash
cd liquidity-scout-trader-v0.1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. Test it immediately in demo mode

```bash
python main.py --demo
```

Run continuously on synthetic data:

```bash
python main.py --demo --loop
```

Stop with `Ctrl+C`.

## 3. Configure your existing AgentID

Edit `.env`:

```text
AGENT_WALLET=YOUR_PUBLIC_X1_WALLET_ADDRESS
```

This wallet address is public. Do **not** paste your keypair/seed phrase.

On startup the bot calls:

```text
GET https://agentid-app.vercel.app/api/verify?wallet=<address>
```

and reports whether the wallet has a verified AgentID.

## 4. Get live XDEX data

X1.Ninja currently provides a free developer API for XDEX pools, trades, and OHLCV.

Get an API key at:

```text
https://x1.ninja/developers
```

Then add **only the API key** to your local `.env`:

```text
X1_NINJA_API_KEY=x1_your_key_here
```

The default pool is the AGI/XNT XDEX pool currently documented by AgentID:

```text
4sn8oCQWPikDxBkyRdd1S6bJ24oYjGF16aR7ZqCSXy4v
```

For this default pair, v0.1 also uses the documented AGI and wrapped-XNT
vaults through the X1 RPC. The OHLCV series drives the signal, while the
on-chain reserve ratio supplies the simulated fill price in **XNT per AGI**.
This avoids mixing X1.Ninja's USD-oriented market fields with an XNT paper balance.

If you change to another pool, replace `POOL_ADDRESS`, `BASE_TOKEN_VAULT`,
and `QUOTE_TOKEN_VAULT` together.

## 5. Run one live-data scan

```bash
python main.py
```

Run continuously:

```bash
python main.py --loop
```

Default polling is once per minute.

## Strategy in v0.1

This is deliberately simple and auditable.

BUY score components:

- fast SMA > slow SMA: +2
- positive momentum >= 0.5%: +1
- volume spike >= 1.5x while momentum is positive: +1

SELL score mirrors the bearish conditions.

Defaults:

- BUY at score >= +3
- SELL at score <= -2
- otherwise HOLD

The displayed "confidence" is a bounded heuristic derived from the score. It is **not** a statistical win probability.

## Risk rules

Default controls:

- minimum pool liquidity: $50,000;
- one open position at a time;
- normal trade budget: 10% of remaining paper XNT;
- maximum position allocation: 25%;
- stop loss: 5%;
- take profit: 10%.

Edit `.env` to change them.

## Paper state

Generated files:

```text
data/state.json          current paper portfolio
data/trades.csv          simulated fills and P/L
data/decisions.jsonl     every scan and signal
data/hxmp_queue.jsonl    important events awaiting human review
```

Reset all paper state:

```bash
python main.py --reset
```

## HXMP integration boundary

HXMP currently requires state-changing operations to be previewed and explicitly approved. v0.1 therefore does **not** auto-write trading memory to X1.

To inspect events that the bot thinks are important enough to become HXMP memories/receipts:

```bash
python main.py --hxmp-review
```

That queue can become the input to v0.2's HXMP preview/approval workflow.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## What v0.1 does NOT do yet

- no live trading;
- no wallet signing;
- no automatic HXMP on-chain writes;
- no AI/LLM judgment;
- no Telegram alerts;
- no whale-wallet clustering;
- no backtester yet;
- no transaction-cost/slippage model yet.

Those omissions are intentional. First prove that the data feed and paper strategy behave correctly.

## Recommended path to v0.2

1. Collect live paper-trade history.
2. Add a historical backtester against X1.Ninja OHLCV.
3. Add slippage + fee assumptions.
4. Add large-swap / LP event detection from `/v1/trades/{pool}`.
5. Add performance metrics: win rate, profit factor, max drawdown.
6. Add HXMP dry-run/preview bridge.
7. Only after evidence is good, design a human-approved live-trade executor.
