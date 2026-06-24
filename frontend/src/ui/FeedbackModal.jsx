// FeedbackModal.jsx — the "Reportar problema" dialog. Captures a category + a free-text
// message and AUTO-attaches reproduction context (the permalink to the current dashboard
// state, the active view/banco, app version, optional user-agent) so a report is
// actionable without the researcher copying anything. POSTs via window.postFeedback;
// the author is captured server-side from the IAP identity — there is no login field.
// Reuses the citation modal's chrome classes (cite-backdrop/cite-modal/…). Registered
// as a window global (like the other ui/ modules) and rendered by AppShell.

const FB_CATS = [
  { id: 'bug', label: 'Problema', icon: 'bug_report' },
  { id: 'duvida', label: 'Dúvida', icon: 'help' },
  { id: 'sugestao', label: 'Sugestão', icon: 'lightbulb' },
];

window.FeedbackModal = function FeedbackModal({ open, onClose, context }) {
  const [category, setCategory] = React.useState('bug');
  const [message, setMessage] = React.useState('');
  const [includeBrowser, setIncludeBrowser] = React.useState(true);
  const [status, setStatus] = React.useState('idle'); // idle | sending | done | error
  const [errMsg, setErrMsg] = React.useState('');

  // Reset to a clean form each time the dialog opens.
  React.useEffect(() => {
    if (open) {
      setCategory('bug');
      setMessage('');
      setStatus('idle');
      setErrMsg('');
    }
  }, [open]);

  // Esc closes (mirrors the citation modal).
  React.useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  const ctx = context || {};

  const submit = async () => {
    const text = message.trim();
    if (!text || status === 'sending' || !window.postFeedback) return;
    setStatus('sending');
    setErrMsg('');
    try {
      await window.postFeedback({
        category,
        message: text,
        url: ctx.url || (typeof location !== 'undefined' ? location.href : ''),
        view: ctx.view || '',
        banco: ctx.banco || '',
        app_version: window.APP_VERSION || '',
        browser_info: includeBrowser && typeof navigator !== 'undefined' ? navigator.userAgent : null,
      });
      setStatus('done');
    } catch (e) {
      setStatus('error');
      setErrMsg((e && e.message) || 'Falha ao enviar. Tente novamente.');
    }
  };

  return (
    <div className="cite-backdrop" onClick={onClose}>
      <div className="cite-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="fb-title">
        <header className="cite-head">
          <div>
            <div className="overline">Feedback</div>
            <h2 id="fb-title">Reportar problema ou sugestão</h2>
            <p className="caption">
              Sua mensagem é registrada com o link da tela atual (perspectiva e filtros) e
              seu e-mail institucional, para que a equipe consiga reproduzir e responder.
            </p>
          </div>
          <button className="fm-close" onClick={onClose} aria-label="Fechar">
            <window.Icon name="close" size={18}/>
          </button>
        </header>
        <div className="cite-body">
          {status === 'done' ? (
            <div className="fb-done">
              <window.Icon name="check_circle" size={28}/>
              <p>Obrigado! Seu feedback foi registrado e a equipe vai analisá-lo.</p>
              <div className="cite-actions">
                <button className="btn-primary" onClick={onClose}>Fechar</button>
              </div>
            </div>
          ) : (
            <>
              <div className="fb-cats" role="radiogroup" aria-label="Tipo de feedback">
                {FB_CATS.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    role="radio"
                    aria-checked={category === c.id}
                    className={'fb-cat' + (category === c.id ? ' active' : '')}
                    onClick={() => setCategory(c.id)}>
                    <window.Icon name={c.icon} size={16}/> {c.label}
                  </button>
                ))}
              </div>
              <label className="fb-label" htmlFor="fb-msg">O que aconteceu? (e o que você esperava)</label>
              <textarea
                id="fb-msg"
                className="fb-textarea"
                rows={5}
                value={message}
                maxLength={5000}
                autoFocus
                placeholder="Descreva o problema, a dúvida ou a sugestão…"
                onChange={(e) => setMessage(e.target.value)}
              />
              <label className="fb-check">
                <input
                  type="checkbox"
                  checked={includeBrowser}
                  onChange={(e) => setIncludeBrowser(e.target.checked)}
                />
                Incluir informações do navegador (ajuda no diagnóstico)
              </label>
              {ctx.url && (
                <p className="caption fb-ctx">
                  Contexto anexado: <code>{ctx.view || 'tela atual'}</code> + link de reprodução.
                </p>
              )}
              {status === 'error' && <p className="fb-err" role="alert">{errMsg}</p>}
              <div className="cite-actions">
                <button className="btn-secondary" onClick={onClose}>Cancelar</button>
                <button
                  className="btn-primary"
                  disabled={!message.trim() || status === 'sending'}
                  onClick={submit}>
                  {status === 'sending' ? 'Enviando…' : 'Enviar feedback'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
