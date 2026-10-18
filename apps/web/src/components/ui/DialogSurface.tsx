import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

type Props = {
  title: string;
  onClose: () => void;
  children: ReactNode;
  variant: 'modal' | 'drawer';
  className?: string;
};

/** Shared modal lifecycle for both surfaces: focus, inert background and scroll ownership. */
export function DialogSurface({ title, onClose, children, variant, className = '' }: Props) {
  const titleId = useId();
  const dialog = useRef<HTMLElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const closeAction = useRef(onClose);
  useEffect(() => {
    closeAction.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    const background = [...document.body.children].filter(
      (element) => !element.contains(dialog.current),
    );
    const wasInert = background.map((element) => element.hasAttribute('inert'));
    background.forEach((element) => element.setAttribute('inert', ''));
    document.body.style.overflow = 'hidden';
    close.current?.focus();
    const focusable = () =>
      [
        ...(dialog.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]',
        ) ?? []),
      ].filter((element) => {
        const collapsed = element.closest('details:not([open])');
        return (
          !element.hidden &&
          getComputedStyle(element).display !== 'none' &&
          (!collapsed || collapsed.querySelector('summary') === element)
        );
      });
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeAction.current();
      }
      if (event.key !== 'Tab') return;
      const items = focusable();
      const first = items[0];
      const last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    const keepFocus = (event: FocusEvent) => {
      if (event.target instanceof Node && !dialog.current?.contains(event.target))
        close.current?.focus();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('focusin', keepFocus);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('focusin', keepFocus);
      background.forEach((element, index) => {
        if (!wasInert[index]) element.removeAttribute('inert');
      });
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);

  return createPortal(
    <div
      className={'overlay' + (variant === 'drawer' ? ' drawer-overlay' : '') + ' ' + className}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className={variant}
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <header>
          <h2 id={titleId}>{title}</h2>
          <button
            ref={close}
            className="icon-button"
            onClick={onClose}
            aria-label={variant === 'drawer' ? 'Close drawer' : 'Close dialog'}
          >
            <X aria-hidden="true" />
          </button>
        </header>
        <div className="dialog-content">{children}</div>
      </section>
    </div>,
    document.body,
  );
}
