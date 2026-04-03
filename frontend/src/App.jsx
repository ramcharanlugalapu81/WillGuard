import { useState, useEffect, useRef, useCallback } from 'react';
import { AuthPages } from './components/Auth';
import { MODES, DEMO_THRESHOLDS, REAL_THRESHOLDS, enforceTradeRules, getModeColor } from './components/Engine';
import { SystemModePanel, RiskScorePanel, PortfolioPanel } from './components/Panels';
import { TradeForm, DecisionLedger } from './components/TradeAndLedger';
import { RiskSignals, EmergencyContacts, FinancialWill, EditWillModal, SettingsModal } from './components/Sections';
import ToastContainer, { useToasts } from './components/Toasts';
import emailjs from 'emailjs-com';

// ─── Helpers ─────────────────────────────────────────
function timeStr() { return new Date().toLocaleTimeString(); }
function initials(name) { return (name || 'U').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2); }

function loadLedger() { try { return JSON.parse(localStorage.getItem('wg_ledger') || '[]'); } catch { return []; } }
function saveLedger(entries) { localStorage.setItem('wg_ledger', JSON.stringify(entries)); }
function loadEmailJS() { try { return JSON.parse(localStorage.getItem('wg_emailjs') || '{}'); } catch { return {}; } }

export default function App() {
  // ─── Auth State ──────────────────────────────────
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const email = localStorage.getItem('wg_current_user');
    if (email) {
      const stored = localStorage.getItem(`wg_user_${email}`);
      if (stored) { setUser(JSON.parse(stored)); }
    }
    setAuthChecked(true);
  }, []);

  if (!authChecked) return null;
  if (!user) return <AuthPages onLogin={setUser} />;
  return <Dashboard user={user} setUser={setUser} />;
}

function Dashboard({ user, setUser }) {
  // ─── Core State ──────────────────────────────────
  const [mode, setMode] = useState(MODES.COPILOT);
  const [demoMode, setDemoMode] = useState(true); // Start in demo mode (short thresholds)
  const [demoRunning, setDemoRunning] = useState(false);
  const [secondsInactive, setSecondsInactive] = useState(0);
  const [ledger, setLedger] = useState(loadLedger);
  const [ledgerFilter, setLedgerFilter] = useState('ALL');
  const [risk, setRisk] = useState({ total: 0, sizeShock: 0, suddenness: 0, goalAlignment: 0 });
  const [flash, setFlash] = useState(null);
  const [will, setWill] = useState(user.will);
  const [showEditWill, setShowEditWill] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [emailjsConfig, setEmailjsConfig] = useState(loadEmailJS);
  const [lastNotified, setLastNotified] = useState({});
  const [lastTrade, setLastTrade] = useState(null);
  const [portfolio, setPortfolio] = useState({
    totalValue: 100000, cash: 100000, positions: [],
    history: [100000, 100200, 99800, 100400, 100100, 100600, 100300, 100800, 100500, 100000],
  });
  const [activeNav, setActiveNav] = useState('dashboard');

  const { toasts, addToast, removeToast } = useToasts();

  const lastActivityRef = useRef(Date.now());
  const demoTimerRef = useRef(null);
  const prevModeRef = useRef(mode);
  const notifiedGuardianRef = useRef(false);
  const notifiedLockdownRef = useRef(false);

  const thresholds = demoMode ? DEMO_THRESHOLDS : REAL_THRESHOLDS;

  // ─── Persist ledger on change ────────────────────
  useEffect(() => { saveLedger(ledger); }, [ledger]);

  // ─── Add Ledger Entry ────────────────────────────
  const addLedgerEntry = useCallback((zone, action, riskVal, currentMode, reason) => {
    setLedger(prev => [{ zone, action, risk: riskVal, mode: currentMode, reason, time: timeStr() }, ...prev]);
  }, []);

  // ─── Send Email Notification ─────────────────────
  const sendEmail = useCallback((contact, contactIndex, subject, body) => {
    const cfg = emailjsConfig;
    if (!cfg.serviceId || !cfg.templateId || !cfg.publicKey) {
      addToast('info', '📧 Email Skipped', `EmailJS not configured. Would notify ${contact.name}`);
      return;
    }
    emailjs.send(cfg.serviceId, cfg.templateId, {
      to_email: contact.email, to_name: contact.name, subject, message: body,
    }, cfg.publicKey).then(() => {
      addToast('info', '📧 Alert Sent', `Emergency alert sent to ${contact.name}`);
      setLastNotified(p => ({ ...p, [contactIndex]: timeStr() }));
    }).catch(() => {
      addToast('freeze', 'Email Failed', `Could not send alert to ${contact.name}`);
    });
  }, [emailjsConfig, addToast]);

  // ─── Mode Transition ────────────────────────────
  const transitionMode = useCallback((newMode) => {
    if (newMode === prevModeRef.current) return;
    setFlash(newMode);
    setTimeout(() => setFlash(null), 400);
    setMode(newMode);
    addLedgerEntry('MODE_CHANGE', `→ ${newMode.toUpperCase()}`, null, newMode,
      newMode === MODES.GUARDIAN ? 'Inactivity detected — trades paused' :
      newMode === MODES.LOCKDOWN ? 'Extended inactivity — full freeze' :
      'User activity restored');

    const contacts = user.emergencyContacts || [];
    if (newMode === MODES.GUARDIAN && !notifiedGuardianRef.current) {
      notifiedGuardianRef.current = true;
      if (contacts[0]) sendEmail(contacts[0], 0,
        'WillGuard Alert: Guardian Mode Activated',
        `WillGuard has detected inactivity for ${user.fullName}'s account. System has entered Guardian Mode. All new trades are paused. Portfolio is protected. Time: ${new Date().toLocaleString()}.`);
    }
    if (newMode === MODES.LOCKDOWN && !notifiedLockdownRef.current) {
      notifiedLockdownRef.current = true;
      contacts.forEach((c, i) => sendEmail(c, i,
        '🚨 WillGuard LOCKDOWN: Immediate Attention Required',
        `WillGuard has entered LOCKDOWN mode for ${user.fullName}. Extended inactivity detected. All trading is frozen. A trusted person may need to check on ${user.fullName} immediately. Time: ${new Date().toLocaleString()}.`));
    }
    if (newMode === MODES.COPILOT) {
      notifiedGuardianRef.current = false;
      notifiedLockdownRef.current = false;
    }
    prevModeRef.current = newMode;
  }, [addLedgerEntry, sendEmail, user]);

  // ─── Record Activity ────────────────────────────
  const recordActivity = useCallback(() => {
    lastActivityRef.current = Date.now();
    setSecondsInactive(0);
    if (prevModeRef.current !== MODES.COPILOT) {
      transitionMode(MODES.COPILOT);
    }
  }, [transitionMode]);

  // ─── Heartbeat Timer (1s) ────────────────────────
  useEffect(() => {
    const iv = setInterval(() => {
      const elapsed = Math.floor((Date.now() - lastActivityRef.current) / 1000);
      setSecondsInactive(elapsed);
      if (elapsed >= thresholds.lockdown && prevModeRef.current !== MODES.LOCKDOWN) {
        transitionMode(MODES.LOCKDOWN);
      } else if (elapsed >= thresholds.guardian && prevModeRef.current !== MODES.LOCKDOWN && prevModeRef.current !== MODES.GUARDIAN) {
        transitionMode(MODES.GUARDIAN);
      }
    }, 1000);
    return () => clearInterval(iv);
  }, [thresholds, transitionMode]);

  // ─── Global activity listeners ───────────────────
  useEffect(() => {
    const handler = () => { if (!demoRunning) recordActivity(); };
    window.addEventListener('mousemove', handler);
    window.addEventListener('keydown', handler);
    return () => { window.removeEventListener('mousemove', handler); window.removeEventListener('keydown', handler); };
  }, [demoRunning, recordActivity]);

  // ─── Confidence ──────────────────────────────────
  const confidence = Math.min((secondsInactive / thresholds.guardian) * 100, 100);

  // ─── Trade Submit Handler ────────────────────────
  const handleTrade = useCallback((trade) => {
    recordActivity();
    const result = enforceTradeRules({ ...trade, mode, will });
    setRisk(result.risk);
    setLastTrade({ symbol: trade.symbol, value: trade.quantity * trade.price });
    const action = `${trade.side.toUpperCase()} ${trade.quantity} ${trade.symbol} @$${trade.price}`;
    const orderValue = trade.quantity * trade.price;

    if (result.zone === 'EXECUTE') {
      addLedgerEntry('EXECUTE', action, result.risk.total, mode, result.reason);
      addToast('execute', '✅ Trade Executed', `${action} — $${orderValue.toLocaleString()}`);
      setPortfolio(p => {
        const newCash = trade.side === 'buy' ? p.cash - orderValue : p.cash + orderValue;
        const existing = p.positions.find(pos => pos.symbol === trade.symbol);
        let positions;
        if (existing) {
          positions = p.positions.map(pos => pos.symbol === trade.symbol
            ? { ...pos, qty: trade.side === 'buy' ? pos.qty + trade.quantity : pos.qty - trade.quantity, pnl: pos.pnl + (Math.random() - 0.3) * 50 }
            : pos).filter(pos => pos.qty > 0);
        } else if (trade.side === 'buy') {
          positions = [...p.positions, { symbol: trade.symbol, qty: trade.quantity, pnl: 0 }];
        } else { positions = p.positions; }
        const newTotal = newCash + positions.reduce((s, pos) => s + pos.qty * trade.price, 0);
        return { ...p, cash: newCash, positions, totalValue: newTotal, history: [...p.history.slice(1), newTotal] };
      });
    } else if (result.zone === 'NOTIFY') {
      addToast('notify', '⚠️ Confirmation Required', `${action} — ${result.reason}`, {
        onConfirm: () => {
          addLedgerEntry('EXECUTE', action, result.risk.total, mode, 'Confirmed after NOTIFY');
          addToast('execute', '✅ Confirmed & Executed', `${action}`);
          setPortfolio(p => {
            const newCash = trade.side === 'buy' ? p.cash - orderValue : p.cash + orderValue;
            const existing = p.positions.find(pos => pos.symbol === trade.symbol);
            let positions;
            if (existing) {
              positions = p.positions.map(pos => pos.symbol === trade.symbol ? { ...pos, qty: pos.qty + trade.quantity } : pos);
            } else { positions = [...p.positions, { symbol: trade.symbol, qty: trade.quantity, pnl: 0 }]; }
            const newTotal = newCash + positions.reduce((s, pos) => s + pos.qty * trade.price, 0);
            return { ...p, cash: newCash, positions, totalValue: newTotal, history: [...p.history.slice(1), newTotal] };
          });
        },
        onCancel: () => {
          addLedgerEntry('FREEZE', action, result.risk.total, mode, 'User cancelled after NOTIFY');
          addToast('freeze', '🛑 Trade Cancelled', 'User declined after risk warning');
        },
      });
      addLedgerEntry('NOTIFY', action, result.risk.total, mode, result.reason);
    } else {
      addLedgerEntry('FREEZE', action, result.risk.total, mode, result.reason);
      addToast('freeze', '🛑 Trade Blocked', `${action} — ${result.reason}`);
    }
  }, [mode, will, addLedgerEntry, addToast, recordActivity]);

  // ─── Demo Sequence ──────────────────────────────
  const runDemo = useCallback(() => {
    if (demoRunning) return;
    setDemoRunning(true);
    setDemoMode(true);
    recordActivity();
    setLedger([]);
    setPortfolio({ totalValue: 100000, cash: 100000, positions: [], history: [100000,100200,99800,100400,100100,100600,100300,100800,100500,100000] });
    addToast('info', '▶ Demo Started', '30-second automated demonstration');

    const steps = [
      [0, () => { handleTrade({ symbol: 'AAPL', quantity: 1, side: 'buy', price: 185.50 }); }],
      [5000, () => { handleTrade({ symbol: 'AAPL', quantity: 50, side: 'buy', price: 1000 }); }],
      [10000, () => { handleTrade({ symbol: 'GME', quantity: 5, side: 'buy', price: 25 }); }],
      [15000, () => { lastActivityRef.current = Date.now() - (DEMO_THRESHOLDS.guardian - 2) * 1000; }],
      [25000, () => { handleTrade({ symbol: 'AAPL', quantity: 2, side: 'buy', price: 185.50 }); }],
      [30000, () => { recordActivity(); setDemoRunning(false); addToast('info', '✓ Demo Complete', 'All scenarios demonstrated successfully'); }],
    ];

    steps.forEach(([delay, fn]) => {
      const t = setTimeout(fn, delay);
      if (!demoTimerRef.current) demoTimerRef.current = [];
      demoTimerRef.current.push(t);
    });
  }, [demoRunning, handleTrade, recordActivity, addToast]);

  // ─── Export Ledger ───────────────────────────────
  const exportLedger = () => {
    const blob = new Blob([JSON.stringify(ledger, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `willguard-ledger-${Date.now()}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  // ─── Update Will ─────────────────────────────────
  const handleUpdateWill = (newWill) => {
    setWill(newWill);
    const updated = { ...user, will: newWill };
    setUser(updated);
    localStorage.setItem(`wg_user_${user.email}`, JSON.stringify(updated));
    setShowEditWill(false);
    addToast('info', '📜 Will Updated', 'Financial will changes are now active');
  };

  // ─── Reset ──────────────────────────────────────
  const handleReset = () => {
    if (demoTimerRef.current) { demoTimerRef.current.forEach(clearTimeout); demoTimerRef.current = null; }
    setDemoRunning(false);
    setLedger([]);
    setRisk({ total: 0, sizeShock: 0, suddenness: 0, goalAlignment: 0 });
    setPortfolio({ totalValue: 100000, cash: 100000, positions: [], history: [100000,100200,99800,100400,100100,100600,100300,100800,100500,100000] });
    setLastTrade(null);
    recordActivity();
    addToast('info', '🔄 System Reset', 'All data cleared, system restored to initial state');
  };

  // ─── Logout ─────────────────────────────────────
  const handleLogout = () => {
    localStorage.removeItem('wg_current_user');
    setUser(null);
  };

  // ─── Render ─────────────────────────────────────
  const navItems = [
    { id: 'dashboard', icon: '📊', label: 'Dashboard' },
    { id: 'trade', icon: '⚡', label: 'Trade Evaluator' },
    { id: 'will', icon: '📜', label: 'Financial Will' },
    { id: 'ledger', icon: '📋', label: 'Audit Ledger' },
    { id: 'demo', icon: '🎬', label: 'Demo Mode' },
  ];

  return (
    <div className="dashboard-layout">
      {flash && <div className={`mode-flash ${flash}`}></div>}
      {mode === MODES.LOCKDOWN && <div className="lockdown-border"></div>}
      <ToastContainer toasts={toasts} removeToast={removeToast} />

      {/* ─── Sidebar ─────────────────────────────── */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <div className="sidebar-brand-icon">🛡</div>
            <h2>WillGuard</h2>
          </div>
          <div className={`sidebar-mode-badge ${mode}`}>
            {mode === MODES.COPILOT ? '● CO-PILOT' : mode === MODES.GUARDIAN ? '● GUARDIAN' : '● LOCKDOWN'}
          </div>
        </div>
        <div className="sidebar-user">
          <div className="user-avatar">{initials(user.fullName)}</div>
          <div className="user-info">
            <div className="user-name">{user.fullName}</div>
            <div className="user-role">Account Owner</div>
          </div>
        </div>
        <nav className="sidebar-nav">
          {navItems.map(item => (
            <button key={item.id} className={`nav-item ${activeNav === item.id ? 'active' : ''}`} onClick={() => { setActiveNav(item.id); recordActivity(); }}>
              <span className="nav-icon">{item.icon}</span> {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="btn-logout" onClick={handleLogout}>
            <span className="nav-icon">🚪</span> Logout
          </button>
        </div>
      </aside>

      {/* ─── Main ────────────────────────────────── */}
      <main className="main-content">
        {/* Top Bar */}
        <header className="top-bar">
          <div className="top-bar-left">
            <div className="system-pulse">
              <span className="pulse-dot"></span>
              System Pulse: Stable
            </div>
          </div>
          <div className="top-bar-right">
            <button className="demo-btn guardian" onClick={() => { transitionMode(MODES.GUARDIAN); lastActivityRef.current = Date.now() - thresholds.guardian * 1000; }}>🛡 Guardian</button>
            <button className="demo-btn lockdown" onClick={() => { transitionMode(MODES.LOCKDOWN); lastActivityRef.current = Date.now() - thresholds.lockdown * 1000; }}>🔒 Lockdown</button>
            <button className="demo-btn activity" onClick={recordActivity}>✓ Activity</button>
            <button className="demo-btn reset" onClick={handleReset}>🔄 Reset</button>
            <button className={`demo-btn demo-run`} onClick={runDemo} disabled={demoRunning}>{demoRunning ? '⏳ Running...' : '▶ Demo'}</button>
            <button className="demo-btn settings-btn" onClick={() => setShowSettings(true)}>⚙️</button>
          </div>
        </header>

        {/* Banners */}
        {mode === MODES.GUARDIAN && (
          <div className="guardian-banner">⚠️ GUARDIAN MODE — Inactivity detected. New trades are paused. Activity will restore Co-Pilot mode.</div>
        )}
        {mode === MODES.LOCKDOWN && (
          <div className="lockdown-banner">🔒 LOCKDOWN — Extended inactivity. All trading frozen. Emergency contacts notified.</div>
        )}

        {/* Page Content */}
        <div className="page-content">
          {/* Stats Row */}
          <div className="stats-row">
            <div className="stat-card">
              <div className="stat-card-header">
                <span className="stat-card-title">Portfolio Value</span>
                <span className="stat-card-icon">💼</span>
              </div>
              <div className="stat-card-value">${portfolio.totalValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
              <div className="stat-card-sub"><span style={{ color: 'var(--accent-green)' }}>↑</span> Last updated: just now</div>
            </div>
            <div className="stat-card green">
              <div className="stat-card-header">
                <span className="stat-card-title">Today's P&L</span>
                <span className="stat-card-icon">📈</span>
              </div>
              <div className="stat-card-value" style={{ color: 'var(--accent-green)' }}>+${Math.abs(portfolio.totalValue - 100000).toFixed(2)}</div>
              <div className="stat-card-sub">{((portfolio.totalValue - 100000) / 1000).toFixed(2)}%</div>
            </div>
            <div className={`stat-card ${risk.total < 0.4 ? '' : risk.total < 0.7 ? 'amber' : 'red'}`}>
              <div className="stat-card-header">
                <span className="stat-card-title">Risk Score</span>
                <span className="stat-card-icon">🎯</span>
              </div>
              <div className="stat-card-value text-mono" style={{ color: risk.total < 0.4 ? 'var(--accent-green)' : risk.total < 0.7 ? 'var(--accent-amber)' : 'var(--accent-red)' }}>
                {(risk.total * 100).toFixed(0)}<span style={{ fontSize: '0.9rem' }}>/100</span>
              </div>
              <div className="stat-card-sub">GUARD LEVEL: {risk.total < 0.4 ? 'OPTIMAL' : risk.total < 0.7 ? 'ELEVATED' : 'CRITICAL'}</div>
            </div>
          </div>

          {/* Main Panels */}
          <div className="panels-grid">
            <SystemModePanel mode={mode} secondsInactive={secondsInactive} confidence={confidence} demoRunning={demoRunning} />
            <RiskScorePanel risk={risk} />
          </div>

          <div className="panels-grid">
            <TradeForm onSubmit={handleTrade} disabled={mode === MODES.LOCKDOWN} />
            <PortfolioPanel portfolio={portfolio} />
          </div>

          {/* Decision Ledger */}
          <DecisionLedger entries={ledger} filter={ledgerFilter} setFilter={setLedgerFilter} onExport={exportLedger} />

          {/* Risk Signals */}
          <RiskSignals mode={mode} confidence={confidence} secondsInactive={secondsInactive} lastTrade={lastTrade} will={will} />

          {/* Collapsibles */}
          <EmergencyContacts contacts={user.emergencyContacts} onTestAlert={(c, i) => sendEmail(c, i, 'WillGuard Test Alert', `This is a test alert from WillGuard for ${user.fullName}.`)} lastNotified={lastNotified} />
          <FinancialWill will={will} onEdit={() => setShowEditWill(true)} />
        </div>
      </main>

      {/* Modals */}
      {showEditWill && <EditWillModal will={will} onSave={handleUpdateWill} onClose={() => setShowEditWill(false)} />}
      {showSettings && <SettingsModal emailjsConfig={emailjsConfig} setEmailjsConfig={setEmailjsConfig} onClose={() => setShowSettings(false)} />}
    </div>
  );
}
