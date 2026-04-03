import { getModeIcon, getModeDescription, getModeColor } from './Engine';

export function SystemModePanel({ mode, secondsInactive, confidence, demoRunning }) {
  const icon = getModeIcon(mode);
  const desc = getModeDescription(mode);
  const modeName = mode === 'copilot' ? 'Co-Pilot' : mode === 'guardian' ? 'Guardian' : 'Lockdown';

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">System Mode</span>
        <span className={`panel-badge ${demoRunning ? 'demo' : 'live'}`}>
          {demoRunning ? '● DEMO' : '● LIVE'}
        </span>
      </div>
      <div className="mode-display">
        <div className={`mode-circle ${mode}`}>{icon}</div>
        <div className={`mode-name ${mode}`}>{modeName}</div>
        <div className="mode-desc">{desc}</div>
        <div className="inactivity-bar">
          <div className="inactivity-bar-label">
            <span>Inactivity Confidence</span>
            <span className="text-mono">{confidence.toFixed(0)}%</span>
          </div>
          <div className="inactivity-bar-track">
            <div className={`inactivity-bar-fill ${mode}`} style={{ width: `${Math.min(confidence, 100)}%` }}></div>
          </div>
        </div>
        <div className="inactivity-timer">
          Inactive: <span style={{ color: getModeColor(mode) }}>{secondsInactive}s</span>
        </div>
      </div>
    </div>
  );
}

export function RiskScorePanel({ risk }) {
  const score = risk?.total ?? 0;
  const label = score < 0.4 ? 'LOW RISK' : score < 0.7 ? 'MODERATE RISK' : 'HIGH RISK';
  const labelClass = score < 0.4 ? 'low' : score < 0.7 ? 'moderate' : 'high';
  const gaugeColor = score < 0.4 ? 'var(--accent-green)' : score < 0.7 ? 'var(--accent-amber)' : 'var(--accent-red)';

  // SVG semicircle gauge
  const cx = 90, cy = 85, r = 70;
  const startAngle = Math.PI;
  const endAngle = 0;
  const sweepAngle = startAngle - (startAngle - endAngle) * score;
  const arcPath = (a1, a2) => {
    const x1 = cx + r * Math.cos(a1), y1 = cy - r * Math.sin(a1);
    const x2 = cx + r * Math.cos(a2), y2 = cy - r * Math.sin(a2);
    const large = (a1 - a2) > Math.PI ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 0 ${x2} ${y2}`;
  };

  const signals = [
    { name: 'Size Shock', value: risk?.sizeShock ?? 0, weight: '40%' },
    { name: 'Suddenness', value: risk?.suddenness ?? 0, weight: '30%' },
    { name: 'Goal Align.', value: risk?.goalAlignment ?? 0, weight: '30%' },
  ];

  const getBarColor = (v) => v < 0.4 ? 'var(--accent-green)' : v < 0.7 ? 'var(--accent-amber)' : 'var(--accent-red)';

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Risk Score</span>
        <span className={`risk-gauge-label ${labelClass}`}>{label}</span>
      </div>
      <div className="risk-gauge-container">
        <svg className="risk-gauge-svg" viewBox="0 0 180 100">
          <path d={arcPath(Math.PI, 0)} fill="none" stroke="var(--bg-elevated)" strokeWidth="10" strokeLinecap="round" />
          <path d={arcPath(Math.PI, sweepAngle)} fill="none" stroke={gaugeColor} strokeWidth="10" strokeLinecap="round"
            style={{ transition: 'all 0.6s ease', filter: `drop-shadow(0 0 6px ${gaugeColor})` }} />
          <text x={cx} y={cy - 8} textAnchor="middle" fill="var(--text-primary)" fontFamily="var(--font-mono)" fontSize="22" fontWeight="700">
            {score.toFixed(3)}
          </text>
        </svg>
        <div className="risk-breakdown">
          {signals.map(s => (
            <div className="risk-signal" key={s.name}>
              <span className="risk-signal-name">{s.name} <span className="text-muted">({s.weight})</span></span>
              <div className="risk-signal-bar">
                <div className="risk-signal-fill" style={{ width: `${s.value * 100}%`, background: getBarColor(s.value) }}></div>
              </div>
              <span className="risk-signal-value">{s.value.toFixed(3)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function PortfolioPanel({ portfolio }) {
  const { totalValue, cash, positions, history } = portfolio;
  // Simple SVG sparkline
  const h = 40, w = 200;
  const min = Math.min(...history), max = Math.max(...history);
  const range = max - min || 1;
  const points = history.map((v, i) => `${(i / (history.length - 1)) * w},${h - ((v - min) / range) * (h - 4) - 2}`).join(' ');

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Portfolio</span>
        <span className="panel-badge simulated">SIMULATED</span>
      </div>
      <div style={{ display: 'flex', gap: 28, marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>TOTAL VALUE</div>
          <div className="text-mono" style={{ fontSize: '1.5rem', fontWeight: 700 }}>${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
        </div>
        <div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>CASH</div>
          <div className="text-mono" style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--accent-green)' }}>${cash.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
        </div>
        <div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>POSITIONS</div>
          <div className="text-mono" style={{ fontSize: '1.1rem', fontWeight: 600 }}>{positions.length}</div>
        </div>
      </div>
      <div className="sparkline-container">
        <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
          <polyline points={points} fill="none" stroke="var(--accent-cyan)" strokeWidth="1.5" style={{ filter: 'drop-shadow(0 0 3px rgba(0,212,255,0.4))' }} />
        </svg>
      </div>
      {positions.length > 0 && (
        <div className="positions-list">
          {positions.map(p => (
            <div className="position-item" key={p.symbol}>
              <div className="position-ticker">
                <div className="position-ticker-badge">{p.symbol.slice(0, 3)}</div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{p.symbol}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{p.qty} shares</div>
                </div>
              </div>
              <div className="position-details">
                <div className={`position-value ${p.pnl >= 0 ? 'positive' : 'negative'}`}>
                  {p.pnl >= 0 ? '+' : ''}${p.pnl.toFixed(2)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
