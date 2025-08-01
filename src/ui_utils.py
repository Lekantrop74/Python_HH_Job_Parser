from src.Request_func import get_vacancies_async
from src.data_utils import compare_vacancies, export_vacancies, filter_vacancies
from src.selenium_utils import apply_to_vacancies_parallel_batched
import asyncio


def print_menu(menu_type="main"):
    """
    Выводит текстовое меню на экран в зависимости от типа.
    :param menu_type: Строка, указывающая тип меню ('main', 'filter', 'export')
    """
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


def print_vacancy(vacancy, index=None):
    """
    Выводит информацию об одной вакансии в читаемом виде.
    :param vacancy: Словарь с данными о вакансии
    :param index: Порядковый номер (опционально)
    """
    if index is not None:
        print(f"\n{index}. {vacancy['vacancy_name']}")
    else:
        print(f"\n{vacancy['vacancy_name']}")
    print(f"   Город: {vacancy['area']}")
    print(f"   Зарплата: {vacancy['salary_from']} - {vacancy['salary_to']}")
    print(f"   Ссылка: {vacancy['url']}")


def print_vacancies(vacancies, empty_message):
    """
    Выводит список вакансий или сообщение, если список пустой.
    :param vacancies: Список словарей с вакансиями
    :param empty_message: Сообщение, если вакансий нет
    """
    if vacancies:
        for i, vacancy in enumerate(vacancies, 1):
            print_vacancy(vacancy, i)
    else:
        print(empty_message)


def print_stats(stats):
    """
    Выводит сводную статистику по вакансиям.
    :param stats: Словарь со статистикой (кол-во, города, зарплаты)
    """
    print("\nСтатистика по вакансиям:")
    print(f"Всего вакансий: {stats['total_vacancies']}")
    print(f"Уникальных городов: {stats['unique_cities']}")
    print(f"Средняя зарплата: {stats['avg_salary_from']: .0f} - {stats['avg_salary_to']: .0f}")
    print(f"Максимальная зарплата: {stats['max_salary']}")
    print(f"Минимальная зарплата: {stats['min_salary']}")

    print("\nТоп-5 городов:")
    for city, count in stats['top_cities'].items():
        print(f"  {city}: {count}")


# ==== Обработчики меню ====

def handle_search_and_save(writer):
    """
    Выполняет поиск вакансий по ключевому слову и сохраняет их в базу данных.
    :param writer: Экземпляр класса работы с БД
    """
    keyword = input("Введите ключевое слово для поиска: ")
    max_vacancies_input = input("Введите количество вакансий для поиска (По умолчанию 5): ")

    if max_vacancies_input.strip().isdigit():
        max_vacancies_input = int(max_vacancies_input)
    else:
        max_vacancies_input = 5

    vacancies, _ = asyncio.run(get_vacancies_async(keyword, max_vacancies_input))

    writer.create_table()
    writer.clear_table()
    writer.write_data(vacancies)

    print(f"\nНайдено и сохранено {len(vacancies)} вакансий")


def handle_show_all(writer):
    """
    Показывает все сохраненные вакансии.
    :param writer: Экземпляр класса работы с БД
    """
    vacancies = writer.get_all_vacancies()
    print_vacancies(vacancies, "Нет сохраненных вакансий")


def handle_search_by_keyword(writer):
    """
    Производит поиск вакансий по ключевому слову в сохраненной базе.
    :param writer: Экземпляр класса работы с БД
    """
    keyword = input("Введите ключевое слово для поиска: ")
    vacancies = writer.get_vacancies_by_keyword(keyword)
    print_vacancies(vacancies, "Вакансии не найдены")


def handle_filter_vacancies(writer):
    """
    Применяет фильтрацию по городу и уровню зарплаты.
    :param writer: Экземпляр класса работы с БД
    """
    vacancies = writer.get_all_vacancies()
    if not vacancies:
        print("Нет сохраненных вакансий")
        return

    print_menu("filter")
    city = input("Введите город: ").strip()
    min_salary = input("Введите минимальную зарплату: ").strip()
    max_salary = input("Введите максимальную зарплату: ").strip()

    filtered = filter_vacancies(
        vacancies,
        city=city or None,
        min_salary=int(min_salary) if min_salary else None,
        max_salary=int(max_salary) if max_salary else None,
    )

    print_vacancies(filtered, "Вакансии не найдены")


def handle_export(writer):
    """
    Выполняет экспорт вакансий в выбранный формат.
    :param writer: Экземпляр класса работы с БД
    """
    vacancies = writer.get_all_vacancies()
    if not vacancies:
        print("Нет сохраненных вакансий")
        return

    print_menu("export")
    formats = {"1": "csv", "2": "xlsx"}
    file_format = formats.get(input("Введите номер формата: "), None)

    if file_format:
        filename = export_vacancies(vacancies, file_format=file_format)
        print(f"Данные экспортированы в файл: {filename}")
    else:
        print("Неверный выбор формата")


def handle_compare_vacancies(writer):
    """
    Выводит статистику и сравнение по всем сохраненным вакансиям.
    :param writer: Экземпляр класса работы с БД
    """
    vacancies = writer.get_all_vacancies()
    if not vacancies:
        print("Нет сохраненных вакансий")
        return

    stats = compare_vacancies(vacancies)
    print_stats(stats)


def send_apply_to_vacancy(writer):
    """
    Запускает автоматическую отправку откликов на все вакансии.
    :param writer: Экземпляр класса работы с БД
    """
    vacancies = writer.get_all_vacancies()
    asyncio.run(apply_to_vacancies_parallel_batched(vacancies))

    # apply_to_vacancy(vacancies)



def clear_table(writer):
    """
    Очищает таблицу вакансий в базе данных.
    :param writer: Экземпляр класса работы с БД
    """
    writer.clear_table()
    print(f"\nБаза данных отчищена")


def exit_program(writer=None):
    """
    Завершает выполнение программы.
    :param writer: Опционально принимает writer, если нужно освободить ресурсы
    """
    print("До свидания!")
    exit()
