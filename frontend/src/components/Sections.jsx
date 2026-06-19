import { useState } from 'react';

function maskEmail(e) { if (!e) return '—'; const [u, d] = e.split('@'); return u.slice(0, 2) + '***@' + d; }
function maskPhone(p) { if (!p) return '—'; return p.slice(0, 4) + '****' + p.slice(-3); }

export function RiskSignals({ mode, confidence, secondsInactive, lastTrade, will, onOpenClawBot }) {
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
      <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: 14 }}>Live Risk Signals</h3>
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
            {lastTicker} {tickerSafe ? '' : ''}
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
          <div className="signal-card-title">Database</div>
          <div className="signal-card-value" style={{ color: 'var(--accent-cyan)' }}>SQLite</div>
          <div className="signal-card-sub">Persistent • Active</div>
        </div>
        <div className="signal-card clawbot-signal" onClick={onOpenClawBot} style={{ cursor: 'pointer' }}>
          <div className="signal-card-title">ClawBot</div>
          <div className="signal-card-value" style={{ color: '#0ea5e9', fontSize: '1.5rem' }}></div>
          <div className="signal-card-sub">Trade Terminal</div>
        </div>
      </div>
    </div>
  );
}

export function EmergencyContacts({ contacts, onTestAlert, notificationHistory, notificationStatus }) {
  const [open, setOpen] = useState(true);
  if (!contacts || contacts.length === 0) return null;
  return (
    <div className="collapsible">
      <div className="collapsible-header" onClick={() => setOpen(!open)}>
        <h3>Emergency Contacts & Email Notifications</h3>
        <span className={`collapsible-toggle ${open ? 'open' : ''}`}>▼</span>
      </div>
      {open && (
        <div className="collapsible-body">
          {notificationStatus && (
            <div className={`notification-status-bar ${notificationStatus.configured ? 'live' : 'sim'}`}>
              <span>EmailJS: {notificationStatus.configured ? `Live via backend` : 'Simulation Mode'}</span>
              {!notificationStatus.configured && (
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Add EmailJS credentials in backend .env to enable real emails</span>
              )}
            </div>
          )}
          <div className="contacts-grid">
            {contacts.map((c, i) => {
              const recentNotif = (notificationHistory || []).find(n =>
                n.contact_name === c.name || (n.contact_id === c.id)
              );
              return (
                <div className="contact-card" key={i}>
                  <div className="contact-card-name">{c.name}</div>
                  <div className="contact-card-detail">{maskEmail(c.email)}</div>
                  <div className="contact-card-detail">{c.phone || maskPhone(c.phone)}</div>
                  <div className="contact-card-actions">
                    <button className="btn-test-alert" onClick={() => onTestAlert(c, i)}>Send Test Email</button>
                    <span className="last-notified">
                      {recentNotif
                        ? `Last: ${new Date(recentNotif.created_at).toLocaleString()}`
                        : 'Never notified'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Notification History */}
          {notificationHistory && notificationHistory.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h4 style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: 10, color: 'var(--text-secondary)' }}>Email History</h4>
              <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                {notificationHistory.slice(0, 10).map((n, i) => (
                  <div key={i} className="notification-history-item">
                    <div className="notif-row">
                      <span className={`notif-badge ${n.direction === 'inbound' ? 'inbound' : n.status}`}>
                        {n.direction === 'inbound' ? 'IN' : n.status === 'sent' ? 'SENT' : n.status === 'simulated' ? 'SIM' : 'FAIL'}
                      </span>
                      <span className="notif-to">{n.contact_name || 'Unknown'}</span>
                      <span className="notif-time">{new Date(n.created_at).toLocaleString()}</span>
                    </div>
                    <div className="notif-body">{n.message_body?.slice(0, 100)}...</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function FinancialWill({ will, onEdit }) {
  const [open, setOpen] = useState(true);
  if (!will) return null;
  return (
    <div className="collapsible">
      <div className="collapsible-header" onClick={() => setOpen(!open)}>
        <h3>My Financial Will</h3>
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
          <div className="will-grid" style={{ marginTop: 14 }}>
            <div className="will-item">
              <div className="will-item-label">Guardian Inactivity Timer</div>
              <div className="will-item-value text-mono">{(will.guardianTimer || 10)}s</div>
            </div>
            <div className="will-item">
              <div className="will-item-label">Lockdown extended Timer</div>
              <div className="will-item-value text-mono">{(will.lockdownTimer || 15)}s</div>
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <div className="will-item-label" style={{ marginBottom: 6 }}>Approved Tickers</div>
            <div className="ticker-chips">
              {(will.approvedTickers || []).map(t => <span className="ticker-chip" key={t}>{t}</span>)}
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <button className="btn-edit-will" onClick={onEdit}>Edit Will</button>
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
    guardianTimer: String(will.guardianTimer || 10),
    lockdownTimer: String(will.lockdownTimer || 15),
  });
  const set = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }));
  const save = () => {
    const tickers = form.approvedTickers.split(',').map(t => t.trim().toUpperCase()).filter(Boolean);
    onSave({
      riskTolerance: form.riskTolerance,
      dailyTradeLimit: parseFloat(form.dailyTradeLimit) || 50000,
      perOrderLimit: parseFloat(form.perOrderLimit) || 10000,
      approvedTickers: tickers,
      guardianTimer: form.guardianTimer,
      lockdownTimer: form.lockdownTimer,
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
        <div className="form-row">
          <div className="form-group"><label>Guardian Timer (seconds)</label><input type="number" value={form.guardianTimer} onChange={set('guardianTimer')} /></div>
          <div className="form-group"><label>Lockdown Timer (seconds)</label><input type="number" value={form.lockdownTimer} onChange={set('lockdownTimer')} /></div>
        </div>
        <div className="form-group"><label>Approved Tickers (comma separated)</label><input value={form.approvedTickers} onChange={set('approvedTickers')} /></div>
        <button className="btn-primary" onClick={save}>Save Changes</button>
      </div>
    </div>
  );
}

export function SettingsModal({ notificationStatus, notificationHistory, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header"><h2>Settings — Notifications</h2><button className="modal-close" onClick={onClose}>×</button></div>

        {/* Twilio Status */}
        <div className="settings-section">
          <h3>EmailJS Status</h3>
          {notificationStatus ? (
            <div className={`notification-status-bar ${notificationStatus.configured ? 'live' : 'sim'}`}>
              <div>
                <strong>Status:</strong> {notificationStatus.configured ? 'Live' : 'Simulation Mode'}
              </div>
              {notificationStatus.phone_number && (
                <div><strong>From:</strong> {notificationStatus.phone_number}</div>
              )}
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 6 }}>
                {notificationStatus.configured
                  ? 'Email alerts are sent via EmailJS when Guardian/Lockdown modes activate. Emergency contacts can click the Magic Link to restore Co-Pilot mode.'
                  : 'Configure EMAILJS_SERVICE_ID, EMAILJS_TEMPLATE_ID, EMAILJS_PUBLIC_KEY, and EMAILJS_PRIVATE_KEY in backend/.env to enable real Email notifications.'}
              </div>
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>Backend not connected — cannot check EmailJS status.</p>
          )}
        </div>

        {/* How Reply-to-Restore Works */}
        <div className="settings-section">
          <h3>Magic Link Restore Flow</h3>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            <p>When <strong>Lockdown Mode</strong> activates:</p>
            <ol style={{ paddingLeft: 20, marginTop: 8 }}>
              <li>Emergency contacts receive an Email alert from EmailJS</li>
              <li>The Email contains a unique <strong>Magic Link</strong></li>
              <li>Contact clicks the link, which opens in their browser</li>
              <li>The WillGuard backend verifies and logs the click</li>
              <li>System automatically transitions back to <strong>Co-Pilot</strong> mode</li>
            </ol>
          </div>
        </div>

        {/* Recent Notifications */}
        <div className="settings-section">
          <h3>Recent Notifications ({notificationHistory?.length || 0})</h3>
          {notificationHistory && notificationHistory.length > 0 ? (
            <div style={{ maxHeight: 200, overflowY: 'auto' }}>
              {notificationHistory.slice(0, 10).map((n, i) => (
                <div key={i} className="notification-history-item">
                  <div className="notif-row">
                    <span className={`notif-badge ${n.direction === 'inbound' ? 'inbound' : n.status}`}>
                      {n.direction === 'inbound' ? '' : ''} {n.status?.toUpperCase()}
                    </span>
                    <span className="notif-to">{n.contact_name || 'System'}</span>
                    <span className="notif-time">{new Date(n.created_at).toLocaleString()}</span>
                  </div>
                  <div className="notif-body">{n.message_body?.slice(0, 120)}</div>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>No notifications sent yet.</p>
          )}
        </div>

        <button className="btn-primary" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
