import { useEffect, useRef, useState } from 'react';
import { Menu, X } from 'lucide-react';
import { NAV_LINKS, PROJECT_NAME } from '../config';
import { MessengerButton } from './UI';
export default function Header({ legalPage = false }: { legalPage?: boolean }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    function onKey(event: KeyboardEvent) { if (event.key === 'Escape' && open) { setOpen(false); menuRef.current?.focus(); } }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);
  return <header className="header"><div className="container header-inner"><a href="/" className="brand" aria-label={`${PROJECT_NAME} — главная`}><span className="brand-mark" aria-hidden="true">L<span /></span>{PROJECT_NAME}<span className="brand-separator" /><span className="brand-tag">До первой встречи</span></a><nav className="desktop-nav" aria-label="Основная навигация">{NAV_LINKS.map(link => <a key={link.href} href={`${legalPage ? '/' : ''}${link.href}`}>{link.label}</a>)}</nav><div className="header-actions"><MessengerButton className="header-cta" /><button ref={menuRef} className="menu-toggle" onClick={() => setOpen(!open)} aria-label={open ? 'Закрыть меню' : 'Открыть меню'} aria-expanded={open} aria-controls="mobile-menu">{open ? <X /> : <Menu />}</button></div></div>{open && <nav id="mobile-menu" className="mobile-nav" aria-label="Мобильная навигация">{NAV_LINKS.map(link => <a key={link.href} href={`${legalPage ? '/' : ''}${link.href}`} onClick={() => setOpen(false)}>{link.label}</a>)}<MessengerButton /></nav>}</header>;
}
