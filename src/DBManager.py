"""
Модуль для управления вакансиями в SQLite.

Функционал:
- Создание и очистка таблиц вакансий.
- Запись, получение и поиск вакансий.
- Учёт уже обработанных вакансий (processed_urls).
"""

import sqlite3
from pathlib import Path


class DBVacanciesManager:
    """
    Менеджер для работы с базой данных SQLite (вакансии и обработанные ID).
    """

    def __init__(self, db_path="vacancies.db"):
        """
        Args:
            db_path (str): Путь к файлу базы данных.
        """
        self.db_path = Path(db_path)

    def connect(self):
        """Создаёт подключение к базе данных SQLite."""
        return sqlite3.connect(self.db_path.as_posix())

    @staticmethod
    def map_to_dict(keys, rows):
        """Преобразует список кортежей в список словарей по ключам."""
        return [dict(zip(keys, row)) for row in rows]

    def create_table(self):
        """Создаёт таблицу vacancies, если она не существует."""
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS vacancies (
                id INTEGER PRIMARY KEY,
                name TEXT,
                description TEXT
            );
        """)
        print("Таблица vacancies успешно создана.")

    def clear_table(self):
        """Очищает таблицу vacancies."""
        self.execute_query("DELETE FROM vacancies;")
        print("Таблица vacancies очищена.")

    def write_data(self, data):
        """
        Записывает вакансии в таблицу vacancies.

        Args:
            data (list[dict]): Список вакансий с ключами id, name, description.
        """
        query = """
            INSERT OR IGNORE INTO vacancies 
            (id, name, description)
            VALUES (?, ?, ?);
        """
        data_tuples = list(map(lambda v: (
            v["id"], v["name"], v["description"]
        ), data))

        self.execute_query(query, data_tuples, executemany=True)
        print("Данные успешно записаны в базу данных.")

    def get_all_vacancies(self):
        """Возвращает все вакансии в виде списка словарей."""
        rows = self.execute_query(
            "SELECT id, name, description FROM vacancies;",
            fetch_all=True
        )
        keys = ["id", "vacancy_name", "description"]
        return self.map_to_dict(keys, rows)

    def get_vacancies_by_keyword(self, keyword):
        """
        Ищет вакансии по ключевому слову в названии.

        Args:
            keyword (str): Ключевое слово для поиска.

        Returns:
            list[dict]: Найденные вакансии.
        """
        rows = self.execute_query(
            """
            SELECT id, name
            FROM vacancies
            WHERE LOWER(name) LIKE LOWER(?);
            """,
            (f"%{keyword}%",),
            fetch_all=True
        )
        keys = ["id", "vacancy_name"]
        return self.map_to_dict(keys, rows)

    def execute_query(self, query, data=None, fetch_all=False, executemany=False):
        """
        Выполняет SQL-запрос.

        Args:
            query (str): SQL-запрос.
            data: Данные для подстановки в запрос.
            fetch_all (bool): Вернуть ли все строки результата.
            executemany (bool): Выполнить ли executemany.

        Returns:
            list | None: Результаты запроса или None.
        """
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                if data:
                    (cursor.executemany if executemany else cursor.execute)(query, data)
                else:
                    cursor.execute(query)

                if fetch_all:
                    return cursor.fetchall()

                conn.commit()
        except sqlite3.Error as e:
            print(f"SQLite ошибка: {e}")
            return [] if fetch_all else None

    def create_processed_urls_table(self):
        """Создаёт таблицу processed_urls для хранения ID обработанных вакансий."""
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS processed_urls (
                id INTEGER PRIMARY KEY
            );
        """)
        print("Таблица processed_urls успешно создана.")

    def insert_processed_id(self, vacancy_id):
        """Добавляет один обработанный ID в таблицу processed_urls."""
        self.execute_query(
            "INSERT OR IGNORE INTO processed_urls (id) VALUES (?);",
            (vacancy_id,)
        )

    def insert_processed_ids_bulk(self, ids):
        """Добавляет несколько обработанных ID в таблицу processed_urls."""
        self.execute_query(
            "INSERT OR IGNORE INTO processed_urls (id) VALUES (?);",
            [(vid,) for vid in ids],
            executemany=True
        )

    def is_id_processed(self, vacancy_id):
        """
        Проверяет, есть ли вакансия с данным ID в processed_urls.

        Args:
            vacancy_id (int): ID вакансии.

        Returns:
            bool: True, если ID уже обработан.
        """
        result = self.execute_query(
            "SELECT 1 FROM processed_urls WHERE id = ?;",
            (vacancy_id,),
            fetch_all=True
        )
        return bool(result)

    def get_all_processed_ids(self):
        """Возвращает множество всех обработанных ID."""
        rows = self.execute_query("SELECT id FROM processed_urls;", fetch_all=True)
        return set(row[0] for row in rows)
