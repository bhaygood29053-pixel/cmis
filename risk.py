def entry_allowed(snapshot, portfolio, settings):
    reasons = []
    if snapshot.liquidity_usd and snapshot.liquidity_usd < settings.min_liquidity_usd:
        reasons.append(
            f"liquidity ${snapshot.liquidity_usd:,.0f} below "
            f"${settings.min_liquidity_usd:,.0f} minimum"
        )
    if portfolio.position is not None:
        reasons.append("position already open")
    return (not reasons, reasons)

def exit_reason(snapshot, portfolio, settings):
    if portfolio.position is None:
        return None

    entry = portfolio.position.entry_price
    if entry <= 0:
        return None
    change = snapshot.price / entry - 1.0

    if change <= -settings.stop_loss_pct:
        return f"STOP_LOSS ({change:.2%})"
    if change >= settings.take_profit_pct:
        return f"TAKE_PROFIT ({change:.2%})"
    return None

def trade_budget(portfolio, settings):
    allocation = portfolio.quote_balance * settings.trade_allocation_pct
    max_by_portfolio = portfolio.quote_balance * settings.max_position_pct
    return max(0.0, min(allocation, max_by_portfolio))
