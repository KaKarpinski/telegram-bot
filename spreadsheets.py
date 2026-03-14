import gspread
from gs_init import spreadsheet

from helpers import col_letter, current_month_label
from logger import logger

def get_categories() -> list:
    try:
        ws = spreadsheet.worksheet("Kategorie")
        values = ws.col_values(1)
        return [v.strip().lower() for v in values if v.strip()]
    except gspread.exceptions.WorksheetNotFound:
        return []


def save_categories(categories: list):
    try:
        ws = spreadsheet.worksheet("Kategorie")
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="Kategorie", rows=100, cols=1)
    ws.update("A1", [[cat] for cat in categories])

def get_or_create_monthly_ws(categories: list) -> gspread.Worksheet:
    month = current_month_label()
    try:
        return spreadsheet.worksheet(month)
    except gspread.exceptions.WorksheetNotFound:
        return create_monthly_ws(month, categories)


def create_monthly_ws(month: str, categories: list) -> gspread.Worksheet:
    num_cats = len(categories)
    num_cols = 1 + num_cats + 1

    ws = spreadsheet.add_worksheet(title=month, rows=33, cols=num_cols)

    first_cat = col_letter(2)
    last_cat = col_letter(1 + num_cats)

    headers = ["dzień"] + categories + ["SUMA"]
    all_rows = [headers]

    for day in range(1, 32):
        r = day + 1
        formula = f"=SUM({first_cat}{r}:{last_cat}{r})"
        all_rows.append([day] + [""] * num_cats + [formula])

    suma_row = ["SUMA"]
    for i in range(num_cats):
        c = col_letter(2 + i)
        suma_row.append(f"=SUM({c}2:{c}32)")
    suma_row.append(f"=SUM({first_cat}33:{last_cat}33)")
    all_rows.append(suma_row)

    ws.update("A1", all_rows, value_input_option="USER_ENTERED")
    logger.info("Utworzono zakładkę: %s", month)
    return ws


def add_category_to_monthly_ws(new_category: str, all_categories: list):
    month = current_month_label()
    try:
        ws = spreadsheet.worksheet(month)
    except gspread.exceptions.WorksheetNotFound:
        return

    num_cats = len(all_categories)
    old_suma_col = num_cats + 1
    new_suma_col = num_cats + 2
    new_cat_letter = col_letter(old_suma_col)

    new_col = [new_category]             # wiersz 1: nagłówek
    new_col += [""] * 31                 # wiersze 2-32: dni (puste)
    new_col.append(                      # wiersz 33: suma kategorii
        f"=SUM({new_cat_letter}2:{new_cat_letter}32)"
    )

    ws.insert_cols([new_col], col=old_suma_col, value_input_option="USER_ENTERED")

    first_cat = col_letter(2)
    last_cat = col_letter(num_cats + 1)
    suma_letter = col_letter(new_suma_col)

    suma_cells = []
    for day in range(1, 32):
        r = day + 1
        suma_cells.append([f"=SUM({first_cat}{r}:{last_cat}{r})"])
    suma_cells.append([f"=SUM({first_cat}33:{last_cat}33)"])

    ws.update(
        f"{suma_letter}2:{suma_letter}33",
        suma_cells,
        value_input_option="USER_ENTERED",
    )
    logger.info("Dodano kolumnę '%s' do zakładki %s", new_category, month)

