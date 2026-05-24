"""
MAZE by Щёлочь — Telegram bot.

Commands:
  /start  — welcome image + intro + Play button
  /lore   — story of how Ronaldo got stuck in Шёлочь labyrinth + Play button

Any other text → fallback reply with Play button.
"""
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Config from environment (set in Railway dashboard)
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEB_APP_URL = os.environ.get("WEB_APP_URL", "https://comforting-paprenjak-ed3c6f.netlify.app")

# Images bundled with the repo
WELCOME_IMAGE_PATH = "welcome.jpg"
LORE_IMAGE_PATH = "lore.jpg"

WELCOME_TEXT = (
    "👋 Привет! Это MAZE by Щёлочь.\n\n"
    "Маленькая игра в стиле пакмана. Бегай по лабиринту, "
    "собирай мячи и не попадайся врагам.\n\n"
    "🍺 Пиво даёт силу — на пару секунд враги становятся "
    "беззащитными, можно их есть.\n\n"
    "🎮 Управление: свайпы по экрану или D-pad внизу "
    "(переключается кнопкой).\n\n"
    "🏆 Цель: собрать все мячи и заслужить Кубок Чемпионов.\n\n"
    "Жми «Играть» 👇\n\n"
    "📖 А ещё — загляни в /lore, узнаешь как Криш сюда попал."
)

LORE_TEXT = (
    "📖 ЛОР\n\n"
    "Москва, лето 2018-го. ЧМ по футболу только что закончился — "
    "Россия выбила Испанию, страна гудит, на Красной площади ещё "
    "горят файеры. Криштиану Роналду, уставший после долгого матча, "
    "бредёт по ночной Москве в поисках своего отеля.\n\n"
    "Где-то возле Кремля он замечает вывеску с пивной кружкой. "
    "«Hotel? Beerhouse? Whatever — finally», — думает он и заходит внутрь.\n\n"
    "Это была ошибка. 🍺\n\n"
    "Внутри его уже ждали — двое мужиков и две девушки с кружками: "
    "Маша, Сергей, Лена и Сальвини (да-да, тот самый, как он там "
    "оказался — отдельный вопрос). Они пьют пиво, смотрят повтор "
    "матча и зовут Криша за стол.\n\n"
    "Через пять кружек Роналду понимает, что это не отель. И даже "
    "не пивная. Это — ЛАБИРИНТ ЩЁЛОЧИ. Бесконечные коридоры, "
    "плакаты «ПИВО ЭТО ЖИЗНЬ», запах хмеля и четыре силуэта, "
    "которые бегут за ним.\n\n"
    "Выход где-то есть. Кубок Чемпионов — тоже. Надо только собрать "
    "все мячи и не дать себя поймать.\n\n"
    "🏃 Беги, Криш. Беги. 👇"
)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def play_button() -> InlineKeyboardMarkup:
    """Inline button that opens the Mini App in full-screen Telegram."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome photo + caption + Play button."""
    user = update.effective_user
    logger.info("User %s (%s) -> /start", user.id, user.username)
    with open(WELCOME_IMAGE_PATH, "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=WELCOME_TEXT,
            reply_markup=play_button(),
        )


async def lore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /lore — story image + caption + Play button."""
    user = update.effective_user
    logger.info("User %s (%s) -> /lore", user.id, user.username)
    with open(LORE_IMAGE_PATH, "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=LORE_TEXT,
            reply_markup=play_button(),
        )


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Any non-command message → short reply with Play button."""
    await update.message.reply_text(
        "Жми «Играть» внизу 👇\n\n"
        "Команды:\n"
        "/start — приветствие\n"
        "/lore — как Роналду попал в лабиринт",
        reply_markup=play_button(),
    )


def main() -> None:
    """Run the bot via long polling."""
    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lore", lore))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))

    logger.info("Bot started. Web App URL: %s", WEB_APP_URL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
