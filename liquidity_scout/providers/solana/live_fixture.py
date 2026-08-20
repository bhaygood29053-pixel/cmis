"""Repository-owned read-only Solana Token-2022 readiness fixture.

This fixture exists only to make live RPC contract verification reproducible. It
is not a market benchmark, safety endorsement, pricing authority, or execution
configuration.
"""

from __future__ import annotations

from dataclasses import dataclass

from liquidity_scout.providers.solana.rpc import TOKEN_2022_PROGRAM_ID


@dataclass(frozen=True)
class SolanaLiveMintFixture:
    name: str
    mint: str
    program_kind: str
    program_id: str
    decimals: int
    provenance_urls: tuple[str, ...]
    scope: str = "read_only_rpc_contract_probe"
    execution_authorized: bool = False


# Solana's official documentation identifies this exact mint as PYUSD on Solana
# and explicitly maps it to the Token-2022 program with 6 decimals.
SOLANA_TOKEN_2022_LIVE_FIXTURE = SolanaLiveMintFixture(
    name="PYUSD",
    mint="2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo",
    program_kind="token_2022",
    program_id=TOKEN_2022_PROGRAM_ID,
    decimals=6,
    provenance_urls=(
        "https://solana.com/news/pyusd-paypal-solana-developer",
        "https://solana.com/docs/payments/how-payments-work",
    ),
)


__all__ = [
    "SOLANA_TOKEN_2022_LIVE_FIXTURE",
    "SolanaLiveMintFixture",
]
