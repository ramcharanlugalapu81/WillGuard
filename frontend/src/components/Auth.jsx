import { useState } from 'react';
import * as api from '../api';

const DEFAULT_WILL = {
  riskTolerance: 'Moderate',
  dailyTradeLimit: 50000,
  perOrderLimit: 10000,
  approvedTickers: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'SPY', 'QQQ', 'NVDA'],
};

export function AuthPages({ onLogin, backendConnected }) {
  const [isLogin, setIsLogin] = useState(true);
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    fullName: '', email: '', password: '', phone: '',
    ec1Name: '', ec1Email: '', ec1Phone: '',
    ec2Name: '', ec2Email: '', ec2Phone: '',
    riskTolerance: 'Moderate', dailyLimit: '50000', perOrderLimit: '10000',
    approvedTickers: 'AAPL,MSFT,GOOGL,AMZN,TSLA,SPY,QQQ,NVDA',
    guardianTimer: '10', lockdownTimer: '15',
  });
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const set = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }));

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Try backend first
    const { ok, data, error: apiError } = await api.login(form.email, form.password);
    if (ok && data) {
      onLogin(data);
      setLoading(false);
      return;
    }

    // Fallback to localStorage
    const stored = localStorage.getItem(`wg_user_${form.email}`);
    if (!stored) {
      setError(apiError || 'Account not found. Please register first.');
      setLoading(false);
      return;
    }
    const user = JSON.parse(stored);
    if (user.password !== form.password) {
      setError('Incorrect password.');
      setLoading(false);
      return;
    }
    localStorage.setItem('wg_current_user', form.email);
    onLogin(user);
    setLoading(false);
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    if (step === 1) {
      if (!form.fullName || !form.email || !form.password) { setError('Please fill all required fields.'); return; }
      setStep(2); return;
    }
    if (step === 2) {
      if (!form.ec1Name || !form.ec1Email || !form.ec1Phone) { setError('Emergency Contact 1 is required.'); return; }
      setStep(3); return;
    }

    setLoading(true);
    const tickers = form.approvedTickers.split(',').map(t => t.trim().toUpperCase()).filter(Boolean);
    const emergencyContacts = [
      { name: form.ec1Name, email: form.ec1Email, phone: form.ec1Phone },
      ...(form.ec2Name ? [{ name: form.ec2Name, email: form.ec2Email, phone: form.ec2Phone }] : []),
    ];
    const willData = {
      riskTolerance: form.riskTolerance,
      dailyTradeLimit: parseFloat(form.dailyLimit) || 50000,
      perOrderLimit: parseFloat(form.perOrderLimit) || 10000,
      approvedTickers: tickers.length ? tickers : DEFAULT_WILL.approvedTickers,
    };

    // Register via backend
    const { ok, data, error: apiError } = await api.register({
      email: form.email,
      full_name: form.fullName,
      password: form.password,
      phone: form.phone,
      emergency_contacts: emergencyContacts,
      will: willData,
    });

    if (ok && data) {
      // Also save to localStorage as backup
      const localUser = {
        ...data,
        fullName: form.fullName,
        email: form.email,
        password: form.password,
        phone: form.phone,
        emergencyContacts,
        will: willData,
      };
      localStorage.setItem(`wg_user_${form.email}`, JSON.stringify(localUser));
      localStorage.setItem('wg_current_user', form.email);
      onLogin(data);
    } else {
      // Fallback: save locally only
      const user = {
        fullName: form.fullName, email: form.email, password: form.password, phone: form.phone,
        emergencyContacts,
        will: willData,
      };
      localStorage.setItem(`wg_user_${form.email}`, JSON.stringify(user));
      localStorage.setItem('wg_current_user', form.email);
      if (apiError && apiError !== 'Backend offline') {
        setError(apiError);
        setLoading(false);
        return;
      }
      onLogin(user);
    }
    setLoading(false);
  };

  const renderHero = () => (
    <div className="auth-split-hero">
      <div className="auth-logo" style={{ marginBottom: 30 }}>
        <div className="auth-logo-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        </div>
        <h1 className="stylish-logo">Will<span>Guard</span></h1>
      </div>
      <h1 className="hero-title">
        {isLogin ? "Welcome Back to" : "Future of"} <br/>
        <span className="stylish-logo">Will<span>Guard</span></span>
      </h1>
      <p className="hero-subtitle">
        {isLogin 
          ? "Sign in to monitor your active trades and manage your automated financial safety system." 
          : "Set up your AI financial safety system. Secure your assets, automate protection, and trade with absolute peace of mind."}
      </p>
      
      <div className="hero-features" style={{ display: 'flex', flexDirection: 'column', gap: '18px', marginTop: 30 }}>
         <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'white', fontWeight: 600 }}>ArmorClaw Protocol</div>
         <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'white', fontWeight: 600 }}>Inactivity Detection</div>
         <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'white', fontWeight: 600 }}>Magic Link Restore</div>
      </div>
    </div>
  );

  if (isLogin) {
    return (
      <div className="auth-container">
        <div className="auth-bg-animation">
          <div className="auth-bg-shape cyan"></div>
          <div className="auth-bg-shape green"></div>
          <div className="auth-bg-shape amber"></div>
        </div>
        <div className="auth-grid-overlay"></div>
        
        <div className="auth-split-wrapper">
          {renderHero()}
          <div className="auth-split-form">
            <div className="auth-card">
              <h2 className="auth-title">Welcome Back</h2>

          <p className="auth-subtitle">Sign in to your financial safety system</p>
          <div className={`backend-badge ${backendConnected ? 'connected' : 'offline'}`}>
            <span className="status-dot"></span>
            {backendConnected ? 'Backend Connected' : 'Backend Offline (Local Mode)'}
          </div>
          {error && <div style={{ color: 'var(--accent-red)', fontSize: '0.8rem', marginBottom: 12, padding: '8px 12px', background: 'rgba(255,51,102,0.08)', borderRadius: 6 }}>{error}</div>}
          <form onSubmit={handleLogin}>
            <div className="form-group"><label>Email</label><input type="email" value={form.email} onChange={set('email')} placeholder="you@example.com" required /></div>
            <div className="form-group">
              <label>Password</label>
              <div className="password-input-wrap">
                <input type={showPassword ? "text" : "password"} value={form.password} onChange={set('password')} placeholder="••••••••" required />
                <button type="button" className="eye-btn" onClick={() => setShowPassword(!showPassword)}>
                  {showPassword ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                  )}
                </button>
              </div>
            </div>
            <button className="btn-primary auth-submit-btn" type="submit" disabled={loading}>{loading ? 'Signing In...' : 'Sign In'}</button>
          </form>
          <div className="auth-switch">Don't have an account? <button type="button" onClick={() => { setIsLogin(false); setError(''); }}>Register</button></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
        <div className="auth-bg-animation">
          <div className="auth-bg-shape cyan"></div>
          <div className="auth-bg-shape green"></div>
          <div className="auth-bg-shape amber"></div>
        </div>
        <div className="auth-grid-overlay"></div>
        
      <div className="auth-split-wrapper">
        {renderHero()}
        <div className="auth-split-form">
          <div className="auth-card wide">
            <h2 className="auth-title">Create Your Account</h2>
        <p className="auth-subtitle">Set up your AI financial safety system</p>
        <div className={`backend-badge ${backendConnected ? 'connected' : 'offline'}`}>
          <span className="status-dot"></span>
          {backendConnected ? 'Backend Connected — Data saved to database' : 'Backend Offline — Data saved locally'}
        </div>
        <div className="steps-indicator">
          <div className={`step-dot ${step > 1 ? 'completed' : step === 1 ? 'active' : ''}`}></div>
          <div className={`step-dot ${step > 2 ? 'completed' : step === 2 ? 'active' : ''}`}></div>
          <div className={`step-dot ${step === 3 ? 'active' : ''}`}></div>
        </div>
        {error && <div style={{ color: 'var(--accent-red)', fontSize: '0.8rem', marginBottom: 12, padding: '8px 12px', background: 'rgba(255,51,102,0.08)', borderRadius: 6 }}>{error}</div>}
        <form onSubmit={handleRegister}>
          {step === 1 && (<>
            <div className="auth-section-title">Personal Details</div>
            <div className="form-row">
              <div className="form-group"><label>Full Name *</label><input value={form.fullName} onChange={set('fullName')} placeholder="John Doe" required /></div>
              <div className="form-group"><label>Phone Number</label><input value={form.phone} onChange={set('phone')} placeholder="+91 9876543210" /></div>
            </div>
            <div className="form-group"><label>Email *</label><input type="email" value={form.email} onChange={set('email')} placeholder="you@example.com" required /></div>
            <div className="form-group">
              <label>Password *</label>
              <div className="password-input-wrap">
                <input type={showPassword ? "text" : "password"} value={form.password} onChange={set('password')} placeholder="Min 6 characters" required />
                <button type="button" className="eye-btn" onClick={() => setShowPassword(!showPassword)}>
                  {showPassword ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                  )}
                </button>
              </div>
            </div>
          </>)}
          {step === 2 && (<>
            <div className="auth-section-title">Emergency Contact 1 (Required)</div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 12 }}>
              This contact will receive SMS alerts via Twilio when your account enters Guardian or Lockdown mode. They can reply <strong>SAFE</strong> to restore your account.
            </p>
            <div className="form-row">
              <div className="form-group"><label>Name *</label><input value={form.ec1Name} onChange={set('ec1Name')} placeholder="Contact name" required /></div>
              <div className="form-group"><label>Phone * (with country code)</label><input value={form.ec1Phone} onChange={set('ec1Phone')} placeholder="+91 9876543210" required /></div>
            </div>
            <div className="form-group"><label>Email *</label><input type="email" value={form.ec1Email} onChange={set('ec1Email')} placeholder="contact@email.com" required /></div>
            <div className="auth-section-title">Emergency Contact 2 (Optional)</div>
            <div className="form-row">
              <div className="form-group"><label>Name</label><input value={form.ec2Name} onChange={set('ec2Name')} placeholder="Contact name" /></div>
              <div className="form-group"><label>Phone</label><input value={form.ec2Phone} onChange={set('ec2Phone')} placeholder="+91 ..." /></div>
            </div>
            <div className="form-group"><label>Email</label><input type="email" value={form.ec2Email} onChange={set('ec2Email')} placeholder="contact@email.com" /></div>
          </>)}
          {step === 3 && (<>
            <div className="auth-section-title">Financial Will Setup</div>
            <div className="form-row">
              <div className="form-group">
                <label>Risk Tolerance</label>
                <select value={form.riskTolerance} onChange={set('riskTolerance')}>
                  <option>Conservative</option><option>Moderate</option><option>Aggressive</option>
                </select>
              </div>
              <div className="form-group"><label>Daily Trade Limit ($)</label><input type="number" value={form.dailyLimit} onChange={set('dailyLimit')} /></div>
            </div>
            <div className="form-group"><label>Per-Order Limit ($)</label><input type="number" value={form.perOrderLimit} onChange={set('perOrderLimit')} /></div>
            <div className="form-group"><label>Approved Tickers (comma separated)</label><input value={form.approvedTickers} onChange={set('approvedTickers')} placeholder="AAPL,MSFT,GOOGL" /></div>
            
            <div className="auth-section-title">Inactivity Timeouts (Seconds)</div>
            <div className="form-row">
              <div className="form-group"><label>Guardian Delay</label><input type="number" value={form.guardianTimer} onChange={set('guardianTimer')} placeholder="10" /></div>
              <div className="form-group"><label>Lockdown Delay</label><input type="number" value={form.lockdownTimer} onChange={set('lockdownTimer')} placeholder="15" /></div>
            </div>
          </>)}
          <button className="btn-primary auth-submit-btn" type="submit" disabled={loading}>
            {loading ? 'Processing...' : step < 3 ? 'Continue →' : 'Create Account & Launch'}
          </button>
        </form>
        {step > 1 && <button type="button" style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', marginTop: 12, fontSize: '0.85rem' }} onClick={() => { setStep(s => s - 1); setError(''); }}>← Back</button>}
        <div className="auth-switch">Already have an account? <button type="button" onClick={() => { setIsLogin(true); setStep(1); setError(''); }}>Sign In</button></div>
          </div>
        </div>
      </div>
    </div>
  );
}
