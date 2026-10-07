import { Check } from 'lucide-react';
import { PRICING } from '../config';
import { SectionHeading, MessengerButton } from './UI';
export default function Pricing() {
  return <section id="pricing" className="section pricing-section"><div className="container"><SectionHeading number="07" eyebrow="Выберите глубину подготовки" title="Начните с того, что вам нужно" text="От общего списка до полной картины вашего обращения." /><div className="pricing-grid">{PRICING.map(plan => <article key={plan.start} className={`price-card ${plan.featured ? 'featured' : ''}`}>{plan.featured && <span className="price-badge">Всё для первой встречи</span>}<h3>{plan.name}</h3><div className="price">{plan.price}</div><p className="price-suffix">{plan.suffix}</p><ul>{plan.features.map(feature => <li key={feature}><Check size={16} aria-hidden="true" />{feature}</li>)}</ul><MessengerButton start={plan.start} secondary={!plan.featured}>{plan.button}</MessengerButton></article>)}</div><p className="pricing-note">Цены — часть демонстрационной бизнес-модели учебного проекта.</p></div></section>;
}
