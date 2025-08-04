import asyncio
import os

from src.Request_func import get_vacancies_async
from src.data_utils import compare_vacancies, export_vacancies, filter_vacancies
from src.selenium_utils import apply_to_vacancies_parallel_batched

MAX_PARALLEL_ALLOWED = int(os.getenv("MAX_PARALLEL_ALLOWED", 5))


def get_input(prompt, cast, default=None):
    while True:
        val = input(prompt).strip()
        if not val:
            return default
        try:
            return cast(val)
        except (ValueError, TypeError):
            print(f"Неверный ввод. Ожидается значение типа {cast.__name__}.")


def print_menu(menu_type="main"):
    menus = {
        "main": [
            "Выберите действие:",
            "1. Поиск и сохранение новых вакансий",
            "2. Показать все сохраненные вакансии",
            "3. Поиск по ключевому слову",
            "4. Очистить таблицу",
            "5. Фильтрация вакансий",
            "6. Экспорт вакансий",
            "7. Статистика по вакансиям",
            "8. Вход в аккаунт HH (для автоматической рассылки)",
            "9. Отправка отклика и сопроводительного письма для всех сохранённых в БД вакансий",
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
    print("\n" + "\n".join(menus.get(menu_type, [])))


def print_vacancies(vacancies, empty_message="Нет вакансий"):
    if not vacancies:
        print(empty_message)
        return
    for i, v in enumerate(vacancies, 1):
        print(f"\n{i}. {v['vacancy_name']}\n"
              f"   Город: {v['area']}\n"
              f"   Зарплата: {v['salary_from']} - {v['salary_to']}\n"
              f"   Ссылка: {v['url']}")


def print_stats(stats):
    print("\nСтатистика по вакансиям:")
    print(f"Всего вакансий: {stats['total_vacancies']}")
    print(f"Уникальных городов: {stats['unique_cities']}")
    print(f"Средняя зарплата: {stats['avg_salary_from']: .0f} - {stats['avg_salary_to']: .0f}")
    print(f"Максимальная зарплата: {stats['max_salary']}")
    print(f"Минимальная зарплата: {stats['min_salary']}\n")
    print("Топ-5 городов:")
    for city, count in stats['top_cities'].items():
        print(f"  {city}: {count}")


# ==== Обработчики ====

def handle_search_and_save(writer):
    keyword = get_input("Введите ключевое слово для поиска: ", str)
    max_vacancies = get_input("Введите количество вакансий для поиска (По умолчанию 5): ", int, 5)

    print_menu("search_field")
    search_field_choice = get_input("Введите поле поиска (по умолчанию name): ", int, 1)
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
                search_field=search_field_map[search_field_choice],
                order_by=order_by_map[order_by_choice],
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


def handle_show_all(writer):
    print_vacancies(writer.get_all_vacancies(), "Нет сохраненных вакансий")


def handle_search_by_keyword(writer):
    keyword = get_input("Введите ключевое слово для поиска: ", str)
    print_vacancies(writer.get_vacancies_by_keyword(keyword), "Вакансии не найдены")


def handle_filter_vacancies(writer):
    vacancies = writer.get_all_vacancies()
    if not vacancies:
        print("Нет сохраненных вакансий")
        return

    print_menu("filter")
    filtered = filter_vacancies(
        vacancies,
        city=get_input("Введите город: ", str),
        min_salary=get_input("Введите минимальную зарплату: ", int),
        max_salary=get_input("Введите максимальную зарплату: ", int),
    )

    print_vacancies(filtered, "Вакансии не найдены")


def handle_export(writer):
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


def handle_compare_vacancies(writer):
    vacancies = writer.get_all_vacancies()
    if not vacancies:
        print("Нет сохраненных вакансий")
        return

    stats = compare_vacancies(vacancies)
    print_stats(stats)


def get_parallel_driver_count() -> int:
    while True:
        count = get_input(f"Введите число потоков (1–{MAX_PARALLEL_ALLOWED}): ", int)
        if 1 <= count <= MAX_PARALLEL_ALLOWED:
            return count
        print(f"❗ Число должно быть от 1 до {MAX_PARALLEL_ALLOWED}")


def send_apply_to_vacancy(writer):
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
        if count:
            asyncio.run(apply_to_vacancies_parallel_batched(
                vacancies, shadow=shadow, max_parallel_drivers=count))
    else:
        print("❌ Неизвестный выбор.")


def clear_table(writer):
    writer.clear_table()
    print("База данных очищена.")


def exit_program(_=None):
    print("До свидания!")
    exit()
