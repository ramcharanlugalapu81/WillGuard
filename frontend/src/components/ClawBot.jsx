import { useState, useRef, useEffect } from 'react';

const HELP_TEXT = `
ClawBot — One-Line Trade Terminal
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Commands:
  buy <qty> <TICKER>     → Buy shares (e.g. "buy 10 AAPL")
  sell <qty> <TICKER>    → Sell shares (e.g. "sell 5 TSLA")
  quote <TICKER>         → Get live price (e.g. "quote MSFT")
  status                 → Show system mode & risk
  portfolio              → Show current holdings
  reset                  → Reset system to initial state
  help                   → Show this help
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All trades pass through ArmorClaw enforcement.
`;

export default function ClawBot({ onTrade, mode, portfolio, risk, userId, backendConnected, onReset, onRecordActivity }) {
  const [history, setHistory] = useState([
    { type: 'system', text: 'ClawBot v1.0 — WillGuard Trade Terminal' },
    { type: 'system', text: 'Type "help" for available commands. All trades enforced by ArmorClaw.' },
  ]);
  const [input, setInput] = useState('');
  const [processing, setProcessing] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const addLine = (type, text) => setHistory(h => [...h, { type, text }]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || processing) return;

    const cmd = input.trim();
    addLine('user', `> ${cmd}`);
    setInput('');
    setProcessing(true);

    if (onRecordActivity) onRecordActivity();

    try {
      await processCommand(cmd.toLowerCase());
    } catch (err) {
      addLine('error', `Error: ${err.message}`);
    }

    setProcessing(false);
  };

  const processCommand = async (cmd) => {
    const parts = cmd.split(/\s+/);
    const action = parts[0];

    // ── help ──
    if (action === 'help') {
      addLine('system', HELP_TEXT);
      return;
    }

    // ── status ──
    if (action === 'status') {
      addLine('info', `System Mode: ${mode.toUpperCase()}`);
      addLine('info', `Risk Score: ${(risk.total * 100).toFixed(0)}/100`);
      addLine('info', `Portfolio: $${portfolio.totalValue.toLocaleString()}`);
      addLine('info', `Cash: $${portfolio.cash.toLocaleString()}`);
      addLine('info', `Backend: ${backendConnected ? 'Connected' : 'Offline'}`);
      return;
    }

    // ── portfolio ──
    if (action === 'portfolio') {
      addLine('info', `Total Value: $${portfolio.totalValue.toLocaleString()}`);
      addLine('info', `Cash Available: $${portfolio.cash.toLocaleString()}`);
      if (portfolio.positions && portfolio.positions.length > 0) {
        portfolio.positions.forEach(p => {
          const pnlColor = (p.pnl || 0) >= 0 ? '' : '';
          addLine('info', `  ${pnlColor} ${p.symbol}: ${p.qty} shares (P&L: $${(p.pnl || 0).toFixed(2)})`);
        });
      } else {
        addLine('info', '  No open positions.');
      }
      return;
    }

    // ── reset ──
    if (action === 'reset') {
      if (onReset) await onReset();
      addLine('success', 'System reset to initial state.');
      return;
    }

    // ── quote ──
    if (action === 'quote') {
      if (!parts[1]) { addLine('error', 'Usage: quote <TICKER>'); return; }
      const ticker = parts[1].toUpperCase();
      addLine('info', `Fetching quote for ${ticker}...`);
      try {
        const res = await fetch(`http://localhost:8000/api/quote/${ticker}`);
        const data = await res.json();
        if (data.ask_price) {
          addLine('success', `${ticker}: Ask $${data.ask_price} | Bid $${data.bid_price} | Last $${data.last_price || 'N/A'}`);
        } else {
          addLine('info', `${ticker}: Price ~$${data.price || 'N/A'} (${data.source || 'simulated'})`);
        }
      } catch {
        addLine('error', `Could not fetch quote for ${ticker}`);
      }
      return;
    }

    // ── buy / sell ──
    if (action === 'buy' || action === 'sell') {
      if (!parts[1] || !parts[2]) {
        addLine('error', `Usage: ${action} <quantity> <TICKER>`);
        return;
      }
      const qty = parseFloat(parts[1]);
      const symbol = parts[2].toUpperCase();

      if (isNaN(qty) || qty <= 0) {
        addLine('error', 'Quantity must be a positive number.');
        return;
      }

      addLine('info', `Processing: ${action.toUpperCase()} ${qty} ${symbol}...`);
      addLine('info', `   → ArmorClaw enforcement check...`);

      try {
        const result = await onTrade({ symbol, quantity: qty, side: action });

        if (result) {
          const zone = result.decision?.zone || 'UNKNOWN';
          const allowed = result.decision?.allowed;
          const reason = result.decision?.reason || '';
          const riskScore = result.risk_score?.total || 0;
          const riskMethod = result.risk_score?.method || 'heuristic';

          if (allowed) {
            addLine('success', `EXECUTED: ${action.toUpperCase()} ${qty} ${symbol}`);
            addLine('success', `   Zone: ${zone} | Risk: ${(riskScore * 100).toFixed(0)}/100 (${riskMethod})`);
            if (result.execution?.id) {
              addLine('success', `   Order ID: ${result.execution.id}`);
            }
          } else {
            addLine('blocked', `BLOCKED: ${action.toUpperCase()} ${qty} ${symbol}`);
            addLine('blocked', `   Zone: ${zone} | Reason: ${reason}`);
          }
        }
      } catch (err) {
        addLine('error', `Trade failed: ${err.message}`);
      }
      return;
    }

    // ── unknown command ──
    addLine('error', `Unknown command: "${parts[0]}". Type "help" for commands.`);
  };

  return (
    <div className="clawbot-terminal">
      <div className="clawbot-header">
        <div className="clawbot-title">
          <span className="clawbot-icon">🤖</span>
          <span>ClawBot Terminal</span>
          <span className={`clawbot-mode ${mode}`}>{mode.toUpperCase()}</span>
        </div>
        <div className="clawbot-actions">
          <button className="clawbot-clear" onClick={() => setHistory([
            { type: 'system', text: 'ClawBot v1.0 — Terminal cleared.' },
          ])}>Clear</button>
        </div>
      </div>

      <div className="clawbot-output" ref={scrollRef}>
        {history.map((line, i) => (
          <div key={i} className={`clawbot-line ${line.type}`}>
            <pre>{line.text}</pre>
          </div>
        ))}
        {processing && (
          <div className="clawbot-line processing">
            <pre>Processing...</pre>
          </div>
        )}
      </div>

      <form className="clawbot-input-row" onSubmit={handleSubmit}>
        <span className="clawbot-prompt">$</span>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="buy 10 AAPL • sell 5 TSLA • quote MSFT • help"
          disabled={processing}
          autoFocus
        />
      </form>
    </div>
  );
}
