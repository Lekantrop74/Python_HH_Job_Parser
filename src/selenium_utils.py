import asyncio
import pickle
import time

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

MAX_PARALLEL_DRIVERS = 3


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


def wait_for_page_load(driver, timeout=2):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def check_and_click_apply(driver):
    try:
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


def already_applied(driver):
    try:
        label_elem = driver.find_element(By.XPATH, '//label[contains(text(), "Сопроводительное письмо")]')
        label_id = label_elem.get_attribute("id")
        letter_field = driver.find_element(By.XPATH, f'//textarea[@aria-labelledby="{label_id}"]')
        existing_text = letter_field.get_attribute("value") or ""
        return bool(existing_text.strip())
    except NoSuchElementException:
        return False


def load_letter_template(path="src/cover_letter.txt"):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"❌ Ошибка при загрузке шаблона письма: {e}")
        return None


LETTER_TEMPLATE = load_letter_template()


def generate_cover_letter(name):
    if not LETTER_TEMPLATE:
        return None
    return LETTER_TEMPLATE.format(vacancy_name=name)


def fill_and_submit_cover_letter(driver, vacancy_name):
    try:
        label_elem = WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.XPATH, '//label[contains(text(), "Сопроводительное письмо")]'))
        )
        label_id = label_elem.get_attribute("id")
        letter_field = WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.XPATH, f'//textarea[@aria-labelledby="{label_id}"]'))
        )

        letter = generate_cover_letter(vacancy_name)
        if not letter:
            return False, "⏭ Пропущено: шаблон письма не найден"

        letter_field.clear()
        letter_field.send_keys(letter)

        submit_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, '//button[.//span[text()="Отправить"]]'))
        )
        submit_btn.click()
        time.sleep(1)
        return True, "✅ Письмо отправлено"

    except TimeoutException:
        return False, "❌ Ошибка: не удалось отправить письмо"


def process_single_vacancy(driver, vacancy):
    url = vacancy['url']
    name = vacancy['vacancy_name']
    try:
        driver.get(url)
        wait_for_page_load(driver)

        if check_and_click_apply(driver):
            success, message = fill_and_submit_cover_letter(driver, name)

        elif not already_applied(driver):
            success, message = fill_and_submit_cover_letter(driver, name)

        else:
            return False, f"⏭ Уже откликались: {name}"

        return success, f"{message}: {name}"

    except Exception as e:
        return False, f"❌ Ошибка: {name} ({str(e)})"


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
            print(f"{message}\n📊 Обработано: {idx}/{len(vacancies)} | Новых: {applied} | Пропущено: {skipped}")

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
