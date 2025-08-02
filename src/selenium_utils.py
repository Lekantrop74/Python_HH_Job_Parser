import asyncio
import pickle
from functools import lru_cache
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Конфигурация драйвера
options = Options()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.page_load_strategy = 'eager'
options.add_experimental_option("prefs", {
    "profile.managed_default_content_settings.images": 2,
    "profile.managed_default_content_settings.stylesheets": 2,
    "profile.managed_default_content_settings.fonts": 2,
})

LETTER_TEMPLATE_PATH = "src/cover_letter.txt"
MAX_PARALLEL_DRIVERS = 3
PAGE_TIMEOUT = 5  # вместо 2


def save_cookies():
    driver = webdriver.Chrome()
    driver.get("https://hh.ru/account/login")
    input("Войдите в аккаунт и нажмите Enter...")
    with open("cookies.pkl", "wb") as file:
        pickle.dump(driver.get_cookies(), file)
    driver.quit()


def load_cookies(driver):
    driver.get("https://hh.ru")
    with open("cookies.pkl", "rb") as file:
        for cookie in pickle.load(file):
            driver.add_cookie(cookie)
    driver.refresh()


def check_and_click_apply(driver):
    try:
        skip_checks = [
            {
                "xpath": '//*[translate(normalize-space(.), "\u00A0", " ")="Вы откликнулись"]',
                "reason": "⏭ Уже откликались"
            },
            {
                "xpath": '//*[contains(@class, "magritte-text") and contains(text(), "Вам отказали")]',
                "reason": "⏭ Получен отказ"
            }
        ]

        for check in skip_checks:
            if driver.find_elements(By.XPATH, check["xpath"]):
                print(check["reason"])
                return False

        apply_button = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((
                By.XPATH,
                '//div[not(@data-qa="vacancy-serp__vacancy") and contains(@class, "magritte-card")]//span[text()="Откликнуться"]'
            ))
        )
        apply_button.click()

        try:
            relocate_button = WebDriverWait(driver, 1).until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//span[text()="Все равно откликнуться"]/ancestor::button'))
            )
            relocate_button.click()
        except TimeoutException:
            pass

        return True

    except TimeoutException:
        return False


@lru_cache
def load_letter_template(path=LETTER_TEMPLATE_PATH):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"❌ Ошибка при загрузке шаблона: {e}")
        return None


def generate_cover_letter(name):
    template = load_letter_template()
    return template.format(vacancy_name=name) if template else None


def fill_and_submit_cover_letter(driver, name):
    try:
        label = WebDriverWait(driver, PAGE_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, '//label[contains(text(), "Сопроводительное письмо")]'))
        )
        label_id = label.get_attribute("id")

        textarea = driver.find_element(By.XPATH, f'//textarea[@aria-labelledby="{label_id}"]')
        letter = generate_cover_letter(name)

        if not letter:
            return False, "⏭ Пропущено: шаблон не найден"

        textarea.clear()
        textarea.send_keys(letter)

        submit = WebDriverWait(driver, PAGE_TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, '//button[.//span[text()="Отправить"]]'))
        )
        submit.click()
        return True, "✅ Письмо отправлено"

    except TimeoutException:
        return False, "❌ Не удалось отправить"


def process_single_vacancy(driver, vacancy):
    try:
        driver.get(vacancy['url'])

        if check_and_click_apply(driver):
            success, message = fill_and_submit_cover_letter(driver, vacancy['vacancy_name'])
        else:
            return False, f"⏭ Уже откликались: {vacancy['vacancy_name']}"

        return success, f"{message}: {vacancy['vacancy_name']}"

    except Exception as e:
        return False, f"❌ Ошибка: {vacancy['vacancy_name']} ({e})"


def apply_to_vacancy_batch(vacancies):
    driver = webdriver.Chrome()
    load_cookies(driver)

    applied, skipped = 0, 0
    total = len(vacancies)

    try:
        for idx, vacancy in enumerate(vacancies, 1):
            success, message = process_single_vacancy(driver, vacancy)
            applied += success
            skipped += not success
            print(f"{message}\n📊 {idx}/{len(vacancies)} | ✅ {applied} | ⏭ {skipped}")

    finally:
        print(f"\n🎯 Итог: из {total} вакансий")
        print(f"👉 Новых откликов: {applied}")
        print(f"⏭ Пропущено (уже откликались/ошибки): {skipped}")
        driver.quit()


async def apply_to_vacancies_parallel_batched(vacancies):
    batch_size = (len(vacancies) + MAX_PARALLEL_DRIVERS - 1) // MAX_PARALLEL_DRIVERS
    batches = [vacancies[i:i + batch_size] for i in range(0, len(vacancies), batch_size)]

    async def run_batch(batch):
        return await asyncio.to_thread(apply_to_vacancy_batch, batch)

    results = await asyncio.gather(*[run_batch(batch) for batch in batches])
    return results
