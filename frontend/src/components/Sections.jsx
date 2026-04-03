import { useState } from 'react';

function maskEmail(e) { if (!e) return '—'; const [u, d] = e.split('@'); return u.slice(0, 2) + '***@' + d; }
function maskPhone(p) { if (!p) return '—'; return p.slice(0, 4) + '****' + p.slice(-3); }

export function RiskSignals({ mode, confidence, secondsInactive, lastTrade, will }) {
  const now = new Date();
  const etTime = now.toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit' });
  const etHour = parseInt(now.toLocaleString('en-US', { timeZone: 'America/New_York', hour: 'numeric', hour12: false }));
  const etDay = now.toLocaleDateString('en-US', { timeZone: 'America/New_York', weekday: 'short' });
  const isMarketOpen = !['Sat', 'Sun'].includes(etDay) && etHour >= 9 && etHour < 16;

  const inactColor = confidence < 40 ? 'green' : confidence < 70 ? 'amber' : 'red';
  const lastValue = lastTrade?.value ?? 0;
  const lastLimit = will?.perOrderLimit ?? 10000;
  const lastSafe = lastValue <= lastLimit;
  const lastTicker = lastTrade?.symbol ?? '—';
  const tickerSafe = lastTicker === '—' || (will?.approvedTickers ?? []).includes(lastTicker);

  return (
    <div style={{ marginBottom: 20 }}>
      <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: 14 }}>⚡ Live Risk Signals</h3>
      <div className="signals-grid">
        <div className={`signal-card ${isMarketOpen ? 'green' : 'red'}`}>
          <div className="signal-card-title">Market Hours</div>
          <div className="signal-card-value" style={{ color: isMarketOpen ? 'var(--accent-green)' : 'var(--accent-red)' }}>
            <span className={`signal-dot ${isMarketOpen ? 'green' : 'red'}`}></span>
            {isMarketOpen ? 'OPEN' : 'CLOSED'}
          </div>
          <div className="signal-card-sub">{etTime} ET • {etDay}</div>
        </div>
        <div className={`signal-card ${inactColor}`}>
          <div className="signal-card-title">Inactivity Level</div>
          <div className="signal-card-value text-mono">{confidence.toFixed(0)}%</div>
          <div className="signal-card-sub">{secondsInactive}s inactive</div>
        </div>
        <div className={`signal-card ${lastSafe ? 'green' : 'red'}`}>
          <div className="signal-card-title">Last Trade Size</div>
          <div className="signal-card-value text-mono">${lastValue.toLocaleString()}</div>
          <div className="signal-card-sub">Limit: ${lastLimit.toLocaleString()}</div>
        </div>
        <div className={`signal-card ${tickerSafe ? 'green' : 'red'}`}>
          <div className="signal-card-title">Ticker Safety</div>
          <div className="signal-card-value" style={{ color: tickerSafe ? 'var(--accent-green)' : 'var(--accent-red)' }}>
            {lastTicker} {tickerSafe ? '✓' : '✗'}
          </div>
          <div className="signal-card-sub">{tickerSafe ? 'Approved' : 'Not approved'}</div>
        </div>
        <div className="signal-card green">
          <div className="signal-card-title">System Heartbeat</div>
          <div className="signal-card-value" style={{ color: 'var(--accent-green)' }}>
            <span className="signal-dot green"></span>ACTIVE
          </div>
          <div className="signal-card-sub">{new Date().toLocaleTimeString()}</div>
        </div>
        <div className="signal-card cyan">
          <div className="signal-card-title">Policy Version</div>
          <div className="signal-card-value" style={{ color: 'var(--accent-cyan)' }}>will.yaml</div>
          <div className="signal-card-sub">v1.0 • Active</div>
        </div>
      </div>
    </div>
  );
}

export function EmergencyContacts({ contacts, onTestAlert, lastNotified }) {
  const [open, setOpen] = useState(false);
  if (!contacts || contacts.length === 0) return null;
  return (
    <div className="collapsible">
      <div className="collapsible-header" onClick={() => setOpen(!open)}>
        <h3>🚨 Emergency Contacts</h3>
        <span className={`collapsible-toggle ${open ? 'open' : ''}`}>▼</span>
      </div>
      {open && (
        <div className="collapsible-body">
          <div className="contacts-grid">
            {contacts.map((c, i) => (
              <div className="contact-card" key={i}>
                <div className="contact-card-name">{c.name}</div>
                <div className="contact-card-detail">📧 {maskEmail(c.email)}</div>
                <div className="contact-card-detail">📱 {maskPhone(c.phone)}</div>
                <div className="contact-card-actions">
                  <button className="btn-test-alert" onClick={() => onTestAlert(c, i)}>Test Alert</button>
                  <span className="last-notified">
                    {lastNotified?.[i] ? `Last: ${lastNotified[i]}` : 'Never notified'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function FinancialWill({ will, onEdit }) {
  const [open, setOpen] = useState(false);
  if (!will) return null;
  return (
    <div className="collapsible">
      <div className="collapsible-header" onClick={() => setOpen(!open)}>
        <h3>📜 My Financial Will</h3>
        <span className={`collapsible-toggle ${open ? 'open' : ''}`}>▼</span>
      </div>
      {open && (
        <div className="collapsible-body">
          <div className="will-grid">
            <div className="will-item">
              <div className="will-item-label">Risk Tolerance</div>
              <div className="will-item-value">{will.riskTolerance}</div>
            </div>
            <div className="will-item">
              <div className="will-item-label">Daily Limit</div>
              <div className="will-item-value text-mono">${(will.dailyTradeLimit || 50000).toLocaleString()}</div>
            </div>
            <div className="will-item">
              <div className="will-item-label">Per-Order Limit</div>
              <div className="will-item-value text-mono">${(will.perOrderLimit || 10000).toLocaleString()}</div>
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <div className="will-item-label" style={{ marginBottom: 6 }}>Approved Tickers</div>
            <div className="ticker-chips">
              {(will.approvedTickers || []).map(t => <span className="ticker-chip" key={t}>{t}</span>)}
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <button className="btn-edit-will" onClick={onEdit}>✏️ Edit Will</button>
          </div>
        </div>
      )}
    </div>
  );
}

export function EditWillModal({ will, onSave, onClose }) {
  const [form, setForm] = useState({
    riskTolerance: will.riskTolerance || 'Moderate',
    dailyTradeLimit: String(will.dailyTradeLimit || 50000),
    perOrderLimit: String(will.perOrderLimit || 10000),
    approvedTickers: (will.approvedTickers || []).join(', '),
  });
  const set = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }));
  const save = () => {
    const tickers = form.approvedTickers.split(',').map(t => t.trim().toUpperCase()).filter(Boolean);
    onSave({
      riskTolerance: form.riskTolerance,
      dailyTradeLimit: parseFloat(form.dailyTradeLimit) || 50000,
      perOrderLimit: parseFloat(form.perOrderLimit) || 10000,
      approvedTickers: tickers,
    });
  };
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header"><h2>Edit Financial Will</h2><button className="modal-close" onClick={onClose}>×</button></div>
        <div className="form-group">
          <label>Risk Tolerance</label>
          <select value={form.riskTolerance} onChange={set('riskTolerance')}>
            <option>Conservative</option><option>Moderate</option><option>Aggressive</option>
          </select>
        </div>
        <div className="form-row">
          <div className="form-group"><label>Daily Trade Limit ($)</label><input type="number" value={form.dailyTradeLimit} onChange={set('dailyTradeLimit')} /></div>
          <div className="form-group"><label>Per-Order Limit ($)</label><input type="number" value={form.perOrderLimit} onChange={set('perOrderLimit')} /></div>
        </div>
        <div className="form-group"><label>Approved Tickers (comma separated)</label><input value={form.approvedTickers} onChange={set('approvedTickers')} /></div>
        <button className="btn-primary" onClick={save}>Save Changes</button>
      </div>
    </div>
  );
}

export function SettingsModal({ emailjsConfig, setEmailjsConfig, onClose }) {
  const [form, setForm] = useState(emailjsConfig);
  const set = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }));
  const save = () => { setEmailjsConfig(form); localStorage.setItem('wg_emailjs', JSON.stringify(form)); onClose(); };
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header"><h2>⚙️ Settings — EmailJS</h2><button className="modal-close" onClick={onClose}>×</button></div>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 16 }}>
          Configure EmailJS to send real email alerts to emergency contacts on mode transitions.
          Get free keys at <a href="https://emailjs.com" target="_blank" rel="noreferrer">emailjs.com</a>
        </p>
        <div className="form-group"><label>Service ID</label><input value={form.serviceId} onChange={set('serviceId')} placeholder="service_xxxxx" /></div>
        <div className="form-group"><label>Template ID</label><input value={form.templateId} onChange={set('templateId')} placeholder="template_xxxxx" /></div>
        <div className="form-group"><label>Public Key</label><input value={form.publicKey} onChange={set('publicKey')} placeholder="your_public_key" /></div>
        <button className="btn-primary" onClick={save}>Save Configuration</button>
      </div>
    </div>
  );
}
