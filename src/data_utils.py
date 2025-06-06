import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from configparser import ConfigParser


def config(filename="database.ini", section="postgresql") -> dict:
    """
    Получить конфигурацию для подключения к базе данных
    :param filename: имя файла конфигурации
    :param section: имя секции в файле конфигурации
    :return: словарь с параметрами подключения
    """
    parser = ConfigParser()  # Создаём объект для парсинга конфигурационного файла
    parser.read(filename)  # Читаем файл конфигурации

    if parser.has_section(section):  # Проверяем, есть ли нужная секция в файле
        return dict(parser.items(section))  # Преобразуем параметры подключения в словарь и возвращаем
    else:
        raise Exception(  # Вызываем исключение, если секция не найдена
            f"Секция '{section}' не найдена в файле '{filename}'."
        )


def export_vacancies(vacancies: List[Dict], file_format: str = "csv", filename: Optional[str] = None) -> str:
    """
    Экспортирует вакансии в CSV или Excel файл.

    Аргументы:
    - vacancies: список словарей с вакансиями
    - file_format: 'csv' или 'xlsx' (по умолчанию 'csv')
    - filename: имя файла (если не указано, будет сгенерировано автоматически)

    Возвращает:
    - str: путь к созданному файлу
    """
    if file_format not in ["csv", "xlsx"]:
        raise ValueError("Неверный формат файла. Используйте 'csv' или 'xlsx'.")

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"vacancies_{timestamp}.{file_format}"

    # Преобразуем данные в формат DataFrame
    df = pd.DataFrame([{
        'Название вакансии': v['vacancy_name'],
        'Город': v['area'],
        'Зарплата от': v['salary_from'],
        'Зарплата до': v['salary_to'],
        'Ссылка': v['url']
    } for v in vacancies])

    # Сохраняем файл в нужном формате
    if file_format == "csv":
        df.to_csv(filename, index=False, encoding='utf-8-sig')
    else:
        df.to_excel(filename, index=False)

    return filename


def filter_vacancies(vacancies: List[Dict],
                     city: Optional[str] = None,
                     min_salary: Optional[int] = None,
                     max_salary: Optional[int] = None) -> List[Dict]:
    """
    Фильтрует вакансии по заданным параметрам.
    """
    return [
        v for v in vacancies
        if (not city or v['area'].lower() == city.lower()) and
           (min_salary is None or (v['salary_from'] and v['salary_from'] >= min_salary)) and
           (max_salary is None or (v['salary_to'] and v['salary_to'] <= max_salary))
    ]


def compare_vacancies(vacancies: List[Dict]) -> Dict:
    """
    Сравнивает вакансии и возвращает статистику.
    """
    if not vacancies:
        return {}

    df = pd.DataFrame(vacancies).dropna(subset=['salary_from', 'salary_to'])

    return {
        'total_vacancies': len(vacancies),
        'unique_cities': df['area'].nunique(),
        'avg_salary_from': df['salary_from'].mean(),
        'avg_salary_to': df['salary_to'].mean(),
        'max_salary': df['salary_to'].max(),
        'min_salary': df['salary_from'].min(),
        'top_cities': df['area'].value_counts().head(5).to_dict(),
    }
