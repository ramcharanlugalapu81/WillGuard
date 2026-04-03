// ─── System State Engine ─────────────────────────────
// Tracks user activity, manages COPILOT → GUARDIAN → LOCKDOWN transitions.

export const MODES = { COPILOT: 'copilot', GUARDIAN: 'guardian', LOCKDOWN: 'lockdown' };

// Demo-mode thresholds (short for presentations)
export const DEMO_THRESHOLDS = { guardian: 8, lockdown: 20 };
// Real-mode thresholds
export const REAL_THRESHOLDS = { guardian: 14400, lockdown: 86400 };

export function getModeColor(mode) {
  switch (mode) {
    case MODES.COPILOT: return 'var(--accent-cyan)';
    case MODES.GUARDIAN: return 'var(--accent-amber)';
    case MODES.LOCKDOWN: return 'var(--accent-red)';
    default: return 'var(--text-muted)';
  }
}

export function getModeIcon(mode) {
  switch (mode) {
    case MODES.COPILOT: return '✅';
    case MODES.GUARDIAN: return '🛡';
    case MODES.LOCKDOWN: return '🔒';
    default: return '⚡';
  }
}

export function getModeDescription(mode) {
  switch (mode) {
    case MODES.COPILOT:
      return 'System is actively monitoring. All trades are evaluated through ArmorClaw enforcement.';
    case MODES.GUARDIAN:
      return 'Inactivity detected. All new trades are paused. Existing positions are held safely.';
    case MODES.LOCKDOWN:
      return 'Extended inactivity. Full trade freeze is active. Emergency contacts have been notified.';
    default: return '';
  }
}

// ─── ArmorClaw Enforcement Engine ────────────────────
export function enforceTradeRules({ symbol, quantity, side, price, mode, will }) {
  const orderValue = quantity * price;
  const { approvedTickers, perOrderLimit, dailyTradeLimit } = will;

  // 1. Size Shock signal
  const sizeShock = Math.min(orderValue / perOrderLimit, 1.0);
  // 2. Suddenness (simulated market volatility)
  const suddenness = Math.random() * 0.3;
  // 3. Goal Alignment
  const isApproved = approvedTickers.map(t => t.toUpperCase()).includes(symbol.toUpperCase());
  const goalAlignment = isApproved ? 0 : 0.8;

  const riskScore = sizeShock * 0.4 + suddenness * 0.3 + goalAlignment * 0.3;
  const riskData = {
    total: parseFloat(riskScore.toFixed(3)),
    sizeShock: parseFloat(sizeShock.toFixed(3)),
    suddenness: parseFloat(suddenness.toFixed(3)),
    goalAlignment: parseFloat(goalAlignment.toFixed(3)),
  };

  // Enforcement rules in priority order
  if (mode === MODES.LOCKDOWN) {
    return { zone: 'FREEZE', reason: 'System in Lockdown — all trading is frozen', risk: riskData };
  }
  if (mode === MODES.GUARDIAN) {
    return { zone: 'FREEZE', reason: 'Guardian mode — new trades blocked until activity resumes', risk: riskData };
  }
  if (!isApproved) {
    return { zone: 'FREEZE', reason: `Ticker ${symbol.toUpperCase()} not in approved universe`, risk: riskData };
  }
  if (orderValue > perOrderLimit) {
    return { zone: 'FREEZE', reason: `Exceeds per-order limit of $${perOrderLimit.toLocaleString()}`, risk: riskData };
  }
  if (riskScore > 0.65) {
    return { zone: 'NOTIFY', reason: 'High risk score — requires manual confirmation', risk: riskData };
  }
  return { zone: 'EXECUTE', reason: 'Trade approved — within all safety parameters', risk: riskData };
}
