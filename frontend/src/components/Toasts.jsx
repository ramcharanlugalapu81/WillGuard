import { useState, useCallback, useRef } from 'react';

let toastIdCounter = 0;
let globalAddToast = null;

export function useToasts() {
  const [toasts, setToasts] = useState([]);
  const timersRef = useRef({});

  const addToast = useCallback((type, title, msg, actions = null) => {
    const id = ++toastIdCounter;
    setToasts(prev => [...prev, { id, type, title, msg, actions }]);
    if (!actions) {
      timersRef.current[id] = setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
        delete timersRef.current[id];
      }, 4000);
    }
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
    if (timersRef.current[id]) { clearTimeout(timersRef.current[id]); delete timersRef.current[id]; }
  }, []);

  globalAddToast = addToast;
  return { toasts, addToast, removeToast };
}

export function getGlobalAddToast() { return globalAddToast; }

export default function ToastContainer({ toasts, removeToast }) {
  const icons = { execute: '✅', freeze: '🛑', notify: '⚠️', info: 'ℹ️' };
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.type}`}>
          <span className="toast-icon">{icons[t.type] || 'ℹ️'}</span>
          <div className="toast-content">
            <div className="toast-title">{t.title}</div>
            <div className="toast-msg">{t.msg}</div>
            {t.actions && (
              <div className="toast-actions">
                <button className="toast-confirm" onClick={() => { t.actions.onConfirm(); removeToast(t.id); }}>Confirm</button>
                <button className="toast-cancel" onClick={() => { t.actions.onCancel(); removeToast(t.id); }}>Cancel</button>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
