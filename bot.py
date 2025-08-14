import os
import re
import requests
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes



import os
from telegram.ext import Application

PORT = int(os.environ.get('PORT', 5000))  # Render использует $PORT

async def main():
    application = Application.builder().token(TOKEN).build()
    
    # Для вебхуков
    await application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"https://your-bot-name.onrender.com/{TOKEN}"
    )
    
    # ИЛИ для polling (не рекомендуется на Render)
    # application.run_polling()
# Загружаем переменные из .env
load_dotenv()

# Получаем токен из переменных окружения
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TOKEN:
    raise ValueError("❌ Токен бота не найден! Создайте .env файл с TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    await update.message.reply_text(
        "📸 Instagram Downloader\n\n"
        "Отправьте мне ссылку на:\n"
        "• Пост (фото/видео)\n"
        "• Reels\n"
        "• IGTV\n\n"
        "Пример: https://www.instagram.com/p/Cxyz..."
    )

async def download_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скачиваем медиа из Instagram"""
    url = update.message.text.strip()
    
    # Проверяем формат ссылки
    if not re.match(r'https?://(www\.)?instagram\.com/(p|reel|tv)/', url):
        await update.message.reply_text("🔗 Отправьте корректную ссылку Instagram")
        return
    
    try:
        msg = await update.message.reply_text("⏳ Обрабатываю ссылку...")
        
        # Загружаем страницу
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=50)
        response.raise_for_status()
        
        # Ищем медиа
        content = response.text
        if video_url := re.search(r'"video_url":"([^"]+)"', content):
            await msg.edit_text("🎥 Найдено видео...")
            await update.message.reply_video(video_url.group(1).replace("\\", ""))
        elif image_url := re.search(r'"display_url":"([^"]+)"', content):
            await msg.edit_text("📷 Найдено фото...")
            await update.message.reply_photo(image_url.group(1).replace("\\", ""))
        else:
            await msg.edit_text("❌ Медиа не найдено. Убедитесь, что аккаунт публичный")
            
    except requests.Timeout:
        await msg.edit_text("⌛ Таймаут при загрузке. Попробуйте позже")
    except Exception as e:
        await msg.edit_text(f"⚠️ Ошибка: {str(e)}")

async def post_init(application: Application):
    """Функция инициализации после запуска"""
    bot_info = await application.bot.get_me()
    print(f"✅ Бот @{bot_info.username} запущен!")

def main():
    """Запуск бота"""
    print("🔄 Запускаю бота...")
    
    try:
        # Создаем и настраиваем приложение
        app = Application.builder().token(TOKEN).post_init(post_init).build()
        
        # Регистрируем обработчики
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_media))
        
        # Запускаем бота
        app.run_polling()
        
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")

if __name__ == "__main__":
    main()