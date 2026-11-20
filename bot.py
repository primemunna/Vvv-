import html
import uuid
import sqlite3
from datetime import datetime
import telebot
from telebot import types

# ================= CONFIGURATION =================
BOT_TOKEN = "9264462815:AAGEuwfs4x_MZdv5rwRfM9Pi71Z0-DYKEMw"  # Replace with your BotFather token
SUPPORT_USERNAME = "@ai_brain_box_2"
DB_PATH = "file_sharing.db"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
BOT_USERNAME = bot.get_me().username


# ================= DATABASE SETUP =================
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            joined_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            share_code TEXT UNIQUE,
            user_id INTEGER,
            file_id TEXT,
            file_type TEXT,
            file_name TEXT,
            file_size INTEGER,
            downloads INTEGER DEFAULT 0,
            uploaded_at TEXT
        )
    """)
    conn.commit()
    return conn


db = init_db()


def db_exec(query, params=(), fetch=False, fetchone=False):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute(query, params)
    res = None
    if fetchone:
        res = c.fetchone()
    elif fetch:
        res = c.fetchall()
    conn.commit()
    conn.close()
    return res


def ensure_user(user):
    exists = db_exec("SELECT user_id FROM users WHERE user_id=?", (user.id,), fetchone=True)
    full_name = user.first_name or "User"
    username = user.username or "N/A"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if not exists:
        db_exec(
            "INSERT INTO users (user_id, username, full_name, joined_at) VALUES (?, ?, ?, ?)",
            (user.id, username, full_name, now),
        )
    else:
        db_exec(
            "UPDATE users SET username=?, full_name=? WHERE user_id=?",
            (username, full_name, user.id),
        )


def format_size(size_bytes):
    if not size_bytes:
        return "Unknown"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


# ================= KEYBOARD =================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📤 Upload Files", "📁 My Files")
    markup.row("🆘 Support", "👤 Account")
    return markup


# ================= SEND FILE BY TYPE =================
def send_stored_file(chat_id, file_id, file_type, caption=None):
    if file_type == "document":
        bot.send_document(chat_id, file_id, caption=caption)
    elif file_type == "photo":
        bot.send_photo(chat_id, file_id, caption=caption)
    elif file_type == "video":
        bot.send_video(chat_id, file_id, caption=caption)
    elif file_type == "audio":
        bot.send_audio(chat_id, file_id, caption=caption)
    elif file_type == "voice":
        bot.send_voice(chat_id, file_id, caption=caption)
    elif file_type == "animation":
        bot.send_animation(chat_id, file_id, caption=caption)
    elif file_type == "video_note":
        bot.send_video_note(chat_id, file_id)
    elif file_type == "sticker":
        bot.send_sticker(chat_id, file_id)


# ================= /start & DEEP LINKING =================
@bot.message_handler(commands=["start"])
def handle_start(message):
    ensure_user(message.from_user)
    args = message.text.split()

    # Check if user opened a share link: /start <share_code>
    if len(args) > 1:
        code = args[1].strip()
        row = db_exec(
            "SELECT file_id, file_type, file_name, file_size, downloads FROM files WHERE share_code=?",
            (code,),
            fetchone=True,
        )
        if not row:
            bot.send_message(
                message.chat.id,
                "❌ <b>File Not Found or Deleted!</b>\n\n"
                "The share link you opened is invalid or the owner has removed this file.",
                reply_markup=main_menu(),
            )
            return

        file_id, file_type, file_name, file_size, downloads = row
        db_exec("UPDATE files SET downloads = downloads + 1 WHERE share_code=?", (code,))
        caption = (
            f"📦 <b>Shared File Delivered</b>\n\n"
            f"📄 <b>Name:</b> {html.escape(file_name)}\n"
            f"💾 <b>Size:</b> {format_size(file_size)}\n"
            f"📥 <b>Total Downloads:</b> {downloads + 1}\n\n"
            f"🤖 <i>Powered by @{BOT_USERNAME}</i>"
        )
        try:
            send_stored_file(message.chat.id, file_id, file_type, caption=caption)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Failed to send file: <code>{html.escape(str(e))}</code>")
        return

    name = html.escape(message.from_user.first_name or "User")
    bot.send_message(
        message.chat.id,
        f"👋 <b>Welcome, {name}!</b>\n\n"
        f"📂 You are connected to our <b>Universal Cloud File Sharing Bot</b>. "
        f"Upload any type of file and get an instant, permanent shareable link!\n\n"
        f"✅ <b>Supported File Types:</b>\n"
        f"• Documents (<code>.pdf</code>, <code>.zip</code>, <code>.apk</code>, <code>.exe</code>, <code>.py</code>, etc.)\n"
        f"• Photos & Images\n"
        f"• Videos & Video Notes\n"
        f"• Audio, Music & Voice Messages\n"
        f"• GIFs & Stickers\n\n"
        f"👇 Choose an option from the menu below to begin:",
        reply_markup=main_menu(),
    )


# ================= MENU TEXT HANDLER =================
@bot.message_handler(content_types=["text"])
def handle_text(message):
    uid = message.from_user.id
    text = message.text.strip()
    ensure_user(message.from_user)

    if text == "📤 Upload Files":
        bot.send_message(
            message.chat.id,
            "📤 <b>Ready to Upload!</b>\n\n"
            "Send any file directly to this chat (<b>Document, Photo, Video, Audio, Voice, GIF, or Sticker</b>).\n\n"
            "⚡ As soon as your file arrives, I will store it securely and generate a unique shareable link for you!",
        )

    elif text == "📁 My Files":
        rows = db_exec(
            "SELECT id, share_code, file_type, file_name, file_size, downloads FROM files WHERE user_id=? ORDER BY id DESC",
            (uid,),
            fetch=True,
        )
        if not rows:
            bot.send_message(
                message.chat.id,
                "📭 <b>Your File Vault is Empty</b>\n\n"
                "You haven't uploaded any files yet. Press <b>📤 Upload Files</b> or simply send any file here to get started!",
            )
            return

        bot.send_message(message.chat.id, f"📁 <b>Your Uploaded Files ({len(rows)} total):</b>")
        for f_db_id, code, ftype, fname, fsize, dl in rows[:20]:
            share_link = f"https://t.me/{BOT_USERNAME}?start={code}"
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("📥 Get File", callback_data=f"get_file_{f_db_id}"),
                types.InlineKeyboardButton("🗑 Delete", callback_data=f"del_file_{f_db_id}"),
            )
            bot.send_message(
                message.chat.id,
                f"📄 <b>File:</b> {html.escape(fname)}\n"
                f"🏷 <b>Type:</b> <code>{ftype.upper()}</code> | <b>Size:</b> {format_size(fsize)}\n"
                f"📥 <b>Downloads:</b> {dl}\n"
                f"🔗 <b>Share Link:</b>\n<code>{share_link}</code>",
                reply_markup=markup,
            )

    elif text == "🆘 Support":
        bot.send_message(
            message.chat.id,
            f"🆘 <b>Help & Support Center</b>\n\n"
            f"If you face any issues with uploading files, broken share links, or account inquiries, "
            f"please contact our support team:\n\n"
            f"👨‍💻 <b>Support Contact:</b> {SUPPORT_USERNAME}\n\n"
            f"💡 <i>Please include your User ID (<code>{uid}</code>) when reaching out for faster help.</i>",
        )

    elif text == "👤 Account":
        user_row = db_exec(
            "SELECT user_id, username, full_name, joined_at FROM users WHERE user_id=?",
            (uid,),
            fetchone=True,
        )
        stats = db_exec(
            "SELECT COUNT(*), COALESCE(SUM(file_size), 0), COALESCE(SUM(downloads), 0) FROM files WHERE user_id=?",
            (uid,),
            fetchone=True,
        )
        total_files, total_size, total_dl = stats
        caption = (
            f"👤 <b>Your Account Overview</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📛 <b>Name:</b> {html.escape(user_row[2])}\n"
            f"🆔 <b>User ID:</b> <code>{user_row[0]}</code>\n"
            f"🔗 <b>Username:</b> @{html.escape(user_row[1])}\n"
            f"📅 <b>Joined On:</b> {user_row[3]}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 <b>Total Files Uploaded:</b> {total_files}\n"
            f"💾 <b>Total Storage Used:</b> {format_size(total_size)}\n"
            f"📥 <b>Total Share Downloads:</b> {total_dl}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        try:
            photos = bot.get_user_profile_photos(uid, limit=1)
            if photos.total_count > 0:
                bot.send_photo(message.chat.id, photos.photos[0][-1].file_id, caption=caption)
                return
        except Exception:
            pass
        bot.send_message(message.chat.id, caption)


# ================= ALL MEDIA / FILE UPLOAD HANDLER =================
@bot.message_handler(
    content_types=["document", "photo", "video", "audio", "voice", "animation", "video_note", "sticker"]
)
def handle_all_files(message):
    ensure_user(message.from_user)
    uid = message.from_user.id
    ctype = message.content_type

    file_id = None
    file_name = "Unnamed_File"
    file_size = 0

    if ctype == "document":
        file_id = message.document.file_id
        file_name = message.document.file_name or "Document"
        file_size = message.document.file_size or 0
    elif ctype == "photo":
        photo = message.photo[-1]
        file_id = photo.file_id
        file_name = f"Photo_{int(datetime.now().timestamp())}.jpg"
        file_size = photo.file_size or 0
    elif ctype == "video":
        file_id = message.video.file_id
        file_name = message.video.file_name or f"Video_{int(datetime.now().timestamp())}.mp4"
        file_size = message.video.file_size or 0
    elif ctype == "audio":
        file_id = message.audio.file_id
        file_name = message.audio.file_name or message.audio.title or "Audio.mp3"
        file_size = message.audio.file_size or 0
    elif ctype == "voice":
        file_id = message.voice.file_id
        file_name = f"Voice_{int(datetime.now().timestamp())}.ogg"
        file_size = message.voice.file_size or 0
    elif ctype == "animation":
        file_id = message.animation.file_id
        file_name = message.animation.file_name or "Animation.gif"
        file_size = message.animation.file_size or 0
    elif ctype == "video_note":
        file_id = message.video_note.file_id
        file_name = f"VideoNote_{int(datetime.now().timestamp())}.mp4"
        file_size = message.video_note.file_size or 0
    elif ctype == "sticker":
        file_id = message.sticker.file_id
        file_name = f"Sticker_{message.sticker.emoji or 'item'}.webp"
        file_size = message.sticker.file_size or 0

    share_code = uuid.uuid4().hex[:10]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    db_exec(
        "INSERT INTO files (share_code, user_id, file_id, file_type, file_name, file_size, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (share_code, uid, file_id, ctype, file_name, file_size, now),
    )

    share_link = f"https://t.me/{BOT_USERNAME}?start={share_code}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Open Share Link", url=share_link))

    bot.reply_to(
        message,
        f"✅ <b>File Uploaded & Saved Successfully!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📄 <b>File Name:</b> {html.escape(file_name)}\n"
        f"🏷 <b>Type:</b> <code>{ctype.upper()}</code>\n"
        f"💾 <b>Size:</b> {format_size(file_size)}\n\n"
        f"🔗 <b>Your Shareable Link:</b>\n"
        f"<code>{share_link}</code>\n\n"
        f"📢 <i>Anyone with this link can open it and receive this file instantly!</i>",
        reply_markup=markup,
    )


# ================= INLINE BUTTONS (MY FILES) =================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    data = call.data
    uid = call.from_user.id

    if data.startswith("get_file_"):
        f_id = int(data.split("_")[-1])
        row = db_exec(
            "SELECT file_id, file_type, file_name FROM files WHERE id=? AND user_id=?",
            (f_id, uid),
            fetchone=True,
        )
        if not row:
            bot.answer_callback_query(call.id, "❌ File not found!", show_alert=True)
            return
        bot.answer_callback_query(call.id, "📤 Sending file...")
        send_stored_file(call.message.chat.id, row[0], row[1], caption=f"📄 <b>{html.escape(row[2])}</b>")

    elif data.startswith("del_file_"):
        f_id = int(data.split("_")[-1])
        db_exec("DELETE FROM files WHERE id=? AND user_id=?", (f_id, uid))
        bot.answer_callback_query(call.id, "🗑 File deleted permanently!", show_alert=True)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass


print(f"📂 File Sharing Bot (@{BOT_USERNAME}) is running...")
bot.infinity_polling(skip_pending=True)
