export const PROJECT_NAME = 'LegalStart';
// Замените на username настоящего бота без символа @.
export const TELEGRAM_BOT_USERNAME = 'ADVOKAT_PROJECTBOT';
// Ссылка будет добавлена после подключения бота в MAX.
export const MAX_BOT_URL: string = '';
export const telegramUrl = (start = 'website') => `https://t.me/${TELEGRAM_BOT_USERNAME.replace(/^@/, '')}?start=${encodeURIComponent(start)}`;
export const NAV_LINKS = [
  { label: 'Как работает', href: '#how-it-works' },
  { label: 'Возможности', href: '#practice-areas' },
  { label: 'Тарифы', href: '#pricing' },
  { label: 'FAQ', href: '#faq' },
];
export const PRACTICE_AREAS = [
  { title: 'Уголовное право', description: 'Подготовка информации перед обращением по вопросам уголовного процесса.', start: 'criminal', icon: 'shield' },
  { title: 'ДТП', description: 'Систематизация обстоятельств происшествия и имеющихся документов.', start: 'traffic', icon: 'car' },
  { title: 'Семейные споры', description: 'Подготовка информации по вопросам брака, имущества, алиментов и других семейных ситуаций.', start: 'family', icon: 'family' },
  { title: 'Трудовые споры', description: 'Подготовка материалов по вопросам трудовых отношений.', start: 'labor', icon: 'briefcase' },
  { title: 'Имущественные споры', description: 'Сбор исходной информации по имущественным разногласиям.', start: 'property', icon: 'house' },
  { title: 'Другая ситуация', description: 'Если подходящего направления нет, бот поможет начать с общей анкеты.', start: 'other', icon: 'message' },
] as const;
export const PRICING = [
  { name: 'Базовый', price: '0 ₽', suffix: 'для первого знакомства', features: ['Определение направления', 'Общий список подготовки', 'Переход к конструктору в боте'], button: 'Попробовать', start: 'basic', featured: false },
  { name: 'Полная подготовка', price: '490 ₽', suffix: 'за одно обращение', features: ['Персонализированный сценарий', 'Структурирование ситуации', 'Индивидуальный чек-лист', 'Хронология событий', 'Итоговая карточка обращения'], button: 'Начать подготовку', start: 'full', featured: true },
  { name: 'Для специалистов', price: 'от 1 990 ₽', suffix: 'в месяц', features: ['Персональные ссылки', 'Подготовка клиентов до встречи', 'Структурированные карточки обращений', 'Отдельные сценарии'], button: 'Подробнее', start: 'specialists', featured: false },
];
