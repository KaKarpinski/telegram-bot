from datetime import datetime
from bot.keyboards import with_buttons
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)

from helpers import current_month_label, safe_float, fmt, with_hint
from spreadsheets import get_categories_sum, save_categories, get_categories, get_or_create_monthly_ws, add_category_to_monthly_ws, get_spreadsheet_names, get_monthly_ws, get_category_sum, get_month_sum, get_subscriptions, save_subscription, update_subscription, get_subscriptions_sum
from consts import WAITING_CATEGORIES, WAITING_CATEGORY_ACTION, WAITING_SUM_ACTION, WAITING_SUB_ACTION

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
            f"• /suma — sprawdź sumy według miesięcy"
        )
        return ConversationHandler.END

    await update.message.reply_text(with_hint(
        "Cześć! 👋\n"
        "Podaj kategorie oddzielone przecinkami, np.:\n"
        "kawa, jedzenie, transport"
    ))
    return WAITING_CATEGORIES

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
        await update.message.reply_text(with_hint(
            "Nie masz jeszcze kategorii.\n"
            "Podaj je oddzielone przecinkami, np.:\n"
            "kawa, jedzenie, transport"
        ))
        return WAITING_CATEGORIES

async def handle_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    subs = get_subscriptions()
    if subs:
        formatted = [f"{name} {cost}" for name, cost in subs]
        await update.message.reply_text(
            f"📂 Twoje subskrypcje:\n"
            f"{', '.join(formatted)}\n\n"
            f"Aby dodać nową lub zaktualizować istniejącą, napisz:\n"
            f"dodaj [nazwa] [kwota]\n\n"
            f"Np: dodaj spotify 30"
        )
        return WAITING_SUB_ACTION
    else:
        await update.message.reply_text(with_hint(
            "Nie masz jeszcze subskrypcji.\n"
            f"Aby dodać nową, napisz:\n"
            f"dodaj [nazwa] [kwota]\n\n"
            f"Np: dodaj spotify 30"
        ))
        return WAITING_SUB_ACTION

async def handle_subscription_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()

    if not text.startswith("dodaj "):
        await update.message.reply_text(
            "Napisz: dodaj [nazwa] [kwota]\n"
            "Np: dodaj spotify 30"
        )
        return WAITING_SUB_ACTION

    new_sub = text[6:].strip()

    if not new_sub:
        await update.message.reply_text("Podaj nazwę subskrypcji i kwotę, np: dodaj spotify 30")
        return WAITING_SUB_ACTION

    subs_list = get_subscriptions()
    subs_names = [name for name, cost in subs_list]

    parts = new_sub.split(" ")
    if len(parts) < 2:
        await update.message.reply_text("❌ Błąd: wpisz nazwę i kwotę, np. spotify 30")
        return ConversationHandler.END

    new_sub_name = parts[0].strip().lower()

    try:
        new_sub_cost = int(parts[1].strip())
    except ValueError:
        await update.message.reply_text("❌ Kwota musi być liczbą całkowitą.")
        return ConversationHandler.END

    if new_sub_name in subs_names:
        update_subscription(new_sub_name, new_sub_cost)
        await update.message.reply_text(
            f"✅ Zaktualizowano subskrypcję: {new_sub_name} → {new_sub_cost} PLN"
        )
    else:
        save_subscription(new_sub_name, new_sub_cost)
        subs_list.append((new_sub_name, new_sub_cost))
        f"✅ Dodano subskrypcję: {new_sub_name} {new_sub_cost} PLN"

    updated_subs_list = get_subscriptions()
    formatted_subs = [f"{name} {cost}" for name, cost in updated_subs_list]

    await update.message.reply_text(
        f"📂 Twoje subskrypcje:\n"
        f"{', '.join(formatted_subs)}"
    )
    return ConversationHandler.END

async def get_requested_sum_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    months = get_spreadsheet_names()

    if len(months) <= 1:
        await update.message.reply_text("Nie masz jeszcze czego sumować")
        return
    else:
        await update.message.reply_text(
            "📅 Wybierz miesiąc, z którego mam policzyć sumę:",
            reply_markup=with_buttons(months, columns=3)
        )
        return WAITING_SUM_ACTION
    
async def handle_sum_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    month = query.data.strip().lower()

    await query.edit_message_text("⏳ Obliczam sumę...")
    
    ws = get_monthly_ws(month)

    if not ws:
        await query.edit_message_text(
            f"❌ Nie znaleziono arkusza dla miesiąca: {month}"
        )
        return ConversationHandler.END

    total = get_month_sum(ws)
    categories_sum = get_categories_sum(ws)
    subs_sum = get_subscriptions_sum()

    await query.edit_message_text(
        f"📊 Suma wszystkich wydatków w {month}: {int(total) + subs_sum}\n"
        f"📊 {categories_sum}\n"
        f"➕ w tym subskrypcje: {subs_sum}"
    )
    return ConversationHandler.END    
    
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

    categories.append(new_category)
    save_categories(categories)

    add_category_to_monthly_ws(new_category, categories)

    await update.message.reply_text(
        f"✅ Dodano kategorię: {new_category}\n"
        f"📂 Kategorie: {', '.join(categories)}"
    )
    return ConversationHandler.END

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
            await update.message.reply_text("Kwota musi być liczbą, np. kawa 16")
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

    await update.message.reply_text(
        "🤔 Nie rozumiem. Użyj:\n"
        "• kawa 16 — dodaj wydatek\n"
        "• kawa ile — sprawdź sumę"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Anulowano. Możesz wpisać nową komendę.")
    return ConversationHandler.END