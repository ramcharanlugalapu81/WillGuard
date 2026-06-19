import { useState, useEffect, useRef, useCallback } from 'react';
import { AuthPages } from './components/Auth';
import { MODES, DEMO_THRESHOLDS, REAL_THRESHOLDS, enforceTradeRules, getModeColor } from './components/Engine';
import { SystemModePanel, RiskScorePanel, PortfolioPanel } from './components/Panels';
import { TradeForm, DecisionLedger } from './components/TradeAndLedger';
import { RiskSignals, EmergencyContacts, FinancialWill, EditWillModal, SettingsModal } from './components/Sections';
import ToastContainer, { useToasts } from './components/Toasts';
import ClawBot from './components/ClawBot';
import * as api from './api';

// ─── Helpers ─────────────────────────────────────────
function timeStr() { return new Date().toLocaleTimeString(); }
function initials(name) { return (name || 'U').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2); }

export default function App() {
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [backendConnected, setBackendConnected] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem('wg_session');
    if (stored) {
      try {
        const session = JSON.parse(stored);
        if (!session.id) {
          localStorage.removeItem('wg_session');
          setUser(null);
        } else {
          setUser(session);
        }
      } catch {}
    }
    setAuthChecked(true);
    // Check backend health
    api.checkBackendHealth().then(ok => setBackendConnected(ok));
  }, []);

  const handleLogin = useCallback((userData) => {
    setUser(userData);
    localStorage.setItem('wg_session', JSON.stringify(userData));
  }, []);

  if (!authChecked) return null;
  if (!user) return <AuthPages onLogin={handleLogin} backendConnected={backendConnected} />;
  return <Dashboard user={user} setUser={setUser} backendConnected={backendConnected} setBackendConnected={setBackendConnected} />;
}

function Dashboard({ user, setUser, backendConnected, setBackendConnected }) {
  // ─── Core State ──────────────────────────────────
  const [mode, setMode] = useState(MODES.COPILOT);
  const [demoMode, setDemoMode] = useState(false);
  const [demoRunning, setDemoRunning] = useState(false);
  const [secondsInactive, setSecondsInactive] = useState(0);
  const [ledger, setLedger] = useState([]);
  const [ledgerFilter, setLedgerFilter] = useState('ALL');
  const [risk, setRisk] = useState({ total: 0, sizeShock: 0, suddenness: 0, goalAlignment: 0 });
  const [riskMethod, setRiskMethod] = useState('simulated');
  const [flash, setFlash] = useState(null);
  const [will, setWill] = useState(user.will);
  const [showEditWill, setShowEditWill] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showSystemInfo, setShowSystemInfo] = useState(false);
  const [systemInfo, setSystemInfo] = useState(null);
  const [lastTrade, setLastTrade] = useState(null);
  const [portfolio, setPortfolio] = useState({
    totalValue: 100000, cash: 100000, positions: [],
    history: [100000, 100200, 99800, 100400, 100100, 100600, 100300, 100800, 100500, 100000],
  });
  const [activeNav, setActiveNav] = useState('dashboard');
  const [notificationStatus, setNotificationStatus] = useState(null);
  const [notificationHistory, setNotificationHistory] = useState([]);

  const userId = user.user?.id || user.id;

  const { toasts, addToast, removeToast } = useToasts();

  const lastActivityRef = useRef(Date.now());
  const demoTimerRef = useRef(null);
  const prevModeRef = useRef(mode);
  const notifiedGuardianRef = useRef(false);
  const notifiedLockdownRef = useRef(false);

  const thresholds = demoMode ? DEMO_THRESHOLDS : {
    guardian: parseInt(will?.guardianTimer) || REAL_THRESHOLDS.guardian,
    lockdown: parseInt(will?.lockdownTimer) || REAL_THRESHOLDS.lockdown
  };

  // ─── Load data from backend on mount ──────────────
  useEffect(() => {
    if (!userId) return;

    // Load portfolio from DB
    api.getPortfolio(userId).then(({ ok, data }) => {
      if (ok && data) {
        setPortfolio(prev => ({
          ...prev,
          totalValue: data.totalValue || prev.totalValue,
          cash: data.cash || prev.cash,
          positions: (data.positions || []).map(p => ({
            symbol: p.symbol,
            qty: p.quantity,
            pnl: p.pnl || 0,
          })),
        }));
      }
    });

    // Load ledger from DB
    api.getLedger(userId, 50).then(({ ok, data }) => {
      if (ok && data?.entries) {
        setLedger(data.entries.map(e => ({
          zone: e.zone,
          action: e.action,
          risk: e.risk_score,
          mode: e.mode,
          reason: e.reason,
          time: e.created_at ? new Date(e.created_at).toLocaleTimeString() : '—',
        })));
      }
    });

    // Load notification status
    api.getNotificationStatus().then(({ ok, data }) => {
      if (ok) setNotificationStatus(data);
    });

    // Load notification history
    api.getNotificationHistory(userId).then(({ ok, data }) => {
      if (ok) setNotificationHistory(Array.isArray(data) ? data : []);
    });

    // Load will from DB
    api.getWill(userId).then(({ ok, data }) => {
      if (ok && data) {
        setWill(prev => ({
          ...prev,
          riskTolerance: data.riskTolerance || 'Moderate',
          dailyTradeLimit: data.dailyTradeLimit || 50000,
          perOrderLimit: data.perOrderLimit || 10000,
          approvedTickers: data.approvedTickers || [],
        }));
      }
    });
  }, [userId]);

  // ─── WebSocket Connection ──────────────────────────
  useEffect(() => {
    const ws = api.connectWebSocket(
      (msg) => {
        // Handle real-time events from backend
        if (msg.type === 'mode_change') {
          const newMode = msg.data?.mode;
          if (newMode && newMode !== prevModeRef.current) {
            setFlash(newMode);
            setTimeout(() => setFlash(null), 400);
            setMode(newMode);
            prevModeRef.current = newMode;
            addToast('info', 'Mode Changed',
              `System transitioned to ${newMode.toUpperCase()}${msg.data?.restored_by ? ` by ${msg.data.restored_by}` : ''}`);
          }
        } else if (msg.type === 'trade_result') {
          // Trade processed by backend
        } else if (msg.type === 'system_reset') {
          setMode(MODES.COPILOT);
          prevModeRef.current = MODES.COPILOT;
        }
      },
      () => {
        setBackendConnected(true);
        api.getSystemInfo().then(res => { if (res.ok) setSystemInfo(res.data); });
      },
      () => setBackendConnected(false),
    );

    return () => api.disconnectWebSocket();
  }, [addToast, setBackendConnected]);

  // ─── Add Ledger Entry (local + DB) ────────────────
  const addLedgerEntry = useCallback((zone, action, riskVal, currentMode, reason) => {
    const entry = { zone, action, risk: riskVal, mode: currentMode, reason, time: timeStr() };
    setLedger(prev => [entry, ...prev]);
    if (userId) {
      api.getLedger(userId, 1); // Sync with DB (entry added server-side)
    }
  }, [userId]);

  // ─── Mode Transition ────────────────────────────────
  const transitionMode = useCallback((newMode) => {
    if (newMode === prevModeRef.current) return;
    setFlash(newMode);
    setTimeout(() => setFlash(null), 400);
    setMode(newMode);
    addLedgerEntry('MODE_CHANGE', `→ ${newMode.toUpperCase()}`, null, newMode,
      newMode === MODES.GUARDIAN ? 'Inactivity detected — trades paused' :
      newMode === MODES.LOCKDOWN ? 'Extended inactivity — full freeze' :
      'User activity restored');

    // Send notifications via backend
    if (userId) {
      if (newMode === MODES.GUARDIAN && !notifiedGuardianRef.current) {
        notifiedGuardianRef.current = true;
        api.sendGuardianNotifications(userId).then(({ ok, data }) => {
          if (ok) addToast('info', 'Email Sent', 'Guardian alert sent to emergency contacts');
        });
      }
      if (newMode === MODES.LOCKDOWN && !notifiedLockdownRef.current) {
        notifiedLockdownRef.current = true;
        api.sendLockdownNotifications(userId).then(({ ok, data }) => {
          if (ok) addToast('info', 'Email Sent', 'Lockdown alert sent — contacts can click Magic Link to restore');
        });
      }
    }

    if (newMode === MODES.COPILOT) {
      notifiedGuardianRef.current = false;
      notifiedLockdownRef.current = false;
    }
    prevModeRef.current = newMode;
  }, [addLedgerEntry, addToast, userId]);

  // ─── Record Activity ────────────────────────────────
  const recordActivity = useCallback(() => {
    lastActivityRef.current = Date.now();
    setSecondsInactive(0);
    if (prevModeRef.current !== MODES.COPILOT) {
      transitionMode(MODES.COPILOT);
    }
  }, [transitionMode]);

  // ─── Heartbeat Timer (1s) ────────────────────────────
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

  // ─── Global activity listeners ───────────────────────
  useEffect(() => {
    const handler = () => { if (!demoRunning) recordActivity(); };
    window.addEventListener('mousemove', handler);
    window.addEventListener('keydown', handler);
    return () => { window.removeEventListener('mousemove', handler); window.removeEventListener('keydown', handler); };
  }, [demoRunning, recordActivity]);

  const confidence = Math.min((secondsInactive / thresholds.guardian) * 100, 100);

  // ─── Trade Submit Handler ────────────────────────────
  const handleTrade = useCallback(async (trade) => {
    recordActivity();

    // Try backend first for AI risk scoring
    if (backendConnected && userId) {
      const { ok, data } = await api.submitTrade({
        symbol: trade.symbol,
        action: trade.side,
        quantity: trade.quantity,
        price: trade.price,
      }, userId);

      if (ok && data) {
        // Use backend AI risk scores
        const riskData = data.risk_score || {};
        setRisk({
          total: riskData.total || 0,
          sizeShock: riskData.size_shock || riskData.sizeShock || 0,
          suddenness: riskData.suddenness || 0,
          goalAlignment: riskData.goal_alignment || riskData.goalAlignment || 0,
        });
        setRiskMethod(riskData.method || 'heuristic');
        setLastTrade({ symbol: trade.symbol, value: trade.quantity * trade.price });

        const zone = data.decision?.zone || 'FREEZE';
        const reason = data.decision?.reason || '';
        const action = `${trade.side.toUpperCase()} ${trade.quantity} ${trade.symbol} @$${trade.price}`;
        const orderValue = trade.quantity * trade.price;

        // Update portfolio from backend response
        if (data.portfolio) {
          setPortfolio(prev => ({
            ...prev,
            totalValue: data.portfolio.totalValue || prev.totalValue,
            cash: data.portfolio.cash || prev.cash,
            positions: (data.portfolio.positions || []).map(p => ({
              symbol: p.symbol,
              qty: p.quantity,
              pnl: p.pnl || 0,
            })),
            history: [...prev.history.slice(1), data.portfolio.totalValue || prev.totalValue],
          }));
        }

        if (zone === 'EXECUTE') {
          addLedgerEntry('EXECUTE', action, riskData.total, mode, reason);
          addToast('execute', 'Trade Executed', `${action} — $${orderValue.toLocaleString()}`);
        } else if (zone === 'NOTIFY') {
          addToast('notify', 'Confirmation Required', `${action} — ${reason}`, {
            onConfirm: () => {
              addLedgerEntry('EXECUTE', action, riskData.total, mode, 'Confirmed after NOTIFY');
              addToast('execute', 'Confirmed & Executed', `${action}`);
            },
            onCancel: () => {
              addLedgerEntry('FREEZE', action, riskData.total, mode, 'User cancelled after NOTIFY');
              addToast('freeze', 'Trade Cancelled', 'User declined after risk warning');
            },
          });
          addLedgerEntry('NOTIFY', action, riskData.total, mode, reason);
        } else {
          addLedgerEntry('FREEZE', action, riskData.total, mode, reason);
          addToast('freeze', 'Trade Blocked', `${action} — ${reason}`);
        }
        return;
      }
    }

    // Fallback: client-side enforcement
    const result = enforceTradeRules({ ...trade, mode, will });
    setRisk(result.risk);
    setRiskMethod('simulated');
    setLastTrade({ symbol: trade.symbol, value: trade.quantity * trade.price });
    const action = `${trade.side.toUpperCase()} ${trade.quantity} ${trade.symbol} @$${trade.price}`;
    const orderValue = trade.quantity * trade.price;

    if (result.zone === 'EXECUTE') {
      addLedgerEntry('EXECUTE', action, result.risk.total, mode, result.reason);
      addToast('execute', 'Trade Executed', `${action} — $${orderValue.toLocaleString()}`);
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
      addToast('notify', 'Confirmation Required', `${action} — ${result.reason}`, {
        onConfirm: () => {
          addLedgerEntry('EXECUTE', action, result.risk.total, mode, 'Confirmed after NOTIFY');
          addToast('execute', 'Confirmed & Executed', `${action}`);
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
          addToast('freeze', 'Trade Cancelled', 'User declined after risk warning');
        },
      });
      addLedgerEntry('NOTIFY', action, result.risk.total, mode, result.reason);
    } else {
      addLedgerEntry('FREEZE', action, result.risk.total, mode, result.reason);
      addToast('freeze', 'Trade Blocked', `${action} — ${result.reason}`);
    }
  }, [mode, will, addLedgerEntry, addToast, recordActivity, backendConnected, userId]);

  // ─── Demo Sequence ──────────────────────────────────
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
      [30000, () => { recordActivity(); setDemoRunning(false); addToast('info', 'Demo Complete', 'All scenarios demonstrated successfully'); }],
    ];

    steps.forEach(([delay, fn]) => {
      const t = setTimeout(fn, delay);
      if (!demoTimerRef.current) demoTimerRef.current = [];
      demoTimerRef.current.push(t);
    });
  }, [demoRunning, handleTrade, recordActivity, addToast]);

  // ─── Export Ledger ───────────────────────────────────
  const exportLedger = () => {
    const blob = new Blob([JSON.stringify(ledger, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `willguard-ledger-${Date.now()}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  // ─── Update Will ─────────────────────────────────────
  const handleUpdateWill = async (newWill) => {
    setWill(newWill);
    setShowEditWill(false);
    
    // Save to localStorage so timers persist on refresh if backend doesn't store them
    const stored = localStorage.getItem('wg_session');
    if (stored) {
      try {
        const session = JSON.parse(stored);
        session.will = newWill;
        localStorage.setItem('wg_session', JSON.stringify(session));
      } catch {}
    }

    // Save to backend DB
    if (userId && backendConnected) {
      await api.updateWill(userId, newWill);
    }

    addToast('info', 'Will Updated', 'Financial will changes saved to database & locally');
  };

  // ─── Reset ──────────────────────────────────────────
  const handleReset = async () => {
    if (demoTimerRef.current) { demoTimerRef.current.forEach(clearTimeout); demoTimerRef.current = null; }
    setDemoRunning(false);
    setLedger([]);
    setRisk({ total: 0, sizeShock: 0, suddenness: 0, goalAlignment: 0 });
    setPortfolio({ totalValue: 100000, cash: 100000, positions: [], history: [100000,100200,99800,100400,100100,100600,100300,100800,100500,100000] });
    setLastTrade(null);
    recordActivity();

    if (userId && backendConnected) {
      await api.resetSystem(userId);
    }

    addToast('info', 'System Reset', 'All data cleared, system restored to initial state');
  };

  // ─── Test SMS ────────────────────────────────────────
  const handleTestSMS = async (contact, contactIndex) => {
    if (!userId || !backendConnected) {
      addToast('info', 'Email Skipped', `Backend offline — would notify ${contact.name}`);
      return;
    }
    const contactId = contact.id || contactIndex + 1;
    const { ok, data } = await api.sendTestNotification(userId, contactId);
    if (ok) {
      addToast('info', 'Test Email Sent', `Alert sent to ${contact.name}`);
      // Refresh notification history
      const hist = await api.getNotificationHistory(userId);
      if (hist.ok) setNotificationHistory(Array.isArray(hist.data) ? hist.data : []);
    } else {
      addToast('freeze', 'Email Failed', `Could not send to ${contact.name}`);
    }
  };

  // ─── Logout ─────────────────────────────────────────
  const handleLogout = () => {
    localStorage.removeItem('wg_session');
    localStorage.removeItem('wg_current_user');
    setUser(null);
  };

  // ─── Render ─────────────────────────────────────────
  const navItems = [
    { id: 'dashboard', icon: '', label: 'Dashboard' },
    { id: 'trade', icon: '', label: 'Trade Evaluator' },
    { id: 'will', icon: '', label: 'Financial Will' },
    { id: 'ledger', icon: '', label: 'Audit Ledger' },
    { id: 'demo', icon: '🎬', label: 'Demo Mode' },
  ];

  const displayName = user.user?.full_name || user.full_name || user.fullName || 'User';
  const emergencyContacts = user.emergencyContacts || [];

  return (
    <div className="dashboard-layout">
      {flash && <div className={`mode-flash ${flash}`}></div>}
      {mode === MODES.LOCKDOWN && <div className="lockdown-border"></div>}
      <ToastContainer toasts={toasts} removeToast={removeToast} />

      {/* ─── Sidebar ─────────────────────────────── */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <div className="sidebar-brand-icon"></div>
            <h2>WillGuard</h2>
          </div>
          <div className={`sidebar-mode-badge ${mode}`}>
            {mode === MODES.COPILOT ? 'CO-PILOT' : mode === MODES.GUARDIAN ? 'GUARDIAN' : 'LOCKDOWN'}
          </div>
        </div>
        <div className="sidebar-user">
          <div className="user-avatar">{initials(displayName)}</div>
          <div className="user-info">
            <div className="user-name">{displayName}</div>
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
          <div className={`backend-status ${backendConnected ? 'connected' : 'offline'}`}>
            <span className="status-dot"></span>
            {backendConnected ? 'Backend Connected' : 'Backend Offline'}
          </div>
          {notificationStatus && (
            <div className={`backend-status ${notificationStatus.configured ? 'connected' : 'offline'}`}>
              <span className="status-dot"></span>
              Email: {notificationStatus.configured ? 'Live' : 'Simulation'}
            </div>
          )}
          <button className="clawbot-sidebar-btn" style={{ background: 'rgba(255,255,255,0.05)', marginTop: '4px' }} onClick={() => setShowSystemInfo(true)}>
            <span className="clawbot-sidebar-icon"></span>
            <span>System Diagnostics</span>
          </button>
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" className="clawbot-sidebar-btn" style={{ textDecoration: 'none', background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', marginTop: '4px' }}>
            <span className="clawbot-sidebar-icon">📖</span>
            <span>Python API Docs</span>
          </a>
          <button className="btn-logout" onClick={handleLogout}>
            <span className="nav-icon">🚪</span> Logout
          </button>
        </div>
      </aside>

      {/* ─── Main ────────────────────────────────── */}
      <main className="main-content">
        <header className="top-bar">
          <div className="top-bar-left">
            <div className="system-pulse">
              <span className="pulse-dot"></span>
              System Pulse: Stable
            </div>
          </div>
          <div className="top-bar-right">
            <button className="demo-btn guardian" onClick={() => { transitionMode(MODES.GUARDIAN); lastActivityRef.current = Date.now() - thresholds.guardian * 1000; }}>Guardian</button>
            <button className="demo-btn lockdown" onClick={() => { transitionMode(MODES.LOCKDOWN); lastActivityRef.current = Date.now() - thresholds.lockdown * 1000; }}>Lockdown</button>
            <button className="demo-btn activity" onClick={recordActivity}>Activity</button>
            <button className="demo-btn reset" onClick={handleReset}>Reset</button>
            <button className={`demo-btn demo-run`} onClick={runDemo} disabled={demoRunning}>{demoRunning ? 'Running...' : '▶ Demo'}</button>
            <button className="demo-btn settings-btn" onClick={() => setShowSettings(true)}></button>
          </div>
        </header>

        {mode === MODES.GUARDIAN && (
          <div className="guardian-banner">GUARDIAN MODE — Inactivity detected. New trades are paused. Activity will restore Co-Pilot mode.</div>
        )}
        {mode === MODES.LOCKDOWN && (
          <div className="lockdown-banner">LOCKDOWN — Extended inactivity. All trading frozen. Emergency contacts notified via Email. They can click the Magic Link to restore.</div>
        )}

        <div className="page-content" key={activeNav}>
          <div className="tab-pane-animate">
          {activeNav === 'dashboard' && (
            <>
              <div className="stats-row">
                <div className="stat-card">
                  <div className="stat-card-header">
                    <span className="stat-card-title">Portfolio Value</span>
                    <span className="stat-card-icon"></span>
                  </div>
                  <div className="stat-card-value">${portfolio.totalValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
                  <div className="stat-card-sub"><span style={{ color: portfolio.totalValue >= 100000 ? 'var(--accent-green)' : 'var(--accent-red)' }}>{portfolio.totalValue >= 100000 ? '↑' : '↓'}</span> Cash: ${portfolio.cash.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
                </div>
                <div className={`stat-card ${portfolio.totalValue >= 100000 ? 'green' : 'red'}`}>
                  <div className="stat-card-header">
                    <span className="stat-card-title">Today's P&L</span>
                    <span className="stat-card-icon"></span>
                  </div>
                  <div className="stat-card-value" style={{ color: portfolio.totalValue >= 100000 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                    {portfolio.totalValue >= 100000 ? '+' : '-'}${Math.abs(portfolio.totalValue - 100000).toFixed(2)}
                  </div>
                  <div className="stat-card-sub">{((portfolio.totalValue - 100000) / 1000).toFixed(2)}%</div>
                </div>
                <div className={`stat-card ${risk.total < 0.4 ? '' : risk.total < 0.7 ? 'amber' : 'red'}`}>
                  <div className="stat-card-header">
                    <span className="stat-card-title">Risk Score</span>
                    <span className="stat-card-icon"></span>
                  </div>
                  <div className="stat-card-value text-mono" style={{ color: risk.total < 0.4 ? 'var(--accent-green)' : risk.total < 0.7 ? 'var(--accent-amber)' : 'var(--accent-red)' }}>
                    {(risk.total * 100).toFixed(0)}<span style={{ fontSize: '0.9rem' }}>/100</span>
                  </div>
                  <div className="stat-card-sub">
                    {riskMethod === 'gemini' ? 'AI-Scored' : riskMethod === 'heuristic' ? '📐 Heuristic' : 'Simulated'}
                  </div>
                </div>
              </div>

              <div className="panels-grid">
                <SystemModePanel mode={mode} secondsInactive={secondsInactive} confidence={confidence} demoRunning={demoRunning} />
                <RiskScorePanel risk={risk} method={riskMethod} />
              </div>
            </>
          )}

          {activeNav === 'trade' && (
            <>
              <div className="panels-grid">
                <TradeForm onSubmit={handleTrade} disabled={mode === MODES.LOCKDOWN} />
                <PortfolioPanel portfolio={portfolio} />
              </div>
              <RiskSignals mode={mode} confidence={confidence} secondsInactive={secondsInactive} lastTrade={lastTrade} will={will} onOpenClawBot={() => setActiveNav('clawbot')} />
            </>
          )}

          {activeNav === 'clawbot' && (
            <ClawBot
              onTrade={handleTrade}
              mode={mode}
              portfolio={portfolio}
              risk={risk}
              userId={userId}
              backendConnected={backendConnected}
              onReset={handleReset}
              onRecordActivity={recordActivity}
            />
          )}

          {activeNav === 'ledger' && (
            <DecisionLedger entries={ledger} filter={ledgerFilter} setFilter={setLedgerFilter} onExport={exportLedger} />
          )}

          {activeNav === 'will' && (
            <>
              <FinancialWill will={will} onEdit={() => setShowEditWill(true)} />
              <EmergencyContacts
                contacts={emergencyContacts}
                onTestAlert={handleTestSMS}
                notificationHistory={notificationHistory}
                notificationStatus={notificationStatus}
              />
            </>
          )}

          {activeNav === 'demo' && (
            <div className="panel">
              <div className="panel-header"><span className="panel-title">Demo Instructions</span></div>
              <div style={{ lineHeight: '1.6', color: 'var(--text-secondary)' }}>
                <p>Welcome to the WillGuard interactive demo!</p>
                <div style={{ marginTop: '12px' }}>
                  <p>1. <strong>Co-Pilot Mode:</strong> Try submitting standard trades in the Trade Evaluator tab.</p>
                  <p>2. <strong>Guardian Mode:</strong> Stop interacting with the page. After {thresholds.guardian} seconds, Guardian mode activates, sends an Email, and stops new trades.</p>
                  <p>3. <strong>Lockdown Mode:</strong> After {thresholds.lockdown} seconds of inactivity, Lockdown mode triggers. Emergency contacts receive an Email with a <strong>Magic Link</strong> to restore.</p>
                  <p>4. <strong>Automated Demo:</strong> Click the <strong>▶ Demo</strong> button to watch a pre-scripted sequence.</p>
                  <p>5. <strong>Email Magic Link:</strong> Emergency contacts can click the Magic Link in their email to securely restore the system to Co-Pilot mode.</p>
                </div>
              </div>
            </div>
          )}
          </div>
        </div>
      </main>

      {showEditWill && <EditWillModal will={will} onSave={handleUpdateWill} onClose={() => setShowEditWill(false)} />}
      {showSettings && <SettingsModal notificationStatus={notificationStatus} notificationHistory={notificationHistory} onClose={() => setShowSettings(false)} />}
      
      {showSystemInfo && systemInfo && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '400px' }}>
            <div className="modal-header">
              <h2 className="modal-title">🖥 Backend Diagnostics</h2>
              <button className="modal-close" onClick={() => setShowSystemInfo(false)}>×</button>
            </div>
            <div className="system-info-grid">
              <div className="sys-info-item"><strong>Status:</strong> <span style={{ color: 'var(--accent-green)' }}>ONLINE</span></div>
              <div className="sys-info-item"><strong>Engine:</strong> {systemInfo.engine}</div>
              <div className="sys-info-item"><strong>Python:</strong> {systemInfo.version}</div>
              <div className="sys-info-item"><strong>OS:</strong> {systemInfo.os} ({systemInfo.arch})</div>
              <div className="sys-info-item"><strong>Process ID:</strong> {systemInfo.pid}</div>
              <div className="sys-info-item"><strong>Database:</strong> SQLite (Persistent)</div>
              <div className="sys-info-item"><strong>Alpaca:</strong> {systemInfo.alpaca}</div>
            </div>
            <div style={{ marginTop: '20px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              This data is fetched in real-time from the Python FastAPI server.
            </div>
          </div>
        </div>
      )}

      {/* Floating ClawBot Button */}
      {activeNav !== 'clawbot' && (
        <button className="clawbot-fab" onClick={() => { setActiveNav('clawbot'); recordActivity(); }} title="Open ClawBot Terminal">
          <span className="clawbot-fab-icon"></span>
        </button>
      )}
    </div>
  );
}
