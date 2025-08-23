"""
Модуль для асинхронного парсинга вакансий с сайта HeadHunter.

Этот модуль предоставляет функциональность для:
- Асинхронного получения вакансий через API HH.ru
- Фильтрации вакансий по требуемым навыкам
- Обработки HTML-контента
- Управления ограничениями запросов и капчей
- Интеграции с базой данных для отслеживания обработанных вакансий

Основные компоненты:
- Settings: Конфигурация параметров запросов
- HHClient: Клиент для работы с API HH.ru
- Утилиты для обработки данных
- Основная функция get_vacancies_async
"""

import asyncio
import os
import re
import logging
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass

import aiohttp
from dotenv import load_dotenv
from tqdm.asyncio import tqdm_asyncio

from src.DBManager import DBVacanciesManager

# === Настройки ===
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """
    Конфигурация параметров для работы с API HH.ru.
    
    Атрибуты:
        max_concurrent (int): Максимальное количество одновременных запросов
        request_timeout (float): Задержка между запросами в секундах
        per_page (int): Количество вакансий на страницу
    """
    max_concurrent: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", 1))
    request_timeout: float = int(os.getenv("REQUEST_TIMEOUT", 0)) / 100
    per_page: int = int(os.getenv("PER_PAGE", 100))


settings = Settings()

# === Логирование ===
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Семафор для ограничения количества одновременных запросов
semaphore = asyncio.Semaphore(settings.max_concurrent)


class CaptchaRequired(Exception):
    """
    Исключение, возникающее когда антибот-система HH.ru требует капчу.
    
    Выбрасывается при получении HTTP 403 с сообщением о необходимости капчи.
    """
    pass


# === Утилиты ===
def clean_html(raw_html: str) -> str:
    """
    Очищает HTML-контент от тегов и спецсимволов.
    
    Args:
        raw_html (str): Сырой HTML-текст
        
    Returns:
        str: Очищенный текст без HTML-тегов
        
    Пример:
        >>> clean_html("<p>Python<br>developer</p>")
        'Python\ndeveloper'
    """
    # Заменяем <br> теги на переносы строк
    text = re.sub(r'<br\s*/?>', '\n', raw_html)
    # Удаляем все HTML-теги
    text = re.sub(r'<[^>]+>', '', text)
    # Заменяем HTML-сущности на пробелы
    text = re.sub(r'&[^;]+;', ' ', text)
    # Убираем лишние переносы строк
    return re.sub(r'\n+', '\n', text).strip()


def parse_vacancy(vacancy: Dict, detail: Optional[Dict] = None) -> Dict:
    """
    Парсит вакансию в стандартный формат.
    
    Args:
        vacancy (Dict): Основные данные вакансии из списка
        detail (Optional[Dict]): Детальная информация о вакансии
        
    Returns:
        Dict: Стандартизированная вакансия с полями:
            - id: ID вакансии
            - name: Название вакансии
            - description: Очищенное описание
    """
    description = detail.get("description") if detail else None
    return {
        "id": vacancy["id"],
        "name": vacancy["name"],
        "description": clean_html(description or "Описание отсутствует"),
    }


def has_required_skills(detail: Dict, required_skills: List[str]) -> bool:
    """
    Проверяет наличие требуемых навыков в вакансии.
    
    Args:
        detail (Dict): Детальная информация о вакансии
        required_skills (List[str]): Список требуемых навыков
        
    Returns:
        bool: True если все требуемые навыки присутствуют
        
    Пример:
        detail = {"key_skills": [{"name": "Python"}, {"name": "SQL"}]}
        has_required_skills(detail, ["python", "sql"])
        True
    """
    # Получаем навыки из вакансии (приводим к нижнему регистру)
    skills = {skill['name'].lower() for skill in detail.get("key_skills", [])}
    # Проверяем наличие всех требуемых навыков
    return all(skill.lower() in skills for skill in required_skills)


def build_params(keyword: str, search_field: str, page: int, per_page: int, order_by: Optional[str] = None) -> Dict:
    """
    Строит параметры запроса к API HH.ru.
    
    Args:
        keyword (str): Поисковый запрос
        search_field (str): Поле поиска (name, description, company_name)
        page (int): Номер страницы
        per_page (int): Количество вакансий на страницу
        order_by (Optional[str]): Сортировка (publication_time, salary_desc, etc.)
        
    Returns:
        Dict: Параметры для HTTP-запроса
    """
    params = {
        "text": keyword,
        "search_field": search_field,
        "per_page": per_page,
        "page": page,
    }
    if order_by:
        params["order_by"] = order_by
    return params


# === API-клиент ===
class HHClient:
    """
    Клиент для работы с API HeadHunter.
    
    Предоставляет методы для:
    - Получения списка вакансий
    - Загрузки детальной информации о вакансиях
    - Обработки ошибок и капчи
    """

    BASE_URL = "https://api.hh.ru/vacancies"

    def __init__(self, session: aiohttp.ClientSession):
        """
        Инициализирует клиент с HTTP-сессией.
        
        Args:
            session (aiohttp.ClientSession): HTTP-сессия для запросов
        """
        self.session = session

    async def fetch_details(self, vacancy_id: str) -> Optional[Dict]:
        """
        Загружает детальную информацию о вакансии.
        
        Args:
            vacancy_id (str): ID вакансии
            
        Returns:
            Optional[Dict]: Детальная информация или None при ошибке
            
        Raises:
            CaptchaRequired: Если требуется капча
        """
        async with semaphore:  # Ограничиваем количество одновременных запросов
            await asyncio.sleep(settings.request_timeout)  # Задержка между запросами
            async with self.session.get(f"{self.BASE_URL}/{vacancy_id}") as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status == 403 and "captcha_required" in await resp.text():
                    raise CaptchaRequired

    async def get_total_count(self, keyword: str, search_field: str, order_by: Optional[str] = None) -> int:
        """
        Получает общее количество вакансий по запросу.
        
        Args:
            keyword (str): Поисковый запрос
            search_field (str): Поле поиска
            order_by (Optional[str]): Сортировка
            
        Returns:
            int: Общее количество найденных вакансий
        """
        params = build_params(keyword, search_field, 0, 1, order_by)
        async with self.session.get(self.BASE_URL, params=params) as resp:
            if resp.status != 200:
                logger.error(f"Ошибка запроса общего количества вакансий: {resp.status}")
                return 0
            data = await resp.json()
            return data.get("found", 0)

    async def fetch_page(self, keyword: str, search_field: str, page: int, order_by: Optional[str] = None) -> List[
        Dict]:
        """
        Загружает страницу вакансий.
        
        Args:
            keyword (str): Поисковый запрос
            search_field (str): Поле поиска
            page (int): Номер страницы
            order_by (Optional[str]): Сортировка
            
        Returns:
            List[Dict]: Список вакансий на странице
        """
        params = build_params(keyword, search_field, page, settings.per_page, order_by)
        async with self.session.get(self.BASE_URL, params=params) as resp:
            if resp.status != 200:
                logger.error(f"Ошибка загрузки страницы {page}: {resp.status}")
                return []
            data = await resp.json()
            return data.get("items", [])

    async def fetch_details_batch(self, vacancies: List[Dict], show_progress: bool = True) -> List[Optional[Dict]]:
        """
        Загружает детальную информацию для списка вакансий.
        
        Args:
            vacancies (List[Dict]): Список вакансий
            show_progress (bool): Показывать прогресс-бар
            
        Returns:
            List[Optional[Dict]]: Список детальной информации
        """
        ids = [v["id"] for v in vacancies]
        # Выбираем метод сбора результатов в зависимости от настроек прогресса
        fetcher = tqdm_asyncio.gather if show_progress else asyncio.gather
        return await fetcher(*(self.fetch_details(vid) for vid in ids),
                             desc="Загрузка деталей", ncols=80)


# === Основная функция ===
async def get_vacancies_async(
        keyword: str,
        max_vacancies: int,
        search_field: str,
        order_by: Optional[str] = None,
        required_skills: Optional[List[str]] = None,
        show_progress: bool = True,
) -> Tuple[List[Dict], int]:
    """
    Основная функция для получения вакансий с фильтрацией.
    
    Функция выполняет следующие действия:
    1. Подключается к базе данных для отслеживания обработанных вакансий
    2. Получает общее количество вакансий по запросу
    3. Постранично загружает вакансии
    4. Фильтрует уже обработанные вакансии
    5. При необходимости загружает детальную информацию и фильтрует по навыкам
    6. Возвращает результат и общее количество найденных вакансий
    
    Args:
        keyword (str): Поисковый запрос
        max_vacancies (int): Максимальное количество вакансий для загрузки
        search_field (str): Поле поиска (name, description, company_name)
        order_by (Optional[str]): Сортировка результатов
        required_skills (Optional[List[str]]): Список требуемых навыков для фильтрации
        show_progress (bool): Показывать прогресс-бар
        
    Returns:
        Tuple[List[Dict], int]: (список вакансий, общее количество найденных)
        
    Raises:
        CaptchaRequired: Если HH.ru требует капчу
        
    Пример:
        vacancies, total = await get_vacancies_async(
        ...     keyword="Python developer",
        ...     max_vacancies=10,
        ...     search_field="name",
        ...     required_skills=["python", "sql"]
        ... )
    """
    data: List[Dict] = []

    # Инициализируем базу данных для отслеживания обработанных вакансий
    db = DBVacanciesManager()
    db.create_processed_urls_table()
    seen_ids = set(db.get_all_processed_ids())

    async with aiohttp.ClientSession(headers={"User-Agent": "my-hh-bot"}) as session:
        client = HHClient(session)

        # Получаем общее количество вакансий
        total_found = await client.get_total_count(keyword, search_field, order_by)
        logger.info(f"Всего найдено: {total_found}")

        page = 0
        prev_count = 0
        processed_count = 0

        # Постранично загружаем вакансии
        while len(data) < max_vacancies and page * settings.per_page < total_found:
            # Загружаем страницу вакансий
            vacancies = await client.fetch_page(keyword, search_field, page, order_by)
            processed_count += len(vacancies)

            # Фильтруем уже обработанные вакансии
            vacancies = [v for v in vacancies if int(v["id"]) not in seen_ids]

            exclude_words = {"преподава", "репетитор", "педагог", "учите", "аналитик", "c#", "c++", "frontend"}

            vacancies = [
                v for v in vacancies
                if not any(word in v["name"].lower() for word in exclude_words)
            ]

            if required_skills:
                # Если указаны требуемые навыки, загружаем детальную информацию
                try:
                    details = await client.fetch_details_batch(vacancies, show_progress)
                except CaptchaRequired:
                    logger.error("🔒 Требуется капча. Завершаем выполнение.")
                    break

                # Фильтруем вакансии по требуемым навыкам
                filtered = (
                    parse_vacancy(vac, det)
                    for vac, det in zip(vacancies, details)
                    if det and has_required_skills(det, required_skills)
                )
                data.extend(filtered)
            else:
                # Если навыки не указаны, добавляем все вакансии
                data.extend(parse_vacancy(v) for v in vacancies)

            # Логируем прогресс
            logger.info(
                f"✅ Добавлено: {len(data) - prev_count}, "
                f"Всего: {len(data)} / {max_vacancies} | "
                f"Обработано: {processed_count} из {total_found}"
            )
            prev_count = len(data)
            page += 1

    print(f"Загружено {len(data)} из {total_found}")
    return data[:max_vacancies], total_found
