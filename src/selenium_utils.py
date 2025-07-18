import pickle
import time

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


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


def already_applied(driver):
    """
    Проверяет, был ли уже отклик на вакансию на текущей странице.

    :param driver: Экземпляр Selenium WebDriver
    :return: True, если отклик уже был отправлен; False, если нет
    """
    try:
        driver.find_element(By.XPATH, '//div[contains(text(), "Вы откликнулись")]')
        # 2. Попробовать найти поле сопроводительного письма
        try:
            label_elem = driver.find_element(By.XPATH, '//label[contains(text(), "Сопроводительное письмо")]')
            label_id = label_elem.get_attribute("id")
            letter_field = driver.find_element(By.XPATH, f'//textarea[@aria-labelledby="{label_id}"]')

            # 3. Проверить, заполнено ли поле
            existing_text = letter_field.get_attribute("value") or ""
            return bool(existing_text.strip())  # True — если поле не пустое
        except NoSuchElementException:
            # Если поле письма вообще не отображается, считаем, что его и не требовалось — значит, всё ок
            return True
    except NoSuchElementException:
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


def apply_to_vacancy(vacancies):
    """
    Автоматически переходит по URL'ам вакансий и откликается на них через браузер.
    Предварительно использует сохранённые cookies для авторизации.
    Пропускает вакансии, на которые уже был отклик или при ошибках.

    :param vacancies: Список словарей, содержащих ключи:
                      - 'url' (str): ссылка на вакансию
                      - 'vacancy_name' (str): название вакансии
    """
    driver = webdriver.Chrome()

    try:
        # Авторизация через cookies
        load_cookies(driver)

        for vacancy in vacancies:
            vacancy_url = vacancy['url']
            vacancy_name = vacancy['vacancy_name']

            try:
                # Переход на страницу вакансии
                driver.get(vacancy_url)

                # Ожидание полной загрузки страницы
                WebDriverWait(driver, 15).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )

                # Проверка: уже откликались?
                if already_applied(driver):
                    print(f"⏭ Пропущено: Уже откликнулись на «{vacancy_name}»")
                    continue

                # Клик по кнопке "Откликнуться"
                try:
                    apply_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((
                            By.XPATH,
                            '//div[not(@data-qa="vacancy-serp__vacancy") and contains(@class, "magritte-card")]//span[text()="Откликнуться"]'
                        ))
                    )
                    apply_button.click()
                except TimeoutException:
                    print(f"❌ Кнопка отклика не найдена в основной карточке: {vacancy_name}")
                    continue

                # Обработка окна подтверждения отклика на вакансию в другой стране
                try:
                    relocate_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, '//span[text()="Все равно откликнуться"]/ancestor::button'))
                    )
                    relocate_button.click()
                    print("⚠️ Подтвержден отклик на вакансию в другой стране.")
                except TimeoutException:
                    pass  # Окно не появилось — всё в порядке

                # Генерация и вставка сопроводительного письма
                try:
                    letter = generate_cover_letter(vacancy_name)
                    # Найти label с текстом "Сопроводительное письмо"
                    label_elem = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (By.XPATH, '//label[contains(text(), "Сопроводительное письмо")]'))
                    )

                    # Получить значение его id
                    label_id = label_elem.get_attribute("id")

                    # Найти textarea, у которого aria-labelledby == id найденного label
                    letter_field = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, f'//textarea[@aria-labelledby="{label_id}"]'))
                    )

                    # Очистить и вставить текст
                    letter_field.clear()
                    if letter:  # только если письмо удалось загрузить
                        letter_field.send_keys(letter)
                    else:
                        print(f"⏭ Пропущено: сопроводительное письмо не вставлено для «{vacancy_name}»")
                        continue
                except TimeoutException:
                    print(f"❌ Не удалось найти поле для письма: {vacancy_name}")
                    continue

                time.sleep(3)  # Дать время на рендеринг UI

                # Клик по кнопке "Отправить"
                try:
                    submit_btn = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, '//button[.//span[text()="Отправить"]]'))
                    )
                    submit_btn.click()
                except TimeoutException:
                    print(f"❌ Кнопка отправки не найдена: {vacancy_name}")
                    continue

                time.sleep(1)  # Небольшая пауза после отклика
                print(f"✅ Отклик отправлен: {vacancy_name}")

            except Exception as e:
                # Общая ошибка по вакансии — лог и переход к следующей
                print(f"❌ Ошибка при обработке вакансии «{vacancy_name}»: {e}")
                continue

    finally:
        # Закрытие браузера
        driver.quit()
