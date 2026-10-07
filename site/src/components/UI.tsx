import { MessageCircle, Send, X } from 'lucide-react';
import { useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { MAX_BOT_URL, telegramUrl } from '../config';
export function MessengerButton({ children = 'Начать подготовку', start = 'website', secondary = false, className = '' }: { children?: ReactNode; start?: string; secondary?: boolean; className?: string }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  return <>
    <button type="button" className={`button ${secondary ? 'button-secondary' : 'button-primary'} ${className}`} onClick={() => dialogRef.current?.showModal()} aria-haspopup="dialog"><MessageCircle size={17} aria-hidden="true" />{children}<span className="sr-only"> (выбрать мессенджер)</span></button>
    {createPortal(<dialog ref={dialogRef} className="messenger-dialog" aria-labelledby={titleId} onKeyDown={event => { if (event.key === 'Escape') event.stopPropagation(); }} onClick={event => {
      if (event.target !== event.currentTarget) return;
      const bounds = event.currentTarget.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialogRef.current?.close();
    }}>
      <button type="button" className="messenger-close" aria-label="Закрыть выбор мессенджера" onClick={() => dialogRef.current?.close()}><X size={22} aria-hidden="true" /></button>
      <h2 id={titleId}>Выберите мессенджер</h2>
      <p>Где вам удобнее начать подготовку?</p>
      <div className="messenger-options">
        <a className="button button-primary" href={telegramUrl(start)} target="_blank" rel="noopener noreferrer" onClick={() => dialogRef.current?.close()}><Send size={19} aria-hidden="true" />Telegram<span className="sr-only"> (открывается в новой вкладке)</span></a>
        {MAX_BOT_URL ? <a className="button button-secondary" href={MAX_BOT_URL} target="_blank" rel="noopener noreferrer" onClick={() => dialogRef.current?.close()}><MessageCircle size={19} aria-hidden="true" />MAX<span className="sr-only"> (открывается в новой вкладке)</span></a> : <button type="button" className="button button-secondary messenger-pending" disabled><MessageCircle size={19} aria-hidden="true" />MAX<span className="messenger-soon">Скоро</span></button>}
      </div>
    </dialog>, document.body)}
  </>;
}
export function SectionHeading({ number, eyebrow, title, text }: { number: string; eyebrow: string; title: string; text?: string }) {
  return <div className="section-heading"><p className="eyebrow"><span>{number}</span>{eyebrow}</p><h2>{title}</h2>{text && <p className="section-intro">{text}</p>}</div>;
}
