from statistics import mean
from models import Signal

def _sma(values, n):
    if len(values) < n:
        raise ValueError(f"Need at least {n} candles, got {len(values)}")
    return mean(values[-n:])

def generate_signal(snapshot, settings):
    closes = [c.close for c in snapshot.candles]
    volumes = [c.volume for c in snapshot.candles]
    needed = max(settings.slow_sma, settings.momentum_lookback + 1, 3)
    if len(closes) < needed:
        raise ValueError(f"Need at least {needed} candles.")

    fast = _sma(closes, settings.fast_sma)
    slow = _sma(closes, settings.slow_sma)

    old = closes[-1 - settings.momentum_lookback]
    momentum = (closes[-1] / old - 1.0) if old else 0.0

    prior_vols = volumes[-21:-1] if len(volumes) >= 21 else volumes[:-1]
    baseline_vol = mean(prior_vols) if prior_vols else max(volumes[-1], 1e-12)
    volume_ratio = volumes[-1] / baseline_vol if baseline_vol else 1.0

    score = 0
    reasons = []

    if fast > slow:
        score += 2
        reasons.append("fast SMA above slow SMA")
    elif fast < slow:
        score -= 2
        reasons.append("fast SMA below slow SMA")

    if momentum >= 0.005:
        score += 1
        reasons.append(f"positive momentum {momentum:.2%}")
    elif momentum <= -0.005:
        score -= 1
        reasons.append(f"negative momentum {momentum:.2%}")

    if volume_ratio >= settings.volume_spike_ratio:
        # Volume confirms the direction of momentum; no blind bullish volume bonus.
        if momentum > 0:
            score += 1
            reasons.append(f"bullish volume spike {volume_ratio:.2f}x")
        elif momentum < 0:
            score -= 1
            reasons.append(f"bearish volume spike {volume_ratio:.2f}x")

    if score >= settings.buy_score:
        action = "BUY"
    elif score <= settings.sell_score:
        action = "SELL"
    else:
        action = "HOLD"

    # A bounded heuristic confidence, not a statistical probability.
    confidence = min(0.95, 0.50 + abs(score) * 0.10)

    return Signal(
        action=action,
        score=score,
        confidence=confidence,
        reason="; ".join(reasons) if reasons else "no strong setup",
        fast_sma=fast,
        slow_sma=slow,
        momentum=momentum,
        volume_ratio=volume_ratio,
    )
