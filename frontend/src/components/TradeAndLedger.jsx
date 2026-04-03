import { useState } from 'react';

export function TradeForm({ onSubmit, disabled }) {
  const [symbol, setSymbol] = useState('AAPL');
  const [quantity, setQuantity] = useState('1');
  const [side, setSide] = useState('buy');
  const [price, setPrice] = useState('185.50');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (disabled) return;
    onSubmit({ symbol: symbol.toUpperCase(), quantity: parseFloat(quantity) || 1, side, price: parseFloat(price) || 150 });
  };

  return (
    <div className="panel" style={{ position: 'relative' }}>
      {disabled && (
        <div className="trade-lockdown-overlay">
          <div className="trade-lockdown-msg">🔒 Trading Frozen — System in Lockdown</div>
        </div>
      )}
      <div className="panel-header">
        <span className="panel-title">Submit Trade</span>
        <span className="panel-badge" style={{ background: 'rgba(0,212,255,0.08)', color: 'var(--accent-cyan)', border: '1px solid rgba(0,212,255,0.2)' }}>ArmorClaw</span>
      </div>
      <form className="trade-form" onSubmit={handleSubmit}>
        <div className="form-row">
          <div>
            <label>Symbol</label>
            <input value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="AAPL" />
          </div>
          <div>
            <label>Quantity</label>
            <input type="number" value={quantity} onChange={e => setQuantity(e.target.value)} min="1" />
          </div>
        </div>
        <div className="form-row">
          <div>
            <label>Side</label>
            <select value={side} onChange={e => setSide(e.target.value)}>
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </select>
          </div>
          <div>
            <label>Est. Price ($)</label>
            <input type="number" step="0.01" value={price} onChange={e => setPrice(e.target.value)} />
          </div>
        </div>
        <button className="btn-submit-trade" type="submit" disabled={disabled}>
          ⚡ Evaluate & Submit
        </button>
      </form>
    </div>
  );
}

export function DecisionLedger({ entries, filter, setFilter, onExport }) {
  const filtered = filter === 'ALL' ? entries : entries.filter(e => e.zone === filter);
  return (
    <div className="panel ledger-panel">
      <div className="panel-header">
        <span className="panel-title">Decision Ledger</span>
        <span className="ledger-count">{entries.length} ENTRIES</span>
      </div>
      <div className="ledger-toolbar">
        {['ALL', 'EXECUTE', 'NOTIFY', 'FREEZE'].map(f => (
          <button key={f} className={`ledger-filter ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>{f}</button>
        ))}
        <button className="ledger-export" onClick={onExport}>📥 Export JSON</button>
      </div>
      {filtered.length === 0 ? (
        <div className="empty-state">No entries yet. Submit a trade or trigger a mode change.</div>
      ) : (
        <div style={{ maxHeight: 320, overflowY: 'auto' }}>
          <table className="ledger-table">
            <thead><tr><th>ZONE</th><th>ACTION</th><th>RISK</th><th>MODE</th><th>REASON</th><th>TIME</th></tr></thead>
            <tbody>
              {filtered.map((e, i) => (
                <tr key={i}>
                  <td><span className={`zone-badge ${e.zone.toLowerCase()}`}>{e.zone}</span></td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>{e.action}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>{e.risk != null ? e.risk.toFixed(3) : '—'}</td>
                  <td><span className={`zone-badge ${e.mode}`}>{e.mode.toUpperCase()}</span></td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', maxWidth: 220 }}>{e.reason}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--text-muted)' }}>{e.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
