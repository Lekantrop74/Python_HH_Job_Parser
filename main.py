from src.DBManager import DBVacanciesManager
from src.selenium_utils import save_cookies
from src.ui_utils import *


def main():
    writer = DBVacanciesManager()

    actions = {
        "1": handle_search_and_save,
        "2": handle_show_all,
        "3": handle_search_by_keyword,
        "4": clear_table,
        "5": handle_filter_vacancies,
        "6": handle_export,
        "7": handle_compare_vacancies,
        "8": save_cookies,
        "9": send_apply_to_vacancy,
        "10": exit_program
    }

    while True:
        print_menu()
        choice = input("\nВведите номер действия: ")
        action = actions.get(choice, lambda writer: print("Неверный выбор. Попробуйте снова."))
        action(writer)


if __name__ == "__main__":
    main()
