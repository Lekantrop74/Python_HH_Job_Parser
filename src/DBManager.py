import psycopg2
from src.data_utils import config


class DBVacanciesManager:
    """
    Класс для управления базой данных PostgresSQL, содержащей вакансии.
    Поддерживает подключение, создание таблицы, очистку, вставку и выборку данных.
    """

    def __init__(self, filename="database.ini", section="postgresql"):
        """
        Инициализация параметров подключения к базе данных из конфигурационного файла.

        :param filename: Имя файла конфигурации.
        :param section: Название секции в файле конфигурации.
        """
        self.connection_params = config(filename, section)

    def connect(self):
        """
        Создаёт и возвращает новое подключение к базе данных.

        :return: Объект подключения psycopg2.
        """
        return psycopg2.connect(**self.connection_params)

    # =============== УПРАВЛЕНИЕ СТРУКТУРОЙ ТАБЛИЦЫ ===============

    def create_table(self):
        """
        Создаёт таблицу 'vacancies', если она ещё не существует.
        Структура таблицы включает ID, название, зарплату, регион и описание.
        """
        # Проверяем существование таблицы через information_schema
        if self.execute_query(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'vacancies');",
            fetch_all=True
        )[0][0]:
            return

        # Если таблицы нет — создаём
        self.execute_query("""
            CREATE TABLE vacancies (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                url TEXT,
                salary_from INTEGER,
                salary_to INTEGER,
                area VARCHAR(255),
                description TEXT
            );
        """)

        print("Таблица vacancies успешно создана.")

    def clear_table(self):
        """
        Удаляет все записи из таблицы 'vacancies', не удаляя саму таблицу.
        """
        query = "DELETE FROM vacancies;"
        self.execute_query(query)
        print("Таблица vacancies очищена.")

    # =============== ЗАПИСЬ ДАННЫХ ===============

    def write_data(self, data):
        """
        Записывает список вакансий в базу данных. Пропускает дубликаты по ID.

        :param data: Список словарей, содержащих данные вакансий.
        """
        query = """
            INSERT INTO vacancies (id, name, url, salary_from, salary_to, area, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
        """

        # Преобразуем данные в список кортежей для вставки
        data_tuples = [
            (
                v["id"],
                v["name"],
                v["url"],
                v["salary_from"],
                v["salary_to"],
                v["area"],
                v["description"]
            )
            for v in data
        ]

        # Массовая вставка данных
        self.execute_query(query, data_tuples, executemany=True)
        print("Данные успешно записаны в базу данных.")

    # =============== ЧТЕНИЕ ДАННЫХ ===============

    def get_all_vacancies(self):
        """
        Получает все вакансии из базы данных.

        :return: Список словарей с полями id, vacancy_name, salary_from, salary_to, url, area, description.
        """
        query = """
            SELECT id, name, salary_from, salary_to, url, area, description FROM vacancies;
        """
        result = self.execute_query(query, fetch_all=True)

        return [
            dict(zip(
                ["id", "vacancy_name", "salary_from", "salary_to", "url", "area", "description"],
                row
            ))
            for row in result
        ]

    def get_vacancies_by_keyword(self, keyword):
        """
        Выполняет поиск вакансий по ключевому слову в названии (регистронезависимый поиск).

        :param keyword: Ключевое слово.
        :return: Список словарей с найденными вакансиями.
        """
        query = """
            SELECT id, name, salary_from, salary_to, area, url
            FROM vacancies
            WHERE name ILIKE %s;
        """
        result = self.execute_query(query, (f"%{keyword}%",), fetch_all=True)

        return [
            dict(zip(
                ["id", "vacancy_name", "salary_from", "salary_to", "area", "url"],
                row
            ))
            for row in result
        ]

    # =============== УНИВЕРСАЛЬНЫЙ ВСПОМОГАТЕЛЬНЫЙ МЕТОД ===============

    def execute_query(self, query, data=None, fetch_all=False, executemany=False):
        """
        Универсальный метод для выполнения SQL-запросов.

        :param query: SQL-запрос в виде строки.
        :param data: Кортеж или список кортежей для параметров запроса.
        :param fetch_all: Если True — возвращает результат запроса.
        :param executemany: Если True — выполняет executemany для массовой вставки.
        :return: Результаты запроса (если fetch_all=True), иначе None.
        """
        try:
            with self.connect() as conn:
                with conn.cursor() as cursor:
                    # Выполняем запрос с параметрами
                    if data:
                        if executemany:
                            cursor.executemany(query, data)
                        else:
                            cursor.execute(query, data)
                    else:
                        cursor.execute(query)

                    # Получаем результаты, если нужно
                    if fetch_all:
                        return cursor.fetchall()

                    # Подтверждаем изменения
                    conn.commit()

        except psycopg2.Error as error:
            print(f"Ошибка при работе с базой данных: {error}")
            return [] if fetch_all else None
