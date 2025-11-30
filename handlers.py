# handlers.py - обработчики с PRO тарифом и футбольными командами
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
from gemini_api import GeminiAPI
from firebase_service import DatabaseService
from utils.formatter import format_code, clean_response
from utils.chunker import split_message
from config import FREE_DAILY_LIMIT, PRO_DAILY_LIMIT, PREMIUM_PRICES, ADMIN_IDS
import logging

logger = logging.getLogger(__name__)


class BotHandlers:
    def __init__(self):
        self.gemini = GeminiAPI()
        self.db = DatabaseService()
        logger.info("✅ Обработчики v2.0 с PRO тарифом")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        user = self.db.get_user(user_id)
        if not user:
            self.db.create_user(user_id, username)
            user = self.db.get_user(user_id)
        
        plan_info = self._get_plan_info(user)
        
        keyboard = [
            [InlineKeyboardButton("🎁 Промокод", callback_data="promo")],
            [InlineKeyboardButton("⭐ Купить Premium", callback_data="upgrade")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("⚽ Футбол", callback_data="football")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome = f"""👋 Привет! Я — Gemini AI v2.0

{plan_info}

💬 Просто напиши что угодно!
⚽ Спрашивай про футбол!

🔧 Команды:
/player [имя] - статистика игрока
/club [название] - инфо о клубе
/compare [игрок1] vs [игрок2]
/match [клуб1] vs [клуб2]
/predict [матч] - прогноз
/clear - очистить историю"""
        
        await update.message.reply_text(welcome, reply_markup=reply_markup)
    
    def _get_plan_info(self, user):
        """Информация о тарифе с PRO"""
        plan = user['plan']
        
        if plan == 'vip':
            return "💎 Тариф: VIP (Навсегда) | ∞ запросов ✨"
        
        if plan == 'premium':
            if user['premium_expires']:
                expires = datetime.fromisoformat(user['premium_expires'])
                days = (expires - datetime.now()).days
                if days > 0:
                    return f"⭐ Тариф: PREMIUM ({days} дней) | ∞ запросов"
        
        # 🔥 PRO тариф
        if plan == 'pro':
            if user['premium_expires']:
                expires = datetime.fromisoformat(user['premium_expires'])
                days = (expires - datetime.now()).days
                if days > 0:
                    remaining = self.db.get_remaining_requests(user['user_id'])
                    return f"🔥 Тариф: PRO ({days} дней) | {remaining}/{PRO_DAILY_LIMIT} запросов"
        
        # FREE
        remaining = self.db.get_remaining_requests(user['user_id'])
        return f"🆓 Тариф: FREE | {remaining}/{FREE_DAILY_LIMIT} запросов"
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сообщений с улучшенной обработкой ошибок"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        user = self.db.get_user(user_id)
        if not user:
            await update.message.reply_text("⚠️ Нажми /start")
            return
        
        remaining = self.db.get_remaining_requests(user_id)
        if remaining <= 0:
            keyboard = [[InlineKeyboardButton("⭐ Купить Premium", callback_data="upgrade")]]
            await update.message.reply_text(
                "❌ Лимит исчерпан! /upgrade для безлимита",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Проверка длины сообщения
        if len(message_text) > 2000:
            await update.message.reply_text(
                "⚠️ Слишком длинное сообщение!\n"
                "Попробуй написать короче (до 2000 символов) 📝"
            )
            return
        
        await update.message.chat.send_action("typing")
        
        try:
            history = self.db.get_conversation_history(user_id)
            
            # 🔥 Генерация ответа
            user_plan = user['plan']
            ai_response = self.gemini.generate_response(message_text, history, user_plan)
            
            # Проверка на ошибку
            if not ai_response or "😔" in ai_response[:10]:
                # Это сообщение об ошибке, отправляем как есть
                await update.message.reply_text(ai_response)
                return
            
            # Нормальный ответ - форматируем
            ai_response = clean_response(ai_response)
            formatted = format_code(ai_response)
            chunks = split_message(formatted)
            
            for chunk in chunks:
                try:
                    await update.message.reply_text(
                        chunk,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                except:
                    # Если Markdown не работает
                    await update.message.reply_text(chunk)
            
            # Сохраняем в историю только успешные ответы
            self.db.save_message(user_id, 'user', message_text)
            self.db.save_message(user_id, 'assistant', ai_response)
            
            # Уменьшаем лимит
            if user['plan'] in ['free', 'pro']:
                self.db.use_request(user_id)
                remaining = self.db.get_remaining_requests(user_id)
                if remaining <= 3 and remaining > 0:
                    await update.message.reply_text(
                        f"⚠️ Осталось: {remaining} запросов",
                        disable_notification=True
                    )
        
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
            await update.message.reply_text(
                "😔 Произошла ошибка. Попробуй:\n"
                "1️⃣ /clear - очистить историю\n"
                "2️⃣ Написать короче\n"
                "3️⃣ Подождать минуту"
            )
    
    # ⚽ ФУТБОЛЬНЫЕ КОМАНДЫ
    
    async def player_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /player - статистика из знаний Gemini"""
        if not context.args:
            await update.message.reply_text("⚽ Использование: /player Месси")
            return
        
        player_name = " ".join(context.args)
        prompt = f"""⚽ Расскажи о футболисте {player_name}:

📊 Основная информация:
- Полное имя и возраст
- Текущий клуб и позиция
- Номер на майке

⚽ Статистика карьеры (используй последние известные данные):
- Голы и ассисты
- Достижения и трофеи
- Клубы в карьере

💰 Дополнительно:
- Примерная трансферная стоимость
- Сильные стороны

⚠️ Если данные могут быть неточными - уточни это!"""
        
        update.message.text = prompt
        await self.handle_message(update, context)
    
    async def club_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /club - информация о клубе"""
        if not context.args:
            await update.message.reply_text("⚽ Использование: /club Реал Мадрид")
            return
        
        club_name = " ".join(context.args)
        prompt = f"""⚽ Расскажи о клубе {club_name}:

🏟️ Основная информация:
- Страна и лига
- Домашний стадион
- Год основания

👥 Команда:
- Главный тренер
- Звёзды состава (топ-5 игроков)
- Капитан команды

🏆 Достижения:
- Главные трофеи
- Недавние успехи

⚠️ Используй последние известные данные, если что-то могло измениться - уточни!"""
        
        update.message.text = prompt
        await self.handle_message(update, context)
    
    async def compare_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /compare - сравнение игроков"""
        if len(context.args) < 3 or "vs" not in " ".join(context.args).lower():
            await update.message.reply_text("⚽ Использование: /compare Месси vs Роналду")
            return
        
        text = " ".join(context.args)
        players = text.lower().split("vs")
        
        if len(players) != 2:
            await update.message.reply_text("⚽ Формат: /сравнить Игрок1 vs Игрок2")
            return
        
        p1, p2 = players[0].strip(), players[1].strip()
        prompt = f"""⚽ СРАВНИ футболистов:

🔵 {p1.upper()}  VS  🔴 {p2.upper()}

📊 Сравнение по параметрам:

1️⃣ Статистика карьеры
   - Голы и ассисты
   - Матчи сыграно

2️⃣ Трофеи и достижения
   - Командные титулы
   - Личные награды (Золотые мячи и т.д.)

3️⃣ Навыки
   - Сильные стороны каждого
   - Стиль игры

4️⃣ Рыночная стоимость
   - Примерная стоимость

🎯 Вывод: Кто лучше и почему?

⚠️ Используй известные данные, если что-то неточно - укажи!"""
        
        update.message.text = prompt
        await self.handle_message(update, context)
    
    async def match_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /match - информация о матче"""
        if len(context.args) < 3:
            await update.message.reply_text("⚽ Использование: /match Реал vs Барса")
            return
        
        text = " ".join(context.args)
        prompt = f"""⚽ Расскажи о матче {text}:

📊 История противостояния:
- Статистика личных встреч (примерная)
- Самые запоминающиеся матчи
- Кто чаще побеждает

⚡ О командах:
- Текущая форма (если знаешь)
- Ключевые игроки обеих сторон
- Сильные и слабые стороны

🎯 Интересные факты:
- Рекорды в матчах друг против друга
- Известные игроки игравшие за обе команды

⚠️ Используй известные данные!"""
        
        update.message.text = prompt
        await self.handle_message(update, context)
    
    async def prediction_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /predict - прогноз на матч"""
        if not context.args:
            await update.message.reply_text("⚽ Использование: /predict Реал vs Барса")
            return
        
        match = " ".join(context.args)
        prompt = f"""⚽ Дай прогноз на матч {match}:

📊 Анализ команд:
- Общий уровень команд
- Форма (если известна)
- Ключевые игроки
- История встреч

🎯 Прогноз:
- Примерный счёт (2-3 варианта)
- Вероятный исход (победа команды А, ничья, победа команды Б)
- Ключевые факторы, которые могут повлиять

⚡ Ставки (развлекательно):
- На что можно поставить
- Какие события вероятны (голы, карточки)

⚠️ Это развлекательный прогноз на основе общих знаний!
Для точных данных проверяй свежую статистику перед матчем!"""
        
        update.message.text = prompt
        await self.handle_message(update, context)
    
    # ОСТАЛЬНЫЕ КОМАНДЫ
    
    async def promo_activate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Активация промокода"""
        user_id = update.effective_user.id
        
        if not context.args:
            await update.message.reply_text("🎁 Формат: /promo КОД")
            return
        
        promo_code = context.args[0].upper()
        result = self.db.activate_promocode(user_id, promo_code)
        
        if result['success']:
            promo = result['promo']
            msg = "🎉 Промокод активирован!\n\n"
            
            if promo['type'] == 'vip':
                msg += "💎 VIP Навсегда"
            elif promo['type'] == 'premium':
                msg += f"⭐ Premium {promo['days']} дней"
            elif promo['type'] == 'pro':
                msg += f"🔥 PRO {promo['days']} дней"
            elif promo['type'] == 'requests':
                msg += f"📊 +{promo['requests']} запросов"
            
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(f"❌ {result['error']}")
    
    async def upgrade(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Меню покупки с PRO"""
        keyboard = [
            [InlineKeyboardButton(f"🔥 PRO 30 дней - ${PREMIUM_PRICES['pro_30']}", callback_data="buy_pro_30")],
            [InlineKeyboardButton(f"🔥 PRO 90 дней - ${PREMIUM_PRICES['pro_90']}", callback_data="buy_pro_90")],
            [InlineKeyboardButton(f"⭐ Premium 30 дней - ${PREMIUM_PRICES[30]}", callback_data="buy_premium_30")],
            [InlineKeyboardButton(f"⭐ Premium 90 дней - ${PREMIUM_PRICES[90]}", callback_data="buy_premium_90")],
            [InlineKeyboardButton(f"💎 VIP Навсегда - ${PREMIUM_PRICES['vip']}", callback_data="buy_vip")],
        ]
        
        text = """💰 ТАРИФНЫЕ ПЛАНЫ

🆓 FREE
• 10 запросов в день
• Базовая скорость

🔥 PRO (новый!)
• 20 запросов в день
• Быстрая скорость
• Доступная цена

⭐ PREMIUM
• ♾️ Безлимитные запросы
• ⚡ Максимальная скорость
• 🧠 Gemini 2.0 Flash

💎 VIP (лучший!)
• Всё из Premium
• ⏰ НАВСЕГДА
• 🎯 Эксклюзивно

Выбери план:"""
        
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user:
            await update.message.reply_text("⚠️ /start")
            return
        
        stats = self.db.get_user_stats(user_id)
        remaining = self.db.get_remaining_requests(user_id)
        
        text = f"""📊 Статистика

👤 ID: {user_id}
📝 Тариф: {user['plan'].upper()}
💬 Сообщений: {stats['total_messages']}
📊 Осталось: {remaining if user['plan'] in ['free', 'pro'] else '∞'}"""
        
        await update.message.reply_text(text)
    
    async def clear_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Очистка истории"""
        user_id = update.effective_user.id
        self.db.clear_history(user_id)
        await update.message.reply_text("🗑️ История очищена!")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопок"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "promo":
            await query.message.reply_text("🎁 Формат: /promo КОД")
        
        elif query.data == "upgrade":
            keyboard = [
                [InlineKeyboardButton(f"🔥 PRO 30 дней - ${PREMIUM_PRICES['pro_30']}", callback_data="buy_pro_30")],
                [InlineKeyboardButton(f"🔥 PRO 90 дней - ${PREMIUM_PRICES['pro_90']}", callback_data="buy_pro_90")],
                [InlineKeyboardButton(f"⭐ Premium 30 - ${PREMIUM_PRICES[30]}", callback_data="buy_premium_30")],
                [InlineKeyboardButton(f"⭐ Premium 90 - ${PREMIUM_PRICES[90]}", callback_data="buy_premium_90")],
                [InlineKeyboardButton(f"💎 VIP - ${PREMIUM_PRICES['vip']}", callback_data="buy_vip")],
            ]
            
            text = """💰 ТАРИФЫ

🆓 FREE: 10/день
🔥 PRO: 20/день
⭐ PREMIUM: безлимит
💎 VIP: навсегда"""
            
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif query.data == "stats":
            user_id = query.from_user.id
            user = self.db.get_user(user_id)
            
            if user:
                stats = self.db.get_user_stats(user_id)
                remaining = self.db.get_remaining_requests(user_id)
                
                text = f"""📊 Статистика

👤 ID: {user_id}
📝 Тариф: {user['plan'].upper()}
💬 Сообщений: {stats['total_messages']}
📊 Осталось: {remaining if user['plan'] in ['free', 'pro'] else '∞'}"""
                
                await query.message.reply_text(text)
        
        elif query.data == "football":
            text = """⚽ ФУТБОЛЬНЫЕ КОМАНДЫ

/player [имя] - статистика
/club [название] - инфо о клубе  
/compare [игрок1] vs [игрок2]
/match [клуб1] vs [клуб2]
/predict [матч] - прогноз

Примеры:
/player Месси
/compare Месси vs Роналду
/predict Реал vs Барса"""
            
            await query.message.reply_text(text)
        
        elif query.data == "help":
            text = """ℹ️ ПОМОЩЬ

🔧 Команды:
/start - главное меню
/promo КОД - промокод
/upgrade - купить премиум
/stats - статистика
/clear - очистить историю

⚽ Футбол:
/player [имя]
/club [название]
/compare [А] vs [Б]
/match [А] vs [Б]
/predict [матч]

💬 Просто пиши вопросы!"""
            
            await query.message.reply_text(text)
        
        elif query.data.startswith("buy_"):
            await query.message.reply_text(
                "💳 Для покупки:\n@твой_админ\n\n"
                "Или промокод: /promo КОД"
            )