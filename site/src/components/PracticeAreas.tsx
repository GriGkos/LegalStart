import { ShieldCheck, CarFront, UsersRound, BriefcaseBusiness, House, MessagesSquare } from 'lucide-react';
import { PRACTICE_AREAS } from '../config';
import { SectionHeading, MessengerButton } from './UI';
const icons = { shield: ShieldCheck, car: CarFront, family: UsersRound, briefcase: BriefcaseBusiness, house: House, message: MessagesSquare };
export default function PracticeAreas() {
  return <section id="practice-areas" className="section areas-section"><div className="container"><SectionHeading number="03" eyebrow="Начните со своей ситуации" title="Выберите направление" text="Сценарий подготовки меняется в зависимости от ситуации." /><div className="areas-grid">{PRACTICE_AREAS.map((area, i) => { const Icon = icons[area.icon]; return <article className="area-card" key={area.start}><div className="card-top"><span className="area-icon"><Icon size={28} strokeWidth={1.4} aria-hidden="true" /></span><span>0{i + 1}</span></div><h3>{area.title}</h3><p>{area.description}</p><MessengerButton start={area.start} secondary className="area-button"><span>Начать</span><span className="sr-only">: {area.title}</span></MessengerButton></article>; })}</div></div></section>;
}
