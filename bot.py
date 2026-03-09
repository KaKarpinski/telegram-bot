from dotenv import load_dotenv
import os
import json
import base64
import logging
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

import gspread
from google.oauth2.service_account import Credentials

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

load_dotenv()

# ---------------------------
# Google Sheets
# ---------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ← ZMIANA: obsługa credentials z ENV (dla Koyeb) lub z pliku (lokalnie)
GOOGLE_CREDENTIALS_B64 = os.getenv("GOOGLE_CREDENTIALS_B64")
if GOOGLE_CREDENTIALS_B64:
    creds_json = json.loads(base64.b64decode(GOOGLE_CREDENTIALS_B64))
    creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
else:
    creds = Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_FILE"), scopes=SCOPES
    )

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
gc = gspread.authorize(creds)
spreadsheet = gc.open_by_key(SPREADSHEET_ID)

# Stan konwersacji
WAITING_CATEGORIES = 1
WAITING_CATEGORY_ACTION = 2

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")


# ====== Helpers ======

def col_letter(n: int) -> str:
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def current_month_label() -> str:
    return datetime.today().strftime("%Y-%m")


def safe_float(val) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def fmt(amount: float) -> str:
    if amount == int(amount):
        return str(int(amount))
    return f"{amount:.2f}"


# ---- Kategorie ----

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


# ---- Zakładka miesięczna ----

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
    """Dodaje nową kolumnę kategorii do istniejącej zakładki miesięcznej."""
    month = current_month_label()
    try:
        ws = spreadsheet.worksheet(month)
    except gspread.exceptions.WorksheetNotFound:
        return  # zostanie utworzona z pełną listą przy następnym wpisie

    num_cats = len(all_categories)       # już z nową kategorią
    old_suma_col = num_cats + 1          # gdzie SUMA była przed zmianą
    new_suma_col = num_cats + 2          # gdzie SUMA będzie po wstawieniu
    new_cat_letter = col_letter(old_suma_col)

    # Dane nowej kolumny (33 wiersze)
    new_col = [new_category]             # wiersz 1: nagłówek
    new_col += [""] * 31                 # wiersze 2-32: dni (puste)
    new_col.append(                      # wiersz 33: suma kategorii
        f"=SUM({new_cat_letter}2:{new_cat_letter}32)"
    )

    # Wstaw kolumnę w miejsce starej SUMY (SUMA przesuwa się w prawo)
    ws.insert_cols([new_col], col=old_suma_col, value_input_option="USER_ENTERED")

    # Zaktualizuj formuły SUMY (bo nie rozszerzają się automatycznie)
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

# ====== /start ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    categories = get_categories()

    if categories:
        month = current_month_label()
        get_or_create_monthly_ws(categories)
        await update.message.reply_text(
            f"Cześć! 👋\n"
            f"📂 Kategorie: {', '.join(categories)}\n"
            f"📅 Miesiąc: {month}\n\n"
            f"• kawa 16 — dodaj wydatek\n"
            f"• kawa ile — sprawdź sumę\n"
            f"• /kategorie — zmień kategorie"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Cześć! 👋\n"
        "Podaj kategorie oddzielone przecinkami, np.:\n"
        "kawa, jedzenie, transport"
    )
    return WAITING_CATEGORIES


# ====== Odbiór kategorii ======

async def receive_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text
    categories = [c.strip().lower() for c in raw.split(",") if c.strip()]

    if not categories:
        await update.message.reply_text("Nie wykryłem kategorii — spróbuj ponownie.")
        return WAITING_CATEGORIES

    save_categories(categories)
    get_or_create_monthly_ws(categories)

    await update.message.reply_text(
        f"✅ Kategorie: {', '.join(categories)}\n"
        f"📅 Zakładka: {current_month_label()}\n\n"
        f"Wyślij np.  kawa 16  lub  kawa ile"
    )
    return ConversationHandler.END


# ====== /kategorie ======

async def change_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    categories = get_categories()
    if categories:
        await update.message.reply_text(
            f"📂 Twoje kategorie:\n"
            f"{', '.join(categories)}\n\n"
            f"Aby dodać nową, napisz:\n"
            f"dodaj nazwa\n\n"
            f"Np: dodaj alkohol"
        )
        return WAITING_CATEGORY_ACTION
    else:
        await update.message.reply_text(
            "Nie masz jeszcze kategorii.\n"
            "Podaj je oddzielone przecinkami, np.:\n"
            "kawa, jedzenie, transport"
        )
        return WAITING_CATEGORIES
    
async def handle_category_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()

    if not text.startswith("dodaj "):
        await update.message.reply_text(
            "Napisz: dodaj nazwa\n"
            "Np: dodaj alkohol"
        )
        return WAITING_CATEGORY_ACTION

    new_category = text[6:].strip()

    if not new_category:
        await update.message.reply_text("Podaj nazwę kategorii, np: dodaj alkohol")
        return WAITING_CATEGORY_ACTION

    categories = get_categories()

    if new_category in categories:
        await update.message.reply_text(
            f"❌ Kategoria '{new_category}' już istnieje!\n"
            f"📂 Kategorie: {', '.join(categories)}"
        )
        return ConversationHandler.END

    # Dodaj do listy kategorii
    categories.append(new_category)
    save_categories(categories)

    # Dodaj kolumnę do bieżącego miesiąca
    add_category_to_monthly_ws(new_category, categories)

    await update.message.reply_text(
        f"✅ Dodano kategorię: {new_category}\n"
        f"📂 Kategorie: {', '.join(categories)}"
    )
    return ConversationHandler.END

# ====== Obsługa wiadomości ======

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip().lower()
    categories = get_categories()

    if not categories:
        await update.message.reply_text("Najpierw wpisz /start i podaj kategorie.")
        return

    month = current_month_label()
    ws = get_or_create_monthly_ws(categories)

    # ---------- "kawa ile" ----------
    if text.endswith(" ile"):
        category = text[:-4].strip()

        if category not in categories:
            await update.message.reply_text(
                f"❌ Nieznana kategoria: '{category}'\n"
                f"Dostępne: {', '.join(categories)}"
            )
            return

        cat_col = categories.index(category) + 2
        total = safe_float(ws.cell(33, cat_col).value)
        await update.message.reply_text(f"📊 {category} w {month}: {fmt(total)} zł")
        return

    # ---------- "kawa 16" ----------
    parts = text.split()
    if len(parts) == 2:
        category, amount_str = parts

        if category not in categories:
            await update.message.reply_text(
                f"❌ Nieznana kategoria: '{category}'\n"
                f"Dostępne: {', '.join(categories)}"
            )
            return

        try:
            amount = float(amount_str.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Kwota musi być liczbą, np.  kawa 16")
            return

        day = datetime.today().day
        row = day + 1
        cat_col = categories.index(category) + 2

        current = safe_float(ws.cell(row, cat_col).value)
        ws.update_cell(row, cat_col, current + amount)

        total = safe_float(ws.cell(33, cat_col).value)

        await update.message.reply_text(
            f"✅ +{fmt(amount)} zł → {category}\n"
            f"📊 Suma {category} w {month}: {fmt(total)} zł"
        )
        return

    # ---------- nieznany format ----------
    await update.message.reply_text(
        "🤔 Nie rozumiem. Użyj:\n"
        "• kawa 16 — dodaj wydatek\n"
        "• kawa ile — sprawdź sumę"
    )


# ====== Health check server (wymagany przez Koyeb) ======

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def run_health_server():
    port = int(os.getenv("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


# ====== main ======

def main():
    # ← ZMIANA: health check w tle
    Thread(target=run_health_server, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("kategorie", change_categories),
        ],
        states={
            WAITING_CATEGORIES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_categories)
            ],
            WAITING_CATEGORY_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category_action)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot uruchomiony ✅")
    app.run_polling()


if __name__ == "__main__":
    main()