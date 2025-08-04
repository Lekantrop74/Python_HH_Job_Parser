import sqlite3
from pathlib import Path


class DBVacanciesManager:
    def __init__(self, db_path="vacancies.db"):
        self.db_path = Path(db_path)

    def connect(self):
        return sqlite3.connect(self.db_path.as_posix())

    @staticmethod
    def map_to_dict(keys, rows):
        return [dict(zip(keys, row)) for row in rows]

    def create_table(self):
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS vacancies (
                id INTEGER PRIMARY KEY,
                name TEXT,
                url TEXT,
                salary_from INTEGER,
                salary_to INTEGER,
                area TEXT,
                description TEXT
            );
        """)
        print("Таблица vacancies успешно создана.")

    def clear_table(self):
        self.execute_query("DELETE FROM vacancies;")
        print("Таблица vacancies очищена.")

    def write_data(self, data):
        query = """
            INSERT OR IGNORE INTO vacancies 
            (id, name, url, salary_from, salary_to, area, description)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        data_tuples = list(map(lambda v: (
            v["id"], v["name"], v["url"], v["salary_from"],
            v["salary_to"], v["area"], v["description"]
        ), data))

        self.execute_query(query, data_tuples, executemany=True)
        print("Данные успешно записаны в базу данных.")

    def get_all_vacancies(self):
        rows = self.execute_query(
            "SELECT id, name, salary_from, salary_to, url, area, description FROM vacancies;",
            fetch_all=True
        )
        keys = ["id", "vacancy_name", "salary_from", "salary_to", "url", "area", "description"]
        return self.map_to_dict(keys, rows)

    def get_vacancies_by_keyword(self, keyword):
        rows = self.execute_query(
            """
            SELECT id, name, salary_from, salary_to, area, url
            FROM vacancies
            WHERE LOWER(name) LIKE LOWER(?);
            """,
            (f"%{keyword}%",),
            fetch_all=True
        )
        keys = ["id", "vacancy_name", "salary_from", "salary_to", "area", "url"]
        return self.map_to_dict(keys, rows)

    def execute_query(self, query, data=None, fetch_all=False, executemany=False):
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
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS processed_urls (
                id INTEGER PRIMARY KEY
            );
        """)
        print("Таблица processed_urls успешно создана.")

    def insert_processed_id(self, vacancy_id):
        self.execute_query(
            "INSERT OR IGNORE INTO processed_urls (id) VALUES (?);",
            (vacancy_id,)
        )

    def insert_processed_ids_bulk(self, ids):
        self.execute_query(
            "INSERT OR IGNORE INTO processed_urls (id) VALUES (?);",
            [(vid,) for vid in ids],
            executemany=True
        )

    def is_id_processed(self, vacancy_id):
        result = self.execute_query(
            "SELECT 1 FROM processed_urls WHERE id = ?;",
            (vacancy_id,),
            fetch_all=True
        )
        return bool(result)

    def get_all_processed_ids(self):
        rows = self.execute_query("SELECT id FROM processed_urls;", fetch_all=True)
        return set(row[0] for row in rows)
