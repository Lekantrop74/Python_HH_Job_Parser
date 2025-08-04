import asyncio
import os
import re
import sys

import aiohttp
from dotenv import load_dotenv
from tqdm.asyncio import tqdm_asyncio

from src.DBManager import DBVacanciesManager

load_dotenv()
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 1))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 0))
PER_PAGE = int(os.getenv("PER_PAGE", 100))

semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


def clean_html(raw_html):
    clean_text = re.sub(r'<br>', '\n', raw_html)
    clean_text = re.sub(r'<[^>]+>', '', clean_text)
    clean_text = re.sub(r'&[^;]+;', ' ', clean_text)
    clean_text = re.sub(r'\n+', '\n', clean_text).strip()
    return clean_text


async def fetch_details(session, vacancy_id):
    async with semaphore:
        await asyncio.sleep(REQUEST_TIMEOUT / 100)  # Задержка в мс перед каждым запросом

        async with session.get(f"https://api.hh.ru/vacancies/{vacancy_id}") as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status == 403:
                text = await resp.text()
                if "captcha_required" in text:
                    return None


def parse_vacancy(vacancy, detail):
    salary = vacancy.get("salary") or {}
    return {
        "id": vacancy["id"],
        "name": vacancy["name"],
        "url": vacancy["alternate_url"],
        "salary_from": salary.get("from"),
        "salary_to": salary.get("to"),
        "area": vacancy["area"]["name"],
        "description": clean_html(detail.get("description", "Описание отсутствует")),
    }


def has_required_skills(detail, required_skills):
    skills = {s['name'].lower() for s in detail.get("key_skills", [])}
    return all(skill.lower() in skills for skill in required_skills)


async def get_vacancies_async(keyword, max_vacancies, search_field, order_by=None,
                              required_skills=None, show_progress=True):
    url = "https://api.hh.ru/vacancies"
    page = 0
    data = []

    headers = {"User-Agent": "my-hh-bot"}
    init_params = {
        "text": keyword,
        "search_field": search_field,
        "per_page": 1,
        "page": 0
    }
    if order_by:
        init_params["order_by"] = order_by

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, params=init_params) as resp:
            if resp.status != 200:
                print("Ошибка запроса")
                return [], 0
            total_found = (await resp.json())["found"]

        prev_count = 0  # до while
        print(f"Всего найдено: {total_found}")

        db = DBVacanciesManager()
        db.create_processed_urls_table()
        seen_urls = db.get_all_processed_ids()
        print(seen_urls)

        while len(data) < max_vacancies and page * PER_PAGE < total_found:
            params = {
                "text": keyword,
                "search_field": search_field,
                "per_page": PER_PAGE,
                "page": page
            }
            if order_by:
                params["order_by"] = order_by

            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    print("Ошибка страницы", page)
                    break
                vacancies = (await resp.json())["items"]

            if required_skills:
                ids = [v["id"] for v in vacancies]  # обрабатываем всё
            else:
                limit = min(max_vacancies - len(data), len(vacancies))
                vacancies = vacancies[:limit]
                ids = [v["id"] for v in vacancies]

            fetcher = tqdm_asyncio.gather if show_progress else asyncio.gather
            details = await fetcher(*[fetch_details(session, vid) for vid in ids], desc=f"Страница {page + 1}",
                                    ncols=80)

            for vacancy, detail in zip(vacancies, details):
                if not detail:
                    print(f"\n🔒 Требуется капча. Завершаем выполнение."
                          f"\nСлишком много быстрых запросов сработала антибот система")
                    sys.exit(0)
                if required_skills and not has_required_skills(detail, required_skills):
                    continue
                if vacancy["id"] in seen_urls:
                    continue
                data.append(parse_vacancy(vacancy, detail))
                if len(data) >= max_vacancies:
                    break

            added = len(data) - prev_count
            print(f"✅ Добавлено: {added}, всего: {len(data)} / {max_vacancies}")
            prev_count = len(data)

            page += 1

    print(f"Загружено {len(data)} из {total_found}")
    return data, total_found
