import logging
import sqlite3
from datetime import datetime

from telegram import Update, ChatInviteLink
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    ChatMemberHandler,
    ContextTypes,
)

# ==== НАСТРОЙКИ ====
BOT_TOKEN = "ВСТАВЬТЕ_СЮДА_ТОКЕН_ОТ_BOTFATHER"
CHAT_ID = "-1001234567890"  # id канала/группы, куда создаём ссылки
ADMIN_IDS = {111111111, 222222222}  # user_id тех, кому разрешено создавать ссылки; пусто = разрешено всем
# ====================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DB_PATH = "invite_stats.db"


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            invite_link TEXT UNIQUE NOT NULL,
            chat_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS joins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_name TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT,
            joined_at TEXT NOT NULL,
            left_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def is_admin(user_id: int) -> bool:
    # Если ADMIN_IDS не задан — команды доступны всем (для быстрого старта).
    return not ADMIN_IDS or user_id in ADMIN_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я слежу за переходами по инвайт-ссылкам.\n\n"
        "Команды:\n"
        "/newlink <название> — создать новую ссылку-приглашение с меткой источника\n"
        "/deletelink <название> — удалить (отозвать) ссылку\n"
        "/links — список активных ссылок\n"
        "/stats — статистика переходов по ссылкам\n"
    )


async def new_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("У вас нет прав для этой команды.")
        return

    if not context.args:
        await update.message.reply_text(
            "Использование: /newlink <название источника>\nНапример: /newlink instagram_bio"
        )
        return

    name = "_".join(context.args)

    conn = db_connect()
    existing = conn.execute("SELECT * FROM links WHERE name = ?", (name,)).fetchone()
    if existing:
        await update.message.reply_text(f"Ссылка с названием «{name}» уже существует:\n{existing['invite_link']}")
        conn.close()
        return

    try:
        invite_link: ChatInviteLink = await context.bot.create_chat_invite_link(
            chat_id=CHAT_ID,
            name=name,
            creates_join_request=False,
        )
    except Exception as e:
        logger.exception("Не удалось создать ссылку")
        await update.message.reply_text(
            f"Не получилось создать ссылку: {e}\n"
            "Проверьте, что бот добавлен админом в канал/группу с правом приглашать пользователей."
        )
        conn.close()
        return

    conn.execute(
        "INSERT INTO links (name, invite_link, chat_id, created_at, created_by) VALUES (?, ?, ?, ?, ?)",
        (name, invite_link.invite_link, str(CHAT_ID), datetime.utcnow().isoformat(), user.id),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"Готово! Ссылка для «{name}»:\n{invite_link.invite_link}")


async def delete_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("У вас нет прав для этой команды.")
        return

    if not context.args:
        await update.message.reply_text(
            "Использование: /deletelink <название>\nНапример: /deletelink instagram_bio\n\n"
            "Посмотреть названия можно через /links"
        )
        return

    name = "_".join(context.args)

    conn = db_connect()
    row = conn.execute("SELECT * FROM links WHERE name = ?", (name,)).fetchone()
    if not row:
        await update.message.reply_text(f"Ссылка с названием «{name}» не найдена. Проверьте /links.")
        conn.close()
        return

    try:
        await context.bot.revoke_chat_invite_link(chat_id=row["chat_id"], invite_link=row["invite_link"])
    except Exception as e:
        logger.exception("Не удалось отозвать ссылку")
        await update.message.reply_text(f"Не получилось отозвать ссылку в Telegram: {e}")
        conn.close()
        return

    conn.execute("DELETE FROM links WHERE name = ?", (name,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"Ссылка «{name}» удалена и больше не действует.\n"
        "Статистика по уже перешедшим по ней людям сохранена и видна в /stats."
    )


async def list_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db_connect()
    rows = conn.execute("SELECT name, invite_link FROM links ORDER BY created_at DESC").fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Пока нет ни одной ссылки. Создайте через /newlink <название>.")
        return

    text = "Активные ссылки:\n\n" + "\n".join(f"• {r['name']}: {r['invite_link']}" for r in rows)
    await update.message.reply_text(text)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db_connect()
    rows = conn.execute(
        """
        SELECT j.link_name AS name,
               COUNT(j.id) AS joined,
               SUM(CASE WHEN j.left_at IS NULL THEN 1 ELSE 0 END) AS active,
               MAX(CASE WHEN l.name IS NOT NULL THEN 1 ELSE 0 END) AS is_active_link
        FROM joins j
        LEFT JOIN links l ON l.name = j.link_name
        GROUP BY j.link_name
        ORDER BY joined DESC
        """
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Пока нет данных. Создайте ссылки через /newlink.")
        return

    lines = ["Статистика по источникам:\n"]
    total = 0
    for r in rows:
        joined = r["joined"] or 0
        active = r["active"] or 0
        total += joined
        mark = "" if r["is_active_link"] else " (ссылка удалена)"
        lines.append(f"• {r['name']}{mark}: перешло {joined}, осталось в чате {active}")
    lines.append(f"\nВсего переходов: {total}")

    await update.message.reply_text("\n".join(lines))


async def track_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if result is None:
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    user = result.new_chat_member.user

    joined_now = old_status in (
        ChatMemberStatus.LEFT,
        ChatMemberStatus.BANNED,
    ) and new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED)

    left_now = old_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED) and new_status in (
        ChatMemberStatus.LEFT,
        ChatMemberStatus.BANNED,
    )

    conn = db_connect()

    if joined_now:
        invite_link = result.invite_link
        link_name = (
            invite_link.name if invite_link and invite_link.name else "неизвестный источник (прямая ссылка на чат)"
        )
        conn.execute(
            "INSERT INTO joins (link_name, user_id, username, joined_at) VALUES (?, ?, ?, ?)",
            (link_name, user.id, user.username or user.full_name, datetime.utcnow().isoformat()),
        )
        conn.commit()
        logger.info("Пользователь %s (%s) присоединился через '%s'", user.id, user.username, link_name)

    elif left_now:
        conn.execute(
            "UPDATE joins SET left_at = ? WHERE user_id = ? AND left_at IS NULL",
            (datetime.utcnow().isoformat(), user.id),
        )
        conn.commit()
        logger.info("Пользователь %s покинул чат", user.id)

    conn.close()


def main():
    if "ВСТАВЬТЕ_СЮДА" in BOT_TOKEN:
        raise RuntimeError("Укажите настоящий BOT_TOKEN в начале файла bot.py")
    if "1001234567890" in CHAT_ID:
        raise RuntimeError("Укажите настоящий CHAT_ID в начале файла bot.py")

    init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("newlink", new_link))
    application.add_handler(CommandHandler("deletelink", delete_link))
    application.add_handler(CommandHandler("links", list_links))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(ChatMemberHandler(track_membership, ChatMemberHandler.CHAT_MEMBER))

    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
