import asyncio
import re
import aiohttp
from tqdm.asyncio import tqdm_asyncio

MAX_CONCURRENT_REQUESTS = 10
REQUEST_TIMEOUT = 10
PER_PAGE = 100
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


def clean_html(raw_html):
    clean_text = re.sub(r'<br>', '\n', raw_html)
    clean_text = re.sub(r'<[^>]+>', '', clean_text)
    clean_text = re.sub(r'&[^;]+;', ' ', clean_text)
    clean_text = re.sub(r'\n+', '\n', clean_text).strip()
    return clean_text


async def fetch_details(session, vacancy_id):
    async with semaphore:
        async with session.get(f"https://api.hh.ru/vacancies/{vacancy_id}") as resp:
            return await resp.json()


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


async def get_vacancies_async(keyword, max_vacancies, show_progress=True):
    url = "https://api.hh.ru/vacancies"
    page = 0
    data = []

    headers = {"User-Agent": "my-hh-bot"}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, params={"text": keyword, "search_field": "name", "per_page": 1, "page": 0}) as resp:
            if resp.status != 200:
                print("Ошибка запроса")
                return [], 0
            total_found = (await resp.json())["found"]

        while len(data) < max_vacancies and page * PER_PAGE < total_found:
            params = {
                "text": keyword,
                "search_field": "name",
                "order_by": "publication_time",
                "per_page": PER_PAGE,
                "page": page
            }

            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    print("Ошибка страницы", page)
                    break
                vacancies = (await resp.json())["items"]

            limit = min(max_vacancies - len(data), len(vacancies))
            ids = [v["id"] for v in vacancies[:limit]]

            fetcher = tqdm_asyncio.gather if show_progress else asyncio.gather
            details = await fetcher(*[fetch_details(session, vid) for vid in ids], desc=f"Страница {page + 1}",
                                    ncols=80)

            for vacancy, detail in zip(vacancies, details):
                if not detail:
                    continue
                data.append(parse_vacancy(vacancy, detail))
                if len(data) >= max_vacancies:
                    break

            page += 1

    print(f"Загружено {len(data)} из {total_found}")
    return data, total_found
