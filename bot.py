# bot.py - главный файл с футбольными командами
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import TELEGRAM_TOKEN
from handlers import BotHandlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Запуск бота"""
    logger.info("🚀 Запуск бота v2.0 с PRO тарифом...")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    handlers = BotHandlers()
    
    # Основные команды
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("promo", handlers.promo_activate))
    app.add_handler(CommandHandler("upgrade", handlers.upgrade))
    app.add_handler(CommandHandler("stats", handlers.stats))
    app.add_handler(CommandHandler("clear", handlers.clear_history))
    
    # ⚽ Футбольные команды (латиницей!)
    app.add_handler(CommandHandler("player", handlers.player_command))
    app.add_handler(CommandHandler("club", handlers.club_command))
    app.add_handler(CommandHandler("compare", handlers.compare_command))
    app.add_handler(CommandHandler("match", handlers.match_command))
    app.add_handler(CommandHandler("predict", handlers.prediction_command))
    
    # Обработка кнопок
    app.add_handler(CallbackQueryHandler(handlers.button_callback))
    
    # Обработка текста
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
    
    logger.info("✅ Бот запущен!")
    logger.info("⚽ Футбольные команды активны")
    logger.info("🔥 PRO тариф активен")
    logger.info("📝 Ctrl+C для остановки")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n👋 Бот остановлен")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")