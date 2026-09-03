#!/usr/bin/env python3
"""Read-only live corroboration of the accepted Warp destination reference."""

import json
import os

from liquidity_scout.providers.x1.warp_destination_settlement import (
    collect_warp_destination_settlement_evidence,
)

DEST_TX_SIG = (
    "4PMmzc8Hy1qq7i5AQ2FGRgEi32ZS1DcZS9y7b86xfqaX7wNiFC2t5FWBddj8SsE5cMGW5zfkRRaTFmMgy5ChiuqG"
)
DEST_SLOT = 68029675

result = collect_warp_destination_settlement_evidence(
    transaction_signature=DEST_TX_SIG,
    slot=DEST_SLOT,
    rpc_url=os.getenv("X1_RPC_URL", "https://rpc.mainnet.x1.xyz"),
)
print(json.dumps(result, sort_keys=True))
if result["settlement_verified"] is not True:
    raise SystemExit("Warp destination settlement evidence did not verify")
