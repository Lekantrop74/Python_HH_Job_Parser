import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional


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
        'Ссылка': f"https://hh.ru/vacancy/{v['id']}"
    } for v in vacancies])

    # Сохраняем файл в нужном формате
    if file_format == "csv":
        df.to_csv(filename, index=False, encoding='utf-8-sig')
    else:
        df.to_excel(filename, index=False)

    return filename
