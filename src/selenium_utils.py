import pickle
import time

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument("--headless=new")  # новый режим headless
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")  # для правильной отрисовки
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.page_load_strategy = 'eager'


def save_cookies(Wr):
    """
    Открывает браузер Chrome, переходит на страницу входа hh.ru и сохраняет cookies после ручного входа пользователя.
    Cookies сохраняются в файл 'cookies.pkl' для последующего использования без повторного входа.
    """
    driver = webdriver.Chrome()
    driver.get("https://hh.ru/account/login")
    input("Войдите в аккаунт и нажмите Enter...")
    with open("cookies.pkl", "wb") as file:
        pickle.dump(driver.get_cookies(), file)
    driver.quit()


def load_cookies(driver):
    """
    Загружает cookies из файла 'cookies.pkl' в переданный экземпляр Selenium WebDriver.
    После загрузки cookies страница hh.ru обновляется, чтобы применить авторизацию.

    :param driver: Экземпляр Selenium WebDriver
    """
    driver.get("https://hh.ru")
    with open("cookies.pkl", "rb") as file:
        for cookie in pickle.load(file):
            driver.add_cookie(cookie)
    driver.get("https://hh.ru")  # Перезагрузка страницы после добавления cookies


def check_and_click_apply(driver):
    """
    Проверяет наличие кнопки 'Откликнуться' в основной карточке.
    Если кнопка есть — кликает, иначе считает, что отклик уже был.

    :param driver: экземпляр Selenium WebDriver
    :return: True, если клик по кнопке выполнен;
             False, если кнопки не было (уже откликался или отказ)
    """
    try:
        # Пробуем найти кнопку "Откликнуться"
        apply_button = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((
                By.XPATH,
                '//div[not(@data-qa="vacancy-serp__vacancy") and contains(@class, "magritte-card")]//span[text()="Откликнуться"]'
            ))
        )
        apply_button.click()
        # print("✅ Клик по кнопке 'Откликнуться' выполнен")

        # Обработка окна с предупреждением про вакансию в другой стране
        try:
            relocate_button = WebDriverWait(driver, 1).until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//span[text()="Все равно откликнуться"]/ancestor::button'))
            )
            relocate_button.click()
            # print("⚠️ Подтвержден отклик на вакансию в другой стране.")
        except TimeoutException:
            pass  # Окно не появилось — всё нормально

        return True

    except TimeoutException:
        # print("⏭ Нет кнопки 'Откликнуться' — возможно, уже откликались или отказ")
        return False


def fill_and_submit_cover_letter(driver, vacancy_name):
    """
    Вставляет сопроводительное письмо и кликает кнопку отправки.

    :return: (успех: bool, сообщение: str)
    """
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

    except TimeoutException:
        return False, "❌ Поле письма не найдено"

    try:
        submit_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, '//button[.//span[text()="Отправить"]]'))
        )
        submit_btn.click()
        time.sleep(1)
        return True, "✅ Письмо отправлено"
    except TimeoutException:
        return False, "❌ Кнопка отправки не найдена"


def already_applied(driver):
    """
    Проверяет, есть ли поле сопроводительного письма и заполнено ли оно.

    :param driver: Selenium WebDriver
    :return: True, если письмо уже есть и заполнено, False если письма нет или оно пустое
    """
    try:
        label_elem = driver.find_element(By.XPATH, '//label[contains(text(), "Сопроводительное письмо")]')
        label_id = label_elem.get_attribute("id")
        letter_field = driver.find_element(By.XPATH, f'//textarea[@aria-labelledby="{label_id}"]')
        existing_text = letter_field.get_attribute("value") or ""
        return bool(existing_text.strip())
    except NoSuchElementException:
        # Если поле письма нет — считаем, что письмо не вставлено
        return False


def generate_cover_letter(name, path="src/cover_letter.txt"):
    """
    Загружает сопроводительное письмо из файла и подставляет название вакансии.

    :param name: Название вакансии
    :param path: Путь к файлу с шаблоном письма
    :return: Текст сопроводительного письма
    """
    try:
        with open(path, encoding='utf-8') as f:
            template = f.read()

        # Подставляем название вакансии, если в письме есть плейсхолдер {vacancy_name}
        return template.format(vacancy_name=name)

    except Exception as e:
        print(f"❌ Ошибка при загрузке письма: {e}")
        return None


def try_fill_and_submit(driver, vacancy_name):
    success, message = fill_and_submit_cover_letter(driver, vacancy_name)
    return success, message


def apply_to_vacancy(vacancies):
    driver = webdriver.Chrome(options=options)
    len_vacancies = len(vacancies)
    vacancy_count = 0
    applied_count = 0
    skipped_count = 0

    try:
        load_cookies(driver)

        for vacancy in vacancies:
            vacancy_url = vacancy['url']
            vacancy_name = vacancy['vacancy_name']
            vacancy_count += 1


            try:
                driver.get(vacancy_url)
                WebDriverWait(driver, 2).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )

                if check_and_click_apply(driver):
                    success, message = try_fill_and_submit(driver, vacancy_name)
                    if success:
                        applied_count += 1
                    else:
                        skipped_count += 1
                    status_message = f"{message}: {vacancy_name}"
                else:
                    if not already_applied(driver):
                        success, message = try_fill_and_submit(driver, vacancy_name)
                        if success:
                            applied_count += 1
                        else:
                            skipped_count += 1
                        status_message = f"{message}: {vacancy_name}"
                    else:
                        skipped_count += 1
                        status_message = f"⏭ Уже откликались: {vacancy_name}"

            except Exception as e:
                skipped_count += 1
                status_message = f"❌ Ошибка: {vacancy_name} ({str(e)})"

            # Единый и чистый вывод статуса после каждой вакансии
            print(f"{status_message}\n📊 Обработано: {vacancy_count}/{len_vacancies} | Новых откликов: {applied_count} | Пропущено: {skipped_count}\n")

    finally:
        print(f"\n🎯 Итог: из {len_vacancies} вакансий")
        print(f"👉 Новых откликов: {applied_count}")
        print(f"⏭ Пропущено (уже откликались/ошибки): {skipped_count}")
        driver.quit()
