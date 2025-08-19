#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fedia Adventure Telegram Bot
- Sends a 100-step interactive journey for a 10-year-old boy Fedia.
- At each step user gets two choices (InlineKeyboard). Any choice advances to the next step.
- The ending is always the same: Fedia arrives in Feodosiya and realizes it is the best place in the world.

Requirements:
  pip install "python-telegram-bot>=20,<22"

Run:
  export BOT_TOKEN="8378653232:AAEw_-F8tDB1u6G33veUP-ZM7BNVMMKN934"
  python fedia_bot.py
"""
import os
import json
import logging
from typing import Dict, Any

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    Application,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
)

# --- Config ---
TOKEN = os.getenv("BOT_TOKEN", "8378653232:AAEw_-F8tDB1u6G33veUP-ZM7BNVMMKN934")
DATA_FILE = os.path.join(os.path.dirname(__file__), "fedia_story.json")
TOTAL_STEPS = 100

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Load story ---
if not os.path.exists(DATA_FILE):
    raise FileNotFoundError(
        f"Не найден файл с историей: {DATA_FILE}. Убедитесь, что fedia_story.json лежит рядом с fedia_bot.py"
    )

with open(DATA_FILE, "r", encoding="utf-8") as f:
    STORY = json.load(f)

def _get_user_state(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    # step is 0-based index into STORY
    if "step" not in context.user_data:
        context.user_data["step"] = 0
    if "path" not in context.user_data:
        context.user_data["path"] = []
    return context.user_data

def _build_keyboard(step_idx: int) -> InlineKeyboardMarkup:
    step = STORY[step_idx]
    a = step["a"]
    b = step["b"]
    kb = [
        [
            InlineKeyboardButton(a, callback_data=f"choose|{step_idx}|a"),
            InlineKeyboardButton(b, callback_data=f"choose|{step_idx}|b"),
        ]
    ]
    return InlineKeyboardMarkup(kb)

async def _send_step(update: Update, context: ContextTypes.DEFAULT_TYPE, step_idx: int) -> None:
    """Send step text with two choice buttons."""
    step = STORY[step_idx]
    header = f"Шаг {step['id']}/{TOTAL_STEPS}"
    text = f"{header}\n\n{step['text']}\n\nВыбери вариант:"
    await update.effective_chat.send_message(text, reply_markup=_build_keyboard(step_idx))

async def _send_final(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    path = context.user_data.get("path", [])
    # Optional: show short summary of choices count
    total = len(path)
    await update.effective_chat.send_message(
        "🏁 ФИНАЛ ПУТЕШЕСТВИЯ\n\n"
        "Федя приезжает в город Феодосия, слышит шёпот моря и понимает: "
        "это лучшее место в мире. Здесь — свет, просторы и радость открытий. "
        "Спасибо, что сопровождал его на пути!"
        f"\n\nСделано выборов: {total}. Чтобы пройти ещё раз — /reset"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = _get_user_state(context)
    state["step"] = 0
    state["path"] = []
    await update.message.reply_text(
        "Привет! Это интерактивное путешествие Мальчика Феди (10 лет). "
        "На каждом шаге у тебя будет два варианта выбора. Какой бы ты ни выбрал, "
        "история продолжится и приведёт к одному финалу. Поехали!"
    )
    await _send_step(update, context, 0)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Команды:\n"
        "/start — начать заново\n"
        "/reset — сбросить прогресс\n"
        "/progress — текущий шаг\n"
        "/help — помощь"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = _get_user_state(context)
    state["step"] = 0
    state["path"] = []
    await update.message.reply_text("Прогресс сброшен. Начинаем сначала!")
    await _send_step(update, context, 0)

async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = _get_user_state(context)
    step = state.get("step", 0)
    await update.message.reply_text(f"Ты на шаге {step+1} из {TOTAL_STEPS}.")

async def on_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button presses: 'choose|<step_idx>|a' or 'b'"""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    try:
        kind, step_idx_str, which = data.split("|")
        step_idx = int(step_idx_str)
    except Exception:
        logger.exception("Некорректные данные callback: %s", data)
        await query.edit_message_text("Произошла ошибка с выбором. Нажми /reset и попробуй снова.")
        return

    state = _get_user_state(context)
    # Only accept if pressing for the current step (avoid double-press / race)
    if step_idx != state["step"]:
        # Just ignore or gently indicate
        await query.answer("Этот шаг уже пройден.", show_alert=False)
        return

    # Record the choice
    step_obj = STORY[step_idx]
    chosen_text = step_obj["a"] if which == "a" else step_obj["b"]
    state["path"].append({"step": step_idx+1, "choice": which, "text": chosen_text})

    # Advance
    state["step"] += 1
    next_idx = state["step"]

    # Update previous message to show the chosen option (optional)
    try:
        await query.edit_message_text(
            f"{step_obj['text']}\n\nТвой выбор: {chosen_text} ✅"
        )
    except Exception:
        # Editing may fail if message is too old etc. Just log.
        logger.debug("Не удалось отредактировать сообщение с шагом.")

    # Send next step or final
    if next_idx < TOTAL_STEPS:
        await _send_step(update, context, next_idx)
    else:
        await _send_final(update, context)

def main() -> None:
    if not TOKEN or TOKEN == "PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE":
        raise RuntimeError("Сначала укажи токен в переменной окружения BOT_TOKEN или прямо в коде.")
    app: Application = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("progress", progress))
    app.add_handler(CallbackQueryHandler(on_choice, pattern=r"^choose\|"))

    logger.info("Бот запущен. Ожидаю сообщения...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
