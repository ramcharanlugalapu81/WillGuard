import { useState } from 'react';

const DEFAULT_WILL = {
  riskTolerance: 'Moderate',
  dailyTradeLimit: 50000,
  perOrderLimit: 10000,
  approvedTickers: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'SPY', 'QQQ', 'NVDA'],
};

export function AuthPages({ onLogin }) {
  const [isLogin, setIsLogin] = useState(true);
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    fullName: '', email: '', password: '', phone: '',
    ec1Name: '', ec1Email: '', ec1Phone: '',
    ec2Name: '', ec2Email: '', ec2Phone: '',
    riskTolerance: 'Moderate', dailyLimit: '50000', perOrderLimit: '10000',
    approvedTickers: 'AAPL,MSFT,GOOGL,AMZN,TSLA,SPY,QQQ,NVDA',
  });
  const [error, setError] = useState('');

  const set = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }));

  const handleLogin = (e) => {
    e.preventDefault();
    setError('');
    const stored = localStorage.getItem(`wg_user_${form.email}`);
    if (!stored) { setError('Account not found. Please register first.'); return; }
    const user = JSON.parse(stored);
    if (user.password !== form.password) { setError('Incorrect password.'); return; }
    localStorage.setItem('wg_current_user', form.email);
    onLogin(user);
  };

  const handleRegister = (e) => {
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
    const tickers = form.approvedTickers.split(',').map(t => t.trim().toUpperCase()).filter(Boolean);
    const user = {
      fullName: form.fullName, email: form.email, password: form.password, phone: form.phone,
      emergencyContacts: [
        { name: form.ec1Name, email: form.ec1Email, phone: form.ec1Phone },
        ...(form.ec2Name ? [{ name: form.ec2Name, email: form.ec2Email, phone: form.ec2Phone }] : []),
      ],
      will: {
        riskTolerance: form.riskTolerance,
        dailyTradeLimit: parseFloat(form.dailyLimit) || 50000,
        perOrderLimit: parseFloat(form.perOrderLimit) || 10000,
        approvedTickers: tickers.length ? tickers : DEFAULT_WILL.approvedTickers,
      },
    };
    localStorage.setItem(`wg_user_${form.email}`, JSON.stringify(user));
    localStorage.setItem('wg_current_user', form.email);
    onLogin(user);
  };

  if (isLogin) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-logo">
            <div className="auth-logo-icon">🛡</div>
            <h1>Will<span>Guard</span></h1>
          </div>
          <h2 className="auth-title">Welcome Back</h2>
          <p className="auth-subtitle">Sign in to your financial safety system</p>
          {error && <div style={{ color: 'var(--accent-red)', fontSize: '0.8rem', marginBottom: 12, padding: '8px 12px', background: 'rgba(255,51,102,0.08)', borderRadius: 6 }}>{error}</div>}
          <form onSubmit={handleLogin}>
            <div className="form-group"><label>Email</label><input type="email" value={form.email} onChange={set('email')} placeholder="you@example.com" required /></div>
            <div className="form-group"><label>Password</label><input type="password" value={form.password} onChange={set('password')} placeholder="••••••••" required /></div>
            <button className="btn-primary" type="submit">Sign In</button>
          </form>
          <div className="auth-switch">Don't have an account? <button onClick={() => { setIsLogin(false); setError(''); }}>Register</button></div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card wide">
        <div className="auth-logo">
          <div className="auth-logo-icon">🛡</div>
          <h1>Will<span>Guard</span></h1>
        </div>
        <h2 className="auth-title">Create Your Account</h2>
        <p className="auth-subtitle">Set up your AI financial safety system</p>
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
            <div className="form-group"><label>Password *</label><input type="password" value={form.password} onChange={set('password')} placeholder="Min 6 characters" required /></div>
          </>)}
          {step === 2 && (<>
            <div className="auth-section-title">Emergency Contact 1 (Required)</div>
            <div className="form-row">
              <div className="form-group"><label>Name *</label><input value={form.ec1Name} onChange={set('ec1Name')} placeholder="Contact name" required /></div>
              <div className="form-group"><label>Phone *</label><input value={form.ec1Phone} onChange={set('ec1Phone')} placeholder="+91 ..." required /></div>
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
          </>)}
          <button className="btn-primary" type="submit">{step < 3 ? 'Continue →' : 'Create Account & Launch'}</button>
        </form>
        {step > 1 && <button style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', marginTop: 12, fontSize: '0.85rem' }} onClick={() => { setStep(s => s - 1); setError(''); }}>← Back</button>}
        <div className="auth-switch">Already have an account? <button onClick={() => { setIsLogin(true); setStep(1); setError(''); }}>Sign In</button></div>
      </div>
    </div>
  );
}
