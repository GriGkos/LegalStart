import { Plus } from 'lucide-react';
import { useState } from 'react';
import { SectionHeading } from './UI';
const questions = [
  ['Сервис заменяет адвоката?', 'Нет. Сервис помогает только систематизировать информацию перед встречей.'],
  ['Будет ли сервис давать юридические советы?', 'Нет. Он не должен самостоятельно давать правовую оценку ситуации.'],
  ['Нужно ли загружать документы?', 'Для демонстрационной версии загрузка документов не обязательна. Не передавайте конфиденциальные документы и персональные данные.'],
  ['Где проходит подготовка?', 'Подготовка проходит в боте. При старте можно выбрать мессенджер: Telegram уже доступен, MAX скоро появится. На сайте можно познакомиться с сервисом и выбрать направление.'],
  ['Можно ли остановиться и продолжить позже?', 'На этапе полноценной реализации бот должен позволять продолжить заполнение позднее. Эта возможность запланирована для будущей версии.'],
  ['Сколько времени занимает подготовка?', 'Обычно предполагается несколько минут, однако время зависит от сложности ситуации.'],
  ['Что получает пользователь в конце?', 'Структурированную карточку обращения, хронологию и список информации для подготовки к консультации.'],
];
export default function FAQ() {
  const [expanded, setExpanded] = useState<number | null>(0);
  return <section id="faq" className="section faq-section"><div className="container faq-grid"><SectionHeading number="08" eyebrow="Ответы перед началом" title="Остались вопросы?" text="Главное о сервисе и его возможностях." /><div className="faq-list">{questions.map(([question, answer], i) => <div key={question} className={`faq-item ${expanded === i ? 'expanded' : ''}`}><h3><button aria-expanded={expanded === i} aria-controls={`faq-answer-${i}`} id={`faq-question-${i}`} onClick={() => setExpanded(expanded === i ? null : i)}>{question}<Plus size={21} aria-hidden="true" /></button></h3><div id={`faq-answer-${i}`} role="region" aria-labelledby={`faq-question-${i}`} hidden={expanded !== i}><p>{answer}</p></div></div>)}</div></div></section>;
}
