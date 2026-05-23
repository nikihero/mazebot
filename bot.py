"""
MAZE by Щёлочь — Telegram bot.
Onboarding-only: /start command sends a welcome image with text and a button
that opens the Mini App.
"""
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Get config from environment variables (set in Render dashboard, never hardcoded)
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEB_APP_URL = os.environ.get("WEB_APP_URL", "https://comforting-paprenjak-ed3c6f.netlify.app")

# Welcome image — bundled with the repo
WELCOME_IMAGE_PATH = "welcome.jpg"

WELCOME_TEXT = (
    "👋 Привет! Это MAZE by Щёлочь.\n\n"
    "Маленькая игра в стиле пакмана. Бегай по лабиринту, "
    "собирай мячи и не попадайся врагам.\n\n"
    "🍺 Пиво даёт силу — на пару секунд враги становятся "
    "беззащитными, можно их есть.\n\n"
    "🎮 Управление: свайпы по экрану или D-pad внизу "
    "(переключается кнопкой).\n\n"
    "🏆 Цель: собрать все мячи и заслужить Кубок Чемпионов.\n\n"
    "Жми «Играть» 👇"
)

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# Reduce noise from HTTP library
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def play_button() -> InlineKeyboardMarkup:
    """Inline button that opens the Mini App in full-screen."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text="🎮 Играть",
            web_app=WebAppInfo(url=WEB_APP_URL),
        )]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — send welcome photo + caption + Play button."""
    user = update.effective_user
    logger.info("User %s (%s) started the bot", user.id, user.username)

    with open(WELCOME_IMAGE_PATH, "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=WELCOME_TEXT,
            reply_markup=play_button(),
        )


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to any non-command message with the play button."""
    await update.message.reply_text(
        "Жми «Играть» внизу 👇",
        reply_markup=play_button(),
    )


def main() -> None:
    """Build and run the bot via long polling."""
    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))

    logger.info("Bot started. Web App URL: %s", WEB_APP_URL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
