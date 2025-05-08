import pickle
import time

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def save_cookies():
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
        return True
    except NoSuchElementException:
        return False


def generate_cover_letter(name, description):
    """
    Генерирует простое сопроводительное письмо на основе названия вакансии и её описания.
    Вставляет ключевые навыки, если они упомянуты в тексте вакансии.

    :param name: Название вакансии
    :param description: Текст описания вакансии
    :return: Строка с текстом сопроводительного письма
    """
    intro = f"Здравствуйте! Я заинтересован в вакансии '{name}'."
    body = "Ваше предложение заинтересовало меня по следующим причинам:"

    # Подбор навыков по ключевым словам
    skills = [s for s, kw in {
        "опыт работы с Python": "Python",
        "знание Django": "Django",
        "опыт работы с базами данных": "SQL"
    }.items() if kw in description]

    closing = "Буду рад обсудить детали. Спасибо за внимание!"
    return f"{intro}\n{body} {', '.join(skills)}.\n{closing}"


def apply_to_vacancy(vacancies):
    """
    Автоматически переходит по URL'ам вакансий и откликается на них через браузер.
    Предварительно использует сохранённые cookies для авторизации.
    Пропускает вакансии, на которые уже был отклик или при ошибках.

    :param vacancies: Список словарей, содержащих ключи:
                      - 'url' (str): ссылка на вакансию
                      - 'vacancy_name' (str): название вакансии
                      - 'description' (str): текст описания
    """
    driver = webdriver.Chrome()

    try:
        # Авторизация через cookies
        load_cookies(driver)

        for vacancy in vacancies:
            vacancy_url = vacancy['url']
            vacancy_name = vacancy['vacancy_name']
            vacancy_description = vacancy['description']

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
                    apply_button = driver.find_element(By.XPATH, '//span[text()="Откликнуться"]')
                    apply_button.click()
                except NoSuchElementException:
                    print(f"❌ Кнопка отклика не найдена: {vacancy_name}")
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
                    letter = generate_cover_letter(vacancy_name, vacancy_description)
                    letter_field = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, 'textarea.magritte-native-element___a0RAE_2-1-14'))
                    )
                    letter_field.clear()
                    letter_field.send_keys(letter)
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
