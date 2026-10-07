import { SectionHeading } from './UI';
const steps = [
  ['Выберите ситуацию', 'Укажите направление, по которому планируете обратиться к адвокату.'],
  ['Выберите мессенджер', 'Бот предложит вопросы, подходящие именно для выбранной ситуации.'],
  ['Подготовьте сведения', 'Соберите основные обстоятельства, даты и перечень имеющихся документов.'],
  ['Получите итог', 'Система сформирует структурированную карточку обращения и персональный список для подготовки.'],
];
export default function HowItWorks() {
  return <section id="how-it-works" className="section how-section"><div className="container"><SectionHeading number="02" eyebrow="Понятный процесс" title="От вопроса до подготовленной заявки — несколько шагов" /><div className="steps-grid">{steps.map(([title, text], i) => <article className="process-step" key={title}><div className="step-number"><span>0{i + 1}</span><div aria-hidden="true" /></div><h3>{title}</h3><p>{text}</p></article>)}</div><div className="process-note"><span>На сайте — знакомство с сервисом.</span><span>Подготовка и оформление заявки — в боте.</span></div></div></section>;
}
