"""
Модуль для автоматизации откликов на вакансии на сайте hh.ru

Этот модуль предоставляет функциональность для:
- Автоматического отклика на вакансии
- Заполнения сопроводительных писем
- Обработки различных статусов вакансий (уже откликались, отказали)
- Параллельной обработки вакансий с использованием нескольких браузеров

Основные компоненты:
- Управление cookies для авторизации
- Проверка статуса вакансии перед откликом
- Генерация сопроводительных писем из шаблона
- Пакетная обработка вакансий с параллелизмом
"""

import asyncio
import pickle
from functools import lru_cache
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Конфигурация Chrome драйвера для headless режима
options = Options()
options.add_argument("--headless=new")  # Новый headless режим Chrome
options.add_argument("--disable-gpu")  # Отключение GPU для стабильности
options.add_argument("--window-size=1920,1080")  # Размер окна браузера
options.add_argument("--no-sandbox")  # Отключение sandbox для Docker
options.add_argument("--disable-dev-shm-usage")  # Отключение /dev/shm
options.page_load_strategy = 'eager'  # Стратегия загрузки страницы
# Отключение загрузки изображений, CSS и шрифтов для ускорения
options.add_experimental_option("prefs", {
    "profile.managed_default_content_settings.images": 2,
    "profile.managed_default_content_settings.stylesheets": 2,
    "profile.managed_default_content_settings.fonts": 2,
})

# Константы конфигурации
LETTER_TEMPLATE_PATH = "src/cover_letter.txt"  # Путь к шаблону сопроводительного письма
# MAX_PARALLEL_DRIVERS = 3  # Максимальное количество параллельных браузеров
PAGE_TIMEOUT = 5  # Таймаут ожидания элементов страницы (в секундах)


def save_cookies():
    """
    Сохраняет cookies для авторизации на hh.ru
    
    Функция открывает браузер, переходит на страницу входа и ждет
    ручного входа пользователя. После входа сохраняет cookies в файл
    для последующего использования в автоматических откликах.
    
    Файл cookies.pkl создается в текущей директории.
    """
    driver = webdriver.Chrome()
    driver.get("https://hh.ru/account/login")
    input("Войдите в аккаунт и нажмите Enter...")
    with open("cookies.pkl", "wb") as file:
        pickle.dump(driver.get_cookies(), file)
    driver.quit()


def load_cookies(driver):
    """
    Загружает сохраненные cookies в браузер для авторизации
    
    Args:
        driver: Экземпляр WebDriver для загрузки cookies
        
    Функция загружает cookies из файла cookies.pkl и применяет их
    к текущей сессии браузера для автоматической авторизации.
    """
    driver.get("https://hh.ru")
    with open("cookies.pkl", "rb") as file:
        for cookie in pickle.load(file):
            driver.add_cookie(cookie)
    driver.refresh()


def check_and_click_apply(driver):
    """
    Проверяет возможность отклика на вакансию и нажимает кнопку отклика
    
    Args:
        driver: Экземпляр WebDriver для взаимодействия со страницей
        
    Returns:
        tuple: (success, status, message)
            - success (bool): Успешность операции
            - status (str): Статус операции ("applied", "already_applied", "rejected", "error")
            - message (str): Описательное сообщение о результате
            
    Функция выполняет следующие проверки:
    1. Проверяет, не откликались ли уже на эту вакансию
    2. Проверяет, не получили ли отказ по этой вакансии
    3. Если проверки пройдены - нажимает кнопку "Откликнуться"
    4. Обрабатывает возможное появление кнопки "Все равно откликнуться"
    """
    try:
        # Список проверок для пропуска вакансий
        skip_checks = [
            {
                "xpath": '//*[translate(normalize-space(.), "\u00A0", " ")="Вы откликнулись"]',
                "reason": "already_applied",
                "message": "Уже откликнулись"
            },
            {
                "xpath": '//*[contains(@class, "magritte-text") and contains(text(), "Вам отказали")]',
                "reason": "rejected",
                "message": "Отказ"
            }
        ]

        # Проверяем каждое условие для пропуска
        for check in skip_checks:
            if driver.find_elements(By.XPATH, check["xpath"]):
                return False, check["reason"], check["message"]

        # Ищем и нажимаем кнопку "Откликнуться"
        apply_button = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((
                By.XPATH,
                '//div[not(@data-qa="vacancy-serp__vacancy") and contains'
                '(@class, "magritte-card")]//span[text()="Откликнуться"]'
            ))
        )
        apply_button.click()

        # Обрабатываем возможную кнопку "Все равно откликнуться"
        try:
            relocate_button = WebDriverWait(driver, 1).until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//span[text()="Все равно откликнуться"]/ancestor::button'))
            )
            relocate_button.click()
        except TimeoutException:
            # Кнопка не появилась - это нормально
            pass

        return True, "applied", "✅ Кнопка отклика нажата"

    except TimeoutException:
        return False, "error", "❌ Не удалось найти кнопку отклика"


@lru_cache
def load_letter_template(path=LETTER_TEMPLATE_PATH):
    """
    Загружает шаблон сопроводительного письма из файла
    
    Args:
        path (str): Путь к файлу с шаблоном письма
        
    Returns:
        str or None: Содержимое шаблона или None в случае ошибки
        
    Использует декоратор @lru_cache для кэширования шаблона
    и избежания повторного чтения файла.
    """
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"❌ Ошибка при загрузке шаблона: {e}")
        return None


def generate_cover_letter(name):
    """
    Генерирует сопроводительное письмо на основе шаблона
    
    Args:
        name (str): Название вакансии для подстановки в шаблон
        
    Returns:
        str or None: Сгенерированное письмо или None если шаблон не найден
        
    Подставляет название вакансии в шаблон письма используя
    метод format() с параметром vacancy_name.
    """
    template = load_letter_template()
    return template.format(vacancy_name=name) if template else None


def fill_and_submit_cover_letter(driver, name):
    """
    Заполняет и отправляет сопроводительное письмо
    
    Args:
        driver: Экземпляр WebDriver для взаимодействия со страницей
        name (str): Название вакансии для генерации письма
        
    Returns:
        tuple: (success, status, message)
            - success (bool): Успешность операции
            - status (str): Статус операции ("applied", "error")
            - message (str): Описательное сообщение о результате
            
    Функция выполняет следующие действия:
    1. Находит поле для ввода сопроводительного письма
    2. Генерирует письмо на основе шаблона
    3. Заполняет поле текстом письма
    4. Нажимает кнопку "Отправить"
    """
    try:
        # Ищем label для сопроводительного письма
        label = WebDriverWait(driver, PAGE_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, '//label[contains(text(), "Сопроводительное письмо")]'))
        )
        label_id = label.get_attribute("id")

        # Находим textarea по aria-labelledby атрибуту
        textarea = driver.find_element(By.XPATH, f'//textarea[@aria-labelledby="{label_id}"]')
        letter = generate_cover_letter(name)

        if not letter:
            return False, "error", "⏭ Пропущено: шаблон не найден"

        # Очищаем поле и вводим текст письма
        textarea.clear()
        textarea.send_keys(letter)

        # Находим и нажимаем кнопку "Отправить"
        submit = WebDriverWait(driver, PAGE_TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, '//button[.//span[text()="Отправить"]]'))
        )
        submit.click()
        return True, "applied", "✅ Письмо отправлено"

    except TimeoutException:
        return False, "error", "❌ Не удалось найти кнопку отклика"


def process_single_vacancy(driver, vacancy):
    """
    Обрабатывает одну вакансию: отклик и отправка сопроводительного письма
    
    Args:
        driver: Экземпляр WebDriver для взаимодействия со страницей
        vacancy (dict): Словарь с информацией о вакансии
            Должен содержать ключи:
            - 'url': URL вакансии
            - 'vacancy_name': Название вакансии
            
    Returns:
        tuple: (success, status, message)
            - success (bool): Успешность операции
            - status (str): Статус операции
            - message (str): Описательное сообщение с названием вакансии
            
    Функция выполняет полный цикл обработки вакансии:
    1. Переход на страницу вакансии
    2. Проверка возможности отклика
    3. Заполнение и отправка сопроводительного письма (если отклик возможен)
    """
    try:
        driver.get(vacancy['url'])

        # Пытаемся откликнуться на вакансию
        success, status, message = check_and_click_apply(driver)

        if success:
            # Если отклик успешен, заполняем сопроводительное письмо
            success, status, message = fill_and_submit_cover_letter(driver, vacancy['vacancy_name'])
            return success, status, f"{message}: {vacancy['vacancy_name']}"
        else:
            # Если отклик не удался, возвращаем информацию о причине
            return False, status, f"⏭ Пропущено ({message}): {vacancy['vacancy_name']}"

    except Exception as e:
        return False, "error", f"❌ Ошибка: {vacancy['vacancy_name']} ({e})"


def apply_to_vacancy_batch(vacancies, final_stats, shadow):
    """
    Обрабатывает пакет вакансий в одном браузере
    
    Args:
        vacancies (list): Список словарей с информацией о вакансиях
        final_stats (dict): Словарь для накопления статистики
            Должен содержать ключи: "applied", "already_applied", "rejected", "errors"
        shadow (bool): Запускать с сокрытием окон webdriver.Chrome() или нет.
            
    Функция создает один экземпляр браузера и обрабатывает все вакансии
    из пакета последовательно. Статистика накапливается в final_stats.
    
    В конце работы браузер автоматически закрывается.
    """

    driver = webdriver.Chrome(options=options if shadow else None)
    load_cookies(driver)

    # Счетчики для текущего пакета
    applied = already_applied = rejected = errors = 0
    total = len(vacancies)

    try:
        for idx, vacancy in enumerate(vacancies, 1):
            success, status, message = process_single_vacancy(driver, vacancy)

            # Обновляем счетчики в зависимости от статуса
            if status == "applied":
                applied += 1
            elif status == "already_applied":
                already_applied += 1
            elif status == "rejected":
                rejected += 1
            else:
                errors += 1

            # Выводим прогресс обработки
            print(
                f"\n{message}"
                f"\n📊 {idx}/{total} "
                f"| ✅ Новые: {applied} | ⏭ Уже были: {already_applied} "
                f"| ❌ Отказ: {rejected} | 🛑 Ошибки: {errors}")

    finally:
        # Добавляем статистику текущего пакета к общей статистике
        final_stats["applied"] += applied
        final_stats["already_applied"] += already_applied
        final_stats["rejected"] += rejected
        final_stats["errors"] += errors
        driver.quit()


async def apply_to_vacancies_parallel_batched(vacancies, shadow=True, MAX_PARALLEL_DRIVERS = 3):
    """
    Обрабатывает вакансии параллельно с использованием нескольких браузеров
    
    Args:
        vacancies (list): Список словарей с информацией о вакансиях
        shadow (bool): Список словарей с информацией о вакансиях
        
    Функция разделяет все вакансии на пакеты и обрабатывает их
    параллельно с использованием MAX_PARALLEL_DRIVERS браузеров.
    
    В конце выводит итоговую статистику по всем обработанным вакансиям.
    
    Пример использования:
        await apply_to_vacancies_parallel_batched(vacancies_list)
    """
    # Вычисляем размер пакета для равномерного распределения
    batch_size = (len(vacancies) + MAX_PARALLEL_DRIVERS - 1) // MAX_PARALLEL_DRIVERS
    batches = [vacancies[i:i + batch_size] for i in range(0, len(vacancies), batch_size)]

    # Инициализируем общую статистику
    final_stats = {"applied": 0, "already_applied": 0, "rejected": 0, "errors": 0}

    async def run_batch(batch):
        """Внутренняя функция для запуска пакета в отдельном потоке"""
        return await asyncio.to_thread(apply_to_vacancy_batch, batch, final_stats, shadow)

    # Запускаем все пакеты параллельно
    await asyncio.gather(*[run_batch(batch) for batch in batches])

    # Выводим итоговую статистику
    print(f"\n🎯 Финальный результат: из {len(vacancies)}")
    print(f"👉 Новых откликов: {final_stats['applied']}")
    print(f"⏭ Уже откликались: {final_stats['already_applied']}")
    print(f"❌ Получен отказ: {final_stats['rejected']}")
    print(f"🛑 Ошибки: {final_stats['errors']}")
