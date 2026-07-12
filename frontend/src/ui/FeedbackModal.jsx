// FeedbackModal.jsx — the "Enviar feedback" dialog (problema / dúvida / sugestão).
// Captures a category + a free-text
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

  // Keep the latest context in a ref so the open-effect can seed from it WITHOUT adding
  // `context` (a fresh object literal each render) to the deps — which would reset the
  // textarea on every parent re-render, wiping what the user is typing.
  const ctxRef = React.useRef(context);
  ctxRef.current = context;

  // Idempotency key: STABLE across a retry of the SAME submission (a timeout that actually
  // landed, or a double-click), so the backend dedupes instead of inserting a second BigQuery
  // row AND opening a second GitHub issue. Rotated after a committed submit; fresh per open.
  const cidRef = React.useRef(null);
  const _fbUuid = () =>
    (window.crypto && window.crypto.randomUUID)
      ? window.crypto.randomUUID()
      : 'fb-' + Math.random().toString(36).slice(2) + Date.now().toString(36);

  // Reset the form each time the dialog opens, SEEDING from any prefill (category/message)
  // — the Referências "report a value" loop opens the dialog pre-filled.
  React.useEffect(() => {
    if (open) {
      const c = ctxRef.current || {};
      setCategory(c.category || 'bug');
      setMessage(c.message || '');
      setStatus('idle');
      setErrMsg('');
      cidRef.current = null; // a fresh submission gets a fresh idempotency key
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
    if (!cidRef.current) cidRef.current = _fbUuid(); // stable across retries of THIS submission
    try {
      await window.postFeedback({
        category,
        message: text,
        url: ctx.url || (typeof location !== 'undefined' ? location.href : ''),
        view: ctx.view || '',
        banco: ctx.banco || '',
        app_version: window.APP_VERSION || '',
        browser_info: includeBrowser && typeof navigator !== 'undefined' ? navigator.userAgent : null,
        change_id: cidRef.current,
      });
      setStatus('done');
      cidRef.current = null; // committed → rotate so a later feedback isn't deduped onto this one
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
            <h2 id="fb-title">Fale com a equipe</h2>
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
