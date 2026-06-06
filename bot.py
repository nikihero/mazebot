"""
MAZE by Щёлочь — Telegram bot with leaderboard.

Commands:
  /start  — welcome image + intro + Play button
  /lore   — story image + lore text + Play button
  /top    — show global top-10 leaderboard

Mini App sends WebAppData with {"score": N, "win": true/false}
after each game. Bot saves the best score per user to Supabase.

Any other text → fallback reply with Play button.
"""
import json
import logging
import os

from supabase import create_client, Client
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Config from environment (set in Railway dashboard)
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEB_APP_URL = os.environ.get("WEB_APP_URL", "https://comforting-paprenjak-ed3c6f.netlify.app")
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
BOT_USERNAME = os.environ.get("BOT_USERNAME", "playmazebot")

# Safety: max acceptable score per single game (anti-cheat sanity check)
MAX_PLAUSIBLE_SCORE = 100_000

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
    "📖 А ещё — загляни в /lore, узнаешь как Криш сюда попал.\n"
    "🏆 /top — таблица лидеров."
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

# Supabase client (initialized once at module level)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def play_button() -> InlineKeyboardMarkup:
    """Inline button that opens the Mini App in full-screen Telegram."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])


def display_name(user) -> str:
    """Resolve a user-facing name from a Telegram User object.

    Preference: @username (more "identifiable") → first_name → fallback.
    """
    if user.username:
        return f"@{user.username}"
    if user.first_name:
        return user.first_name
    return "Игрок"


# ===== DATABASE HELPERS =====

def db_get_best(user_id: int) -> int:
    """Return current best_score for user, or 0 if no record yet."""
    try:
        result = supabase.table("scores").select("best_score").eq("user_id", user_id).execute()
        if result.data:
            return result.data[0]["best_score"]
    except Exception:
        logger.exception("db_get_best failed for user_id=%s", user_id)
    return 0


def db_upsert_score(user_id: int, username: str | None, first_name: str | None, score: int) -> tuple[int, bool]:
    """Upsert a new score: keep the higher of (existing, new).

    Returns (best_score_after_update, was_new_record).
    """
    existing_best = db_get_best(user_id)
    if score <= existing_best:
        return existing_best, False

    # New personal record — write it
    try:
        supabase.table("scores").upsert({
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "best_score": score,
        }, on_conflict="user_id").execute()
        return score, True
    except Exception:
        logger.exception("db_upsert_score failed for user_id=%s, score=%s", user_id, score)
        return existing_best, False


def db_get_top(limit: int = 10) -> list[dict]:
    """Return top-N rows sorted by best_score descending."""
    try:
        result = (
            supabase.table("scores")
            .select("user_id, username, first_name, best_score")
            .order("best_score", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception:
        logger.exception("db_get_top failed")
        return []


def db_get_rank(user_id: int) -> int | None:
    """Return 1-based rank of user in the global leaderboard, or None if not present."""
    try:
        # Count users with a strictly higher score; rank = that count + 1
        my_best = db_get_best(user_id)
        if my_best == 0:
            return None
        result = (
            supabase.table("scores")
            .select("user_id", count="exact")
            .gt("best_score", my_best)
            .execute()
        )
        # `count` attribute is populated when count="exact"
        higher = result.count or 0
        return higher + 1
    except Exception:
        logger.exception("db_get_rank failed for user_id=%s", user_id)
        return None


# ===== COMMAND HANDLERS =====

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


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /top — global top-10 with the user's own rank pinned at bottom."""
    user = update.effective_user
    logger.info("User %s (%s) -> /top", user.id, user.username)

    rows = db_get_top(10)
    if not rows:
        await update.message.reply_text(
            "🏆 Пока никто не играл. Стань первым!",
            reply_markup=play_button(),
        )
        return

    # Format the leaderboard
    lines = ["🏆 ТОП-10 MAZE", ""]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, row in enumerate(rows, start=1):
        prefix = medals.get(i, f"{i}.")
        # Choose display name: @username if available, else first_name, else fallback
        name = (
            f"@{row['username']}" if row.get("username")
            else (row.get("first_name") or "Игрок")
        )
        lines.append(f"{prefix} {name} — {row['best_score']}")

    # User's own line
    my_best = db_get_best(user.id)
    my_rank = db_get_rank(user.id)
    lines.append("")
    if my_rank is None:
        lines.append("🎯 Ты ещё не играл. Жми «Играть»!")
    else:
        lines.append(f"🎯 Твоё место: #{my_rank} ({my_best} очков)")

    await update.message.reply_text("\n".join(lines), reply_markup=play_button())


# ===== WEB APP DATA (score from the Mini App) =====

async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle data sent from the Mini App via tg.sendData(...)."""
    user = update.effective_user
    raw = update.effective_message.web_app_data.data
    logger.info("WebAppData from %s: %s", user.id, raw)

    # Parse the payload — expecting JSON like {"score": 1240, "win": true}
    try:
        payload = json.loads(raw)
        score = int(payload.get("score", 0))
        won = bool(payload.get("win", False))
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("Bad WebAppData payload from %s: %r", user.id, raw)
        return

    # Sanity check — drop nonsense scores
    if score < 0 or score > MAX_PLAUSIBLE_SCORE:
        logger.warning("Implausible score from %s: %s", user.id, score)
        return

    # Save (only if new personal record)
    new_best, was_new_record = db_upsert_score(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        score=score,
    )

    # Compose response
    rank = db_get_rank(user.id)
    rank_line = f"📊 Место в топе: #{rank}" if rank else ""

    if won:
        header = "🏆 Победа! Кубок Чемпионов твой."
    else:
        header = "💀 Не в этот раз. Криш почти выбрался..."

    if was_new_record:
        body = f"✨ Новый личный рекорд: {score} очков!"
    else:
        body = f"🎯 Очки: {score} · Лучший: {new_best}"

    msg = "\n\n".join(p for p in [header, body, rank_line] if p)
    await update.effective_message.reply_text(msg, reply_markup=play_button())


# ===== FALLBACK =====

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Any non-command text message → reply with hint and Play button."""
    await update.effective_message.reply_text(
        "Жми «Играть» внизу 👇\n\n"
        "Команды:\n"
        "/start — приветствие\n"
        "/lore — история игры\n"
        "/top — таблица лидеров",
        reply_markup=play_button(),
    )


# ===== MAIN =====

def main() -> None:
    """Build and run the bot via long polling."""
    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lore", lore))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))

    logger.info("Bot started. Web App URL: %s", WEB_APP_URL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
