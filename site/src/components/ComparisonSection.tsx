import { Check, Minus } from 'lucide-react';
import { PROJECT_NAME } from '../config';
import { SectionHeading } from './UI';
const before = ['Обстоятельства вспоминаются во время встречи', 'Документы собираются после консультации', 'Часть информации может быть упущена', 'Время уходит на организационные вопросы'];
const after = ['Основные сведения собраны заранее', 'События расположены по хронологии', 'Есть список документов', 'Сформулирована цель обращения', 'Консультацию проще начать с сути ситуации'];
export default function ComparisonSection() {
  return <section className="section comparison-section"><div className="container"><SectionHeading number="05" eyebrow="Разница в подходе" title={`Обычная подготовка vs ${PROJECT_NAME}`} /><div className="comparison-grid"><article className="comparison-card before-card"><p className="comparison-kicker">Как бывает обычно</p><h3>Без предварительной подготовки</h3><ul>{before.map(text => <li key={text}><Minus size={18} aria-hidden="true" />{text}</li>)}</ul></article><article className="comparison-card after-card"><p className="comparison-kicker">Когда всё собрано заранее</p><h3>С {PROJECT_NAME}</h3><ul>{after.map(text => <li key={text}><Check size={18} aria-hidden="true" />{text}</li>)}</ul></article></div></div></section>;
}
