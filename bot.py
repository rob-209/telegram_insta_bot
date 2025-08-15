import os
import re
import json
import requests
import asyncio
import tempfile
import shutil
import instaloader
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

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
        "• Пост (фото/видео/карусель)\n"
        "• Reels\n"
        "• IGTV\n\n"
        "Пример: https://www.instagram.com/p/Cxyz...\n"
        "Бот скачает все медиа из поста, если их несколько.\n\n"
        "Важно: Бот работает только с публичными аккаунтами!"
    )

async def download_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скачиваем медиа из Instagram используя Instaloader"""
    url = update.message.text.strip()
    
    # Проверяем формат ссылки
    if not re.match(r'https?://(www\.)?instagram\.com/(p|reel|tv)/', url):
        await update.message.reply_text("🔗 Отправьте корректную ссылку Instagram")
        return
    
    try:
        msg = await update.message.reply_text("⏳ Обрабатываю ссылку...")
        
        # Извлекаем shortcode из URL
        parts = url.split('/')
        if 'reel' in parts:
            shortcode_index = parts.index('reel')
        elif 'tv' in parts:
            shortcode_index = parts.index('tv')
        else:
            shortcode_index = parts.index('p') if 'p' in parts else -1
        
        if shortcode_index == -1 or shortcode_index + 1 >= len(parts):
            await update.message.reply_text("❌ Не удалось извлечь shortcode из ссылки")
            return
            
        shortcode = parts[shortcode_index + 1].split('?')[0]  # Удаляем параметры запроса
        
        # Создаем временную папку
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Используем instaloader для получения информации о посте
            L = instaloader.Instaloader(
                dirname_pattern=temp_dir,
                download_pictures=False,
                download_videos=False,
                download_video_thumbnails=False,
                save_metadata=False,
                compress_json=False
            )
            
            # Получаем пост
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            
            # Список URL медиа
            media_urls = []
            if post.typename == 'GraphSidecar':
                # Карусель
                for node in post.get_sidecar_nodes():
                    if node.is_video:
                        media_urls.append(('video', node.video_url))
                    else:
                        media_urls.append(('photo', node.display_url))
            else:
                # Одиночный пост
                if post.is_video:
                    media_urls.append(('video', post.video_url))
                else:
                    media_urls.append(('photo', post.url))
            
            if not media_urls:
                await msg.edit_text("❌ Медиа не найдено")
                return
                
            total_media = len(media_urls)
            await msg.edit_text(f"📥 Найдено {total_media} медиа. Скачиваю...")
            
            # Скачиваем и отправляем каждое медиа
            for index, (media_type, media_url) in enumerate(media_urls):
                # Скачиваем в временный файл
                response = requests.get(media_url, stream=True, timeout=30)
                response.raise_for_status()
                
                # Определяем расширение
                ext = '.mp4' if media_type == 'video' else '.jpg'
                file_path = os.path.join(temp_dir, f"media_{index}{ext}")
                
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Отправляем в Telegram
                if media_type == 'video':
                    await update.message.reply_video(
                        video=open(file_path, 'rb'),
                        supports_streaming=True,
                        caption=f"Медиа {index+1}/{total_media}" if total_media > 1 else None
                    )
                else:
                    await update.message.reply_photo(
                        photo=open(file_path, 'rb'),
                        caption=f"Медиа {index+1}/{total_media}" if total_media > 1 else None
                    )
                
                # Удаляем временный файл
                os.unlink(file_path)
            
            await msg.edit_text("✅ Скачивание завершено!")
            
        except instaloader.exceptions.InstaloaderException as e:
            await msg.edit_text(f"❌ Ошибка Instaloader: {e}")
        except requests.RequestException as e:
            await msg.edit_text(f"⚠️ Ошибка сети: {str(e)}")
        except Exception as e:
            await msg.edit_text(f"⚠️ Неизвестная ошибка: {str(e)}")
        finally:
            # Удаляем временную папку
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except Exception as e:
        await msg.edit_text(f"⚠️ Критическая ошибка: {str(e)}")

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
