import asyncio
import re
import aiohttp
from tqdm.asyncio import tqdm_asyncio

MAX_CONCURRENT_REQUESTS = 10
REQUEST_TIMEOUT = 10
PER_PAGE = 100
HEADERS = {"User-Agent": "my-hh-bot"}
BASE_URL = "https://api.hh.ru"

semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


def clean_html(raw_html):
    return re.sub(r'(\s*<br\s*/?>\s*|<[^>]+>|&[^;]+;)', lambda m: '\n' if '<br' in m.group() else ' ', raw_html).strip()


async def fetch_json(session, url):
    async with semaphore:
        async with session.get(url) as resp:
            return await resp.json() if resp.status == 200 else None


def parse_vacancy(vac, detail):
    salary = vac.get("salary") or {}
    return {
        "id": vac["id"],
        "name": vac["name"],
        "url": vac["alternate_url"],
        "salary_from": salary.get("from"),
        "salary_to": salary.get("to"),
        "area": vac["area"]["name"],
        "description": clean_html(detail.get("description", ""))
    }


async def get_vacancies_async(keyword, max_vacancies, show_progress=True):
    search_url = f"{BASE_URL}/vacancies"
    data, page = [], 0

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        initial = await fetch_json(session, f"{search_url}?text={keyword}&search_field=name&per_page=1&page=0")
        if not initial:
            print("Ошибка запроса")
            return [], 0

        total_found = initial["found"]

        while len(data) < max_vacancies and page * PER_PAGE < total_found:
            params = {
                "text": keyword,
                "search_field": "name",
                "order_by": "publication_time",
                "per_page": PER_PAGE,
                "page": page
            }

            resp = await fetch_json(session, f"{search_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}")
            if not resp:
                print("Ошибка страницы", page)
                break

            vacancies = resp["items"][:max_vacancies - len(data)]
            ids = [v["id"] for v in vacancies]
            fetcher = tqdm_asyncio.gather if show_progress else asyncio.gather
            details = await fetcher(*[fetch_json(session, f"{search_url}/{vid}") for vid in ids],
                                    desc=f"Страница {page + 1}", ncols=80)

            data.extend(parse_vacancy(v, d) for v, d in zip(vacancies, details) if d)
            page += 1

    print(f"Загружено {len(data)} из {total_found}")
    return data, total_found
