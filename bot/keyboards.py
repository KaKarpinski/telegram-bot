from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def with_buttons(buttons: list[str], columns: int = 2) -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    
    for btn_text in buttons:
        row.append(InlineKeyboardButton(text=btn_text, callback_data=btn_text))
        if len(row) == columns:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    return InlineKeyboardMarkup(keyboard)