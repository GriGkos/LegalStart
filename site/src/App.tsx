import Header from './components/Header';
import Hero from './components/Hero';
import ProblemSection from './components/ProblemSection';
import HowItWorks from './components/HowItWorks';
import PracticeAreas from './components/PracticeAreas';
import ResultSection from './components/ResultSection';
import ComparisonSection from './components/ComparisonSection';
import ForLawyers from './components/ForLawyers';
import Pricing from './components/Pricing';
import Disclaimer from './components/Disclaimer';
import FAQ from './components/FAQ';
import FinalCTA from './components/FinalCTA';
import Footer from './components/Footer';
import LegalPage from './pages/LegalPage';
import { useEffect } from 'react';
import { PROJECT_NAME } from './config';
export default function App() {
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  const legalType = path === '/privacy' ? 'privacy' : path === '/terms' ? 'terms' : null;
  useEffect(() => {
    const title = legalType ? `${legalType === 'privacy' ? 'Политика конфиденциальности' : 'Пользовательское соглашение'} — ${PROJECT_NAME}` : `${PROJECT_NAME} — подготовка к первой встрече с адвокатом`;
    document.title = title;
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', title);
    document.querySelector('meta[property="og:site_name"]')?.setAttribute('content', PROJECT_NAME);
  }, [legalType]);
  return <><a href="#main" className="skip-link">К содержимому</a><Header legalPage={!!legalType} /><main id="main">{legalType ? <LegalPage type={legalType} /> : path === '/' ? <><Hero /><ProblemSection /><HowItWorks /><PracticeAreas /><ResultSection /><ComparisonSection /><ForLawyers /><Pricing /><Disclaimer /><FAQ /><FinalCTA /></> : <section className="container legal-page"><h1>Страница не найдена</h1><a className="button button-primary" href="/">На главную</a></section>}</main><Footer legalPage={path !== '/'} /></>;
}
