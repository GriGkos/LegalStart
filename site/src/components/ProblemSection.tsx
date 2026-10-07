import { Brain, Files, ListOrdered, Clock3 } from 'lucide-react';
import { PROJECT_NAME } from '../config';
import { SectionHeading } from './UI';
const problems = [
  { icon: Brain, title: 'Забываются важные обстоятельства', text: 'При разговоре сложно сразу вспомнить все даты, события и детали.' },
  { icon: Files, title: 'Не хватает документов', text: 'Клиент может не знать заранее, какие материалы могут понадобиться.' },
  { icon: ListOrdered, title: 'Нарушается хронология', text: 'События приходится восстанавливать уже во время разговора.' },
  { icon: Clock3, title: 'Тратится время консультации', text: 'Часть встречи уходит на сбор сведений, которые можно было подготовить заранее.' },
];
export default function ProblemSection() {
  return <section className="section problem-section"><div className="container"><div className="heading-split"><SectionHeading number="01" eyebrow="Сначала — ясность" title="Почему к первой консультации стоит подготовиться?" /><p className="section-intro">На первой встрече значительная часть времени может уходить не на обсуждение ситуации, а на восстановление фактов и поиск необходимой информации.</p></div><div className="problem-grid">{problems.map(({ icon: Icon, title, text }, i) => <article className="problem-card" key={title}><div className="card-top"><Icon size={25} strokeWidth={1.4} aria-hidden="true" /><span>0{i + 1}</span></div><h3>{title}</h3><p>{text}</p></article>)}</div><p className="problem-conclusion"><span className="tiny-line" />{PROJECT_NAME} помогает систематизировать эту информацию ещё до встречи.</p></div></section>;
}
