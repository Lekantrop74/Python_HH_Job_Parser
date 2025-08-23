"""
Консольное меню для работы с вакансиями с hh.ru.

Основные возможности:
- Поиск вакансий с использованием API hh.ru.
- Сохранение вакансий в локальную базу данных.
- Просмотр, поиск и фильтрация сохранённых вакансий.
- Экспорт вакансий в CSV или Excel.
- Автоматическая рассылка откликов на сохранённые вакансии через Selenium.
"""

import asyncio
import os
from typing import Optional, Callable, List

from src.Request_func import get_vacancies_async
from src.data_utils import export_vacancies
from src.selenium_utils import apply_to_vacancies_parallel_batched

MAX_PARALLEL_ALLOWED = int(os.getenv("MAX_PARALLEL_ALLOWED", 5))


def get_input(prompt: str, cast: Callable, default: Optional = None) -> Optional:
    """
    Запрашивает ввод у пользователя, приводит к указанному типу или возвращает значение по умолчанию.
    Args:
        prompt (str): Текст запроса для пользователя.
        cast (Callable): Функция для приведения типа (например, int, str).
        default (Optional): Значение по умолчанию, если ввод пустой.
    Returns:
        Optional: Введённое и приведённое к типу значение или default.
    """

    while True:
        val = input(prompt).strip()
        if not val:
            return default
        try:
            return cast(val)
        except (ValueError, TypeError):
            print(f"Неверный ввод. Ожидается значение типа {cast.__name__}.")


menus = {
    "main": [
        "Выберите действие:",
        "1. Поиск и сохранение новых вакансий",
        "2. Показать все сохраненные вакансии",
        "3. Поиск по ключевому слову",
        "4. Очистить таблицу",
        "5. Экспорт вакансий",
        "6. Вход в аккаунт HH (для автоматической рассылки)",
        "7. Отправка отклика и сопроводительного письма для всех сохранённых в БД вакансий",
        "10. Выход"
    ],
    "filter": [
        "Фильтрация вакансий:",
        "(оставьте поле пустым, чтобы пропустить фильтр)"
    ],
    "export": [
        "Выберите формат экспорта:",
        "1. CSV",
        "2. Excel"
    ],
    "selenium": [
        "1. Без открытия окон Chrome в 3 потоках",
        "2. С открытием окон Chrome в 3 потоках",
        "3. Изменить количество потоков + скрытый режим",
        "4. Изменить количество потоков - скрытый режим",
    ],
    "search_field": [
        "1. Только название вакансии (name) (высокое соответствие)",
        "2. Только описание вакансии (description) (низкое соответствие)",
    ],
    "order_by": [
        "1. Сортировка по релевантности",
        "2. Сортировка по дате публикации вакансии",
    ],
}


def print_menu(menu_type: str = "main") -> None:
    """
    Выводит меню на экран.
    Args:
        menu_type (str, optional): Тип меню (ключ из словаря `menus`).
                                   По умолчанию "main".
    """

    print("\n" + "\n".join(menus.get(menu_type, [])))


def print_vacancies(vacancies: List[dict], empty_message: str = "Нет вакансий") -> None:
    """
    Выводит список вакансий в консоль.
    Args:
        vacancies (List[dict]): Список вакансий (каждая вакансия — dict).
        empty_message (str, optional): Сообщение, если список пуст.
                                       По умолчанию "Нет вакансий".
    """

    if not vacancies:
        print(empty_message)
        return
    for i, v in enumerate(vacancies, 1):
        print(
            f"\n{i}. {v.get('vacancy_name', 'Без названия')}\n"
            f"Ссылка: https://hh.ru/vacancy/{v['id']}"
        )


# ==== Обработчики ====

def handle_search_and_save(writer) -> None:
    """
    Выполняет поиск вакансий через API hh.ru, очищает таблицу и сохраняет новые результаты.
    Args:
        writer: Объект для работы с базой данных (должен поддерживать методы
                create_table(), clear_table(), write_data()).
    """

    keyword = get_input("Введите ключевое слово для поиска: ", str)
    max_vacancies = get_input("Введите количество вакансий для поиска (По умолчанию 5): ", int, 5)

    print_menu("search_field")
    search_field_choice = get_input("Введите поле поиска (по умолчанию 1): ", int, 1)
    search_field_map = {
        1: "name",
        2: "description",
    }

    print_menu("order_by")
    order_by_choice = get_input("Введите номер (по умолчанию 1): ", int, 1)
    order_by_map = {
        1: None,
        2: "publication_time",
    }

    skills_input = get_input(
        "\nВведите навыки для фильтрации по key_skills через запятую, например: Python, pandas."
        "\nЗначительно повышает соответствие поиска. (Полезно при поиске по description)"
        "\nНо также значительно замедляет скорость поиска и количество прошедших фильтр вакансий "
        "\n(есть риск нарваться на капчу HH что прекратит поиск, чтобы этого не произошло держите показатель <1.5 it/s)"
        "\nЕсли поиск по name лучше оставить пустым"
        "\nОставьте пустым для пропуска: ",
        str,
        ""
    )
    required_skills = [s.strip() for s in skills_input.split(",") if s.strip()] or None

    try:
        vacancies, _ = asyncio.run(
            get_vacancies_async(
                keyword=keyword,
                max_vacancies=max_vacancies,
                search_field=search_field_map.get(search_field_choice, "name"),
                order_by=order_by_map.get(order_by_choice),
                required_skills=required_skills
            )
        )
    except KeyboardInterrupt:
        print("\nОперация прервана пользователем.")
        return

    writer.create_table()
    writer.clear_table()
    writer.write_data(vacancies)

    print(f"\nНайдено и сохранено {len(vacancies)} вакансий")


def handle_show_all(writer) -> None:
    """
    Показывает все сохранённые вакансии.
    Args:
        writer: Объект для работы с базой данных (метод get_all_vacancies()).
    """

    vacancies = writer.get_all_vacancies()
    print_vacancies(vacancies, "Нет сохраненных вакансий")


def handle_search_by_keyword(writer) -> None:
    """
    Выполняет поиск сохранённых вакансий по ключевому слову.
    Args:
        writer: Объект для работы с базой данных (метод get_vacancies_by_keyword()).
    """

    keyword = get_input("Введите ключевое слово для поиска: ", str)
    vacancies = writer.get_vacancies_by_keyword(keyword)
    print_vacancies(vacancies, "Вакансии не найдены")


def handle_export(writer) -> None:
    """
    Экспортирует вакансии в CSV или Excel.
    Args:
        writer: Объект для работы с базой данных (метод get_all_vacancies()).
    """

    vacancies = writer.get_all_vacancies()
    if not vacancies:
        print("Нет сохраненных вакансий")
        return

    print_menu("export")
    formats = {"1": "csv", "2": "xlsx"}
    choice = get_input("Введите номер формата: ", str)
    file_format = formats.get(choice)

    if file_format:
        filename = export_vacancies(vacancies, file_format=file_format)
        print(f"Данные экспортированы в файл: {filename}")
    else:
        print("Неверный выбор формата")


def get_parallel_driver_count() -> int:
    """
    Запрашивает у пользователя количество параллельных Selenium-драйверов.
    Returns:
        int: Количество потоков (от 1 до MAX_PARALLEL_ALLOWED).
    """

    while True:
        count = get_input(f"Введите число потоков (1–{MAX_PARALLEL_ALLOWED}): ", int)
        if count is not None and 1 <= count <= MAX_PARALLEL_ALLOWED:
            return count
        print(f"❗ Число должно быть от 1 до {MAX_PARALLEL_ALLOWED}")


def send_apply_to_vacancy(writer) -> None:
    """
    Отправляет отклики на все сохранённые вакансии через Selenium.
    Args:
        writer: Объект для работы с базой данных (метод get_all_vacancies()).
    """

    vacancies = writer.get_all_vacancies()
    if not vacancies:
        print("Нет вакансий для отклика.")
        return

    print_menu("selenium")
    choice = get_input("Введите номер формата: ", int)

    if choice in (1, 2):
        shadow = (choice == 1)
        asyncio.run(apply_to_vacancies_parallel_batched(vacancies, shadow=shadow))
    elif choice in (3, 4):
        shadow = (choice == 3)
        count = get_parallel_driver_count()
        asyncio.run(apply_to_vacancies_parallel_batched(vacancies, shadow=shadow, max_parallel_drivers=count))
    else:
        print("❌ Неизвестный выбор.")


def clear_table(writer) -> None:
    """
    Очищает таблицу вакансий в базе данных.
    Args:
        writer: Объект для работы с базой данных (метод clear_table()).
    """

    writer.clear_table()
    print("База данных очищена.")


def exit_program(_=None) -> None:
    """
    Завершает выполнение программы.
    """

    print("До свидания!")
    exit()
