import os
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from groq import Groq

# ===== НАЛАШТУВАННЯ ВЕБ-СЕРВЕРА ДЛЯ RENDER =====
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Запускаємо веб-сервер в окремому потоці
threading.Thread(target=run_health_check, daemon=True).start()

# ===== ОСНОВНИЙ КОД БОТА =====
logging.basicConfig(level=logging.INFO)

# Ключі беруться з налаштувань сервера
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)


@dp.message(CommandStart())
async def start_cmd(message: Message):
    await message.answer(
        "Привіт! Надішли мені голосове повідомлення або кружечок, "
        "і я переведу його в текст українською мовою."
    )


@dp.message(F.voice | F.video_note)
async def handle_audio_or_video_note(message: Message):
    status_msg = await message.reply("⏳ Розпізнаю аудіо...")

    if message.voice:
        file_id = message.voice.file_id
        ext = "ogg"
    else:
        file_id = message.video_note.file_id
        ext = "mp4"

    temp_path = f"temp_{file_id}.{ext}"

    try:
        file_info = await bot.get_file(file_id)
        await bot.download_file(file_info.file_path, destination=temp_path)

        with open(temp_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(temp_path, audio_file.read()),
                model="whisper-large-v3",
                language="uk",
                response_format="text",
            )

        text = str(transcription).strip()

        if text:
            await status_msg.edit_text(f"📝 **Текст:**\n\n{text}")
        else:
            await status_msg.edit_text("Не вдалося розпізнати мову.")

    except Exception as e:
        logging.error(f"Помилка: {e}")
        await status_msg.edit_text("Виникла помилка під час обробки.")

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
