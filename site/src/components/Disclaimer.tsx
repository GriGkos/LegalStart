import { Info } from 'lucide-react';
import { PROJECT_NAME } from '../config';
export default function Disclaimer() {
  return <aside className="container disclaimer" aria-labelledby="disclaimer-title"><span className="disclaimer-icon"><Info size={24} aria-hidden="true" /></span><div><h2 id="disclaimer-title">Важно</h2><p>{PROJECT_NAME} является сервисом предварительной подготовки информации. Он не оказывает юридическую помощь, не анализирует перспективы дела, не формирует правовую позицию и не заменяет консультацию адвоката или иного квалифицированного специалиста.</p><p className="disclaimer-emphasis">На демонстрационной версии проекта не рекомендуется передавать конфиденциальные документы или персональные данные.</p></div></aside>;
}
