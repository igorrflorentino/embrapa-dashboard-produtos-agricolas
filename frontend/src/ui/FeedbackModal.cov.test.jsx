// FeedbackModal.cov.test.jsx — coverage for the "Reportar problema" dialog
// (FeedbackModal.jsx). Drives the open/closed gate, the category pills (radiogroup),
// the textarea + browser-info checkbox, the prefill-seeding open effect, the Esc-to-
// close listener, and the full submit path (success → "done" screen, and the
// catch → error message) by mocking window.postFeedback. window.Icon is stubbed so
// the modal chrome renders in jsdom.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

function stubGlobals() {
  window.Icon = ({ name }) => <i className="icon" data-icon={name} />;
  window.APP_VERSION = '9.9.9';
}

let FeedbackModal;

beforeEach(async () => {
  await import('./FeedbackModal.jsx'); // registers window.FeedbackModal
  FeedbackModal = window.FeedbackModal;
  stubGlobals();
});

afterEach(() => {
  cleanup();
  delete window.postFeedback;
});

describe('FeedbackModal — visibility gate + form chrome', () => {
  it('renders nothing when closed', () => {
    const { container } = render(<FeedbackModal open={false} onClose={() => {}} context={{}} />);
    expect(container.querySelector('.cite-modal')).toBeNull();
  });

  it('renders the three category pills + the message textarea when open', () => {
    const { container } = render(<FeedbackModal open onClose={() => {}} context={{}} />);
    const cats = [...container.querySelectorAll('.fb-cat')].map((b) => b.textContent.trim());
    expect(cats).toEqual(['Problema', 'Dúvida', 'Sugestão']);
    // 'bug' is the default → its pill is active.
    const active = container.querySelector('.fb-cat.active');
    expect(active.textContent).toContain('Problema');
    expect(container.querySelector('textarea.fb-textarea')).toBeTruthy();
    // Submit is disabled while the message is empty.
    const submit = container.querySelector('.btn-primary');
    expect(submit.disabled).toBe(true);
  });

  it('switches the active category when another pill is clicked', () => {
    const { container } = render(<FeedbackModal open onClose={() => {}} context={{}} />);
    const pills = [...container.querySelectorAll('.fb-cat')];
    const sugestao = pills.find((b) => b.textContent.includes('Sugestão'));
    fireEvent.click(sugestao);
    expect(sugestao.classList.contains('active')).toBe(true);
    expect(sugestao.getAttribute('aria-checked')).toBe('true');
  });

  it('seeds category + message from a prefill context on open, and shows the ctx note', () => {
    const { container } = render(
      <FeedbackModal
        open
        onClose={() => {}}
        context={{ category: 'sugestao', message: 'valor estranho', url: '/x', view: 'Referências' }}
      />
    );
    expect(container.querySelector('textarea.fb-textarea').value).toBe('valor estranho');
    const active = container.querySelector('.fb-cat.active');
    expect(active.textContent).toContain('Sugestão');
    // The attached-context caption renders the view name.
    expect(container.textContent).toContain('Contexto anexado:');
    expect(container.textContent).toContain('Referências');
  });

  it('toggles the include-browser checkbox', () => {
    const { container } = render(<FeedbackModal open onClose={() => {}} context={{}} />);
    const cb = container.querySelector('.fb-check input[type="checkbox"]');
    expect(cb.checked).toBe(true); // default on
    fireEvent.click(cb);
    expect(cb.checked).toBe(false);
  });
});

describe('FeedbackModal — close paths', () => {
  it('calls onClose when the backdrop and the close button are clicked', () => {
    const onClose = vi.fn();
    const { container } = render(<FeedbackModal open onClose={onClose} context={{}} />);
    fireEvent.click(container.querySelector('.fm-close'));
    expect(onClose).toHaveBeenCalled();
    fireEvent.click(container.querySelector('.cite-backdrop'));
    expect(onClose.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it('does NOT close when the modal body is clicked (stopPropagation)', () => {
    const onClose = vi.fn();
    const { container } = render(<FeedbackModal open onClose={onClose} context={{}} />);
    fireEvent.click(container.querySelector('.cite-modal'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('closes on the Escape key', () => {
    const onClose = vi.fn();
    render(<FeedbackModal open onClose={onClose} context={{}} />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });
});

describe('FeedbackModal — submit path', () => {
  it('POSTs via window.postFeedback and shows the done screen on success', async () => {
    const postFeedback = vi.fn().mockResolvedValue({ ok: true });
    window.postFeedback = postFeedback;
    const { container } = render(
      <FeedbackModal open onClose={() => {}} context={{ url: '/u', view: 'Overview', banco: 'ibge_pevs' }} />
    );

    fireEvent.change(container.querySelector('textarea.fb-textarea'), {
      target: { value: 'algo quebrou' },
    });
    await act(async () => {
      fireEvent.click(container.querySelector('.btn-primary'));
    });

    expect(postFeedback).toHaveBeenCalledTimes(1);
    const payload = postFeedback.mock.calls[0][0];
    expect(payload.category).toBe('bug');
    expect(payload.message).toBe('algo quebrou');
    expect(payload.url).toBe('/u');
    expect(payload.view).toBe('Overview');
    expect(payload.banco).toBe('ibge_pevs');
    expect(payload.app_version).toBe('9.9.9');
    expect(typeof payload.browser_info).toBe('string'); // checkbox on → UA captured

    // The done screen replaces the form.
    expect(container.textContent).toContain('Obrigado!');
    expect(container.querySelector('textarea.fb-textarea')).toBeNull();
  });

  it('shows the error message when window.postFeedback rejects', async () => {
    window.postFeedback = vi.fn().mockRejectedValue(new Error('rede caiu'));
    const { container } = render(<FeedbackModal open onClose={() => {}} context={{}} />);

    fireEvent.change(container.querySelector('textarea.fb-textarea'), {
      target: { value: 'mensagem' },
    });
    await act(async () => {
      fireEvent.click(container.querySelector('.btn-primary'));
    });

    const err = container.querySelector('.fb-err');
    expect(err).toBeTruthy();
    expect(err.textContent).toBe('rede caiu');
    // Still on the form (not the done screen).
    expect(container.querySelector('textarea.fb-textarea')).toBeTruthy();
  });

  it('omits browser_info when the include-browser checkbox is off', async () => {
    const postFeedback = vi.fn().mockResolvedValue({ ok: true });
    window.postFeedback = postFeedback;
    const { container } = render(<FeedbackModal open onClose={() => {}} context={{}} />);

    fireEvent.click(container.querySelector('.fb-check input[type="checkbox"]')); // turn off
    fireEvent.change(container.querySelector('textarea.fb-textarea'), {
      target: { value: 'sem navegador' },
    });
    await act(async () => {
      fireEvent.click(container.querySelector('.btn-primary'));
    });

    expect(postFeedback.mock.calls[0][0].browser_info).toBeNull();
  });

  it('does not submit when the message is only whitespace', () => {
    const postFeedback = vi.fn();
    window.postFeedback = postFeedback;
    const { container } = render(<FeedbackModal open onClose={() => {}} context={{}} />);
    fireEvent.change(container.querySelector('textarea.fb-textarea'), {
      target: { value: '   ' },
    });
    // Submit stays disabled → clicking is a no-op, and the guard in submit() also bails.
    const submit = container.querySelector('.btn-primary');
    expect(submit.disabled).toBe(true);
    fireEvent.click(submit);
    expect(postFeedback).not.toHaveBeenCalled();
  });
});
