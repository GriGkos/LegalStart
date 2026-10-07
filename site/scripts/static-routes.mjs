import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
const config = readFileSync('src/config.ts', 'utf8');
const name = config.match(/PROJECT_NAME\s*=\s*['"]([^'"]+)['"]/)?.[1];
if (!name) throw new Error('PROJECT_NAME должен быть строковой константой в src/config.ts');
const escape = value => value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const html = readFileSync('dist/index.html', 'utf8').replaceAll('LegalStart', escape(name));
writeFileSync('dist/index.html', html);
for (const [route, title] of [['privacy', 'Политика конфиденциальности'], ['terms', 'Пользовательское соглашение']]) {
  mkdirSync(`dist/${route}`, { recursive: true });
  const routeHtml = html.replace(/<title>.*?<\/title>/, `<title>${title} — ${escape(name)}</title>`).replace(/(<meta property="og:title" content=")[^"]*("\s*\/?>)/, `$1${title} — ${escape(name)}$2`).replace(/(<meta name="twitter:title" content=")[^"]*("\s*\/?>)/, `$1${title} — ${escape(name)}$2`).replace(/(<meta property="og:url" content=")[^"]*("\s*\/?>)/, `$1https://legalstart-preparation.clean-hill-8774.chatgpt.site/${route}$2`);
  writeFileSync(`dist/${route}/index.html`, routeHtml);
}
console.log('Static routes ready: /, /privacy, /terms');
