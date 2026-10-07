import { Link2, ClipboardList, FileCheck2, Handshake } from 'lucide-react';
const flow = [
  { icon: Link2, title: 'Адвокат отправляет ссылку' },
  { icon: ClipboardList, title: 'Клиент проходит подготовку' },
  { icon: FileCheck2, title: 'Формируется карточка обращения' },
  { icon: Handshake, title: 'Информация готова к первой встрече' },
];
export default function ForLawyers() {
  return <section className="lawyers-section"><div className="container lawyers-panel"><div className="lawyers-copy"><p className="eyebrow"><span>06</span>Для адвокатов и специалистов</p><h2>Сервис полезен<br /><em>не только клиентам.</em></h2><p>Адвокат может направить клиенту персональную ссылку на подготовку перед встречей и заранее получить структурированную информацию.</p><a href="#pricing" className="button button-light">Тариф для специалистов</a></div><ol className="lawyers-flow">{flow.map(({ icon: Icon, title }, i) => <li key={title}><span className="flow-icon"><Icon size={21} strokeWidth={1.5} aria-hidden="true" /></span><span className="flow-content"><small>0{i + 1}</small>{title}</span></li>)}</ol></div></section>;
}
