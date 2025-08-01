import asyncio
from src.Request_func import get_vacancies_async
from src.data_utils import compare_vacancies, export_vacancies, filter_vacancies
from src.selenium_utils import apply_to_vacancies_parallel_batched


def get_input(prompt, default=None, cast=str):
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
        ]
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
    keyword = get_input("Введите ключевое слово для поиска: ")
    max_vacancies = get_input("Введите количество вакансий для поиска (По умолчанию 5): ", default=5, cast=int)

    try:
        vacancies, _ = asyncio.run(get_vacancies_async(keyword, max_vacancies))
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
    keyword = get_input("Введите ключевое слово для поиска: ")
    print_vacancies(writer.get_vacancies_by_keyword(keyword), "Вакансии не найдены")


def handle_filter_vacancies(writer):
    vacancies = writer.get_all_vacancies()
    if not vacancies:
        print("Нет сохраненных вакансий")
        return

    print_menu("filter")
    filtered = filter_vacancies(
        vacancies,
        city=get_input("Введите город: "),
        min_salary=get_input("Введите минимальную зарплату: ", cast=int),
        max_salary=get_input("Введите максимальную зарплату: ", cast=int),
    )

    print_vacancies(filtered, "Вакансии не найдены")


def handle_export(writer):
    vacancies = writer.get_all_vacancies()
    if not vacancies:
        print("Нет сохраненных вакансий")
        return

    print_menu("export")
    formats = {"1": "csv", "2": "xlsx"}
    choice = get_input("Введите номер формата: ", cast=str)
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


def send_apply_to_vacancy(writer):
    vacancies = writer.get_all_vacancies()
    if vacancies:
        asyncio.run(apply_to_vacancies_parallel_batched(vacancies))
    else:
        print("Нет вакансий для отклика.")


def clear_table(writer):
    writer.clear_table()
    print("База данных очищена.")


def exit_program(_=None):
    print("До свидания!")
    exit()
