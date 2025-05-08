import re

import requests
import time
from tqdm import tqdm  # Библиотека для отображения прогресса выполнения


def clean_html(raw_html):
    """
    Очищает HTML-разметку из текста, убирая теги и форматируя списки.
    """
    clean_text = re.sub(r'<br>', '\n', raw_html)  # Заменяем <br> на перенос строки
    clean_text = re.sub(r'<[^>]+>', '', clean_text)  # Убираем все HTML-теги
    clean_text = re.sub(r'&[^;]+;', ' ', clean_text)  # Убираем HTML-энкодированные символы
    clean_text = re.sub(r'\n+', '\n', clean_text).strip()  # Убираем лишние пустые строки
    return clean_text


def get_vacancies_HH(keyword, max_vacancies):
    """
    Получает вакансии с сайта HH.ru по заданному ключевому слову с учетом пагинации.

    Аргументы:
    - keyword (str): ключевое слово для поиска вакансий (например, "Python разработчик").
    - max_vacancies (int): максимальное количество вакансий для загрузки.

    Возвращает:
    - data (list): список словарей с информацией о найденных вакансиях.
    - total_found (int): общее количество найденных вакансий.
    """

    url_vacancy = "https://api.hh.ru/vacancies"  # URL API HH.ru для поиска вакансий
    per_page = 100  # Максимальное количество вакансий на одной странице
    page = 0  # Номер страницы
    data = []  # Список для хранения вакансий

    headers = {
        "User-Agent": "my-hh-bot"  # Указываем User-Agent, иначе API может отказать в доступе
    }

    # Первый запрос, чтобы узнать общее количество вакансий
    response_init = requests.get(url_vacancy, params={"text": keyword, "per_page": 1, "page": 0}, headers=headers)

    if response_init.status_code != 200:
        print("Ошибка при получении общего количества вакансий:", response_init.status_code)
        return [], 0

    total_found = response_init.json().get("found", 0)  # Общее количество найденных вакансий

    # Пока не достигли лимита вакансий и есть вакансии
    while len(data) < max_vacancies and page * per_page < total_found:
        params_vacancy = {
            "text": keyword,  # Ключевое слово для поиска
            "per_page": per_page,  # Количество вакансий на странице
            "page": page  # Текущая страница
        }

        # Отправляем GET-запрос на API
        response_vacancy = requests.get(url_vacancy, params=params_vacancy, headers=headers)

        if response_vacancy.status_code != 200:
            print("Ошибка при выполнении запроса:", response_vacancy.status_code)
            break

        vacancies = response_vacancy.json()["items"]  # Получаем список вакансий

        if not vacancies:  # Если вакансий больше нет, выходим из цикла
            break

        # Используем tqdm для отображения прогресса обработки вакансий
        for vacancy in tqdm(vacancies, desc=f"Страница {page + 1}", ncols=80, ascii=True):
            # Получаем детальную информацию о вакансии
            vacancy_details = requests.get(f"https://api.hh.ru/vacancies/{vacancy['id']}", headers=headers).json()

            # Проверяем наличие данных о зарплате
            salary_from = vacancy["salary"]["from"] if vacancy["salary"] and vacancy["salary"]["from"] else None
            salary_to = vacancy["salary"]["to"] if vacancy["salary"] and vacancy["salary"]["to"] else None

            # Очищаем описание вакансии от HTML-тегов
            cleaned_description = clean_html(vacancy_details.get("description", "Описание отсутствует"))

            # Создаем словарь с данными о вакансии
            vacancy_data = {
                "id": vacancy["id"],  # ID вакансии
                "name": vacancy["name"],  # Название вакансии
                "url": vacancy["alternate_url"],  # Ссылка на вакансию
                "salary_from": salary_from,  # Нижняя граница зарплаты
                "salary_to": salary_to,  # Верхняя граница зарплаты
                "area": vacancy["area"]["name"],  # Город
                "description": cleaned_description  # Очищенное описание вакансии
            }

            # Добавляем вакансию в список
            data.append(vacancy_data)

            # Если достигли лимита, выходим
            if len(data) >= max_vacancies:
                break

            # Добавляем небольшую задержку для эффекта прогресс-бара и чтобы не перегружать API
            time.sleep(0.01)

        page += 1  # Переходим на следующую страницу

    print(f"Всего загружено {len(data)} вакансий из {total_found} найденных по запросу '{keyword}'")

    return data
