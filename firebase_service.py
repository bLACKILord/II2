# firebase_service.py - база данных с поддержкой PRO тарифа
import sqlite3
from datetime import datetime, timedelta
from config import DATABASE_PATH, FREE_DAILY_LIMIT, PRO_DAILY_LIMIT, MAX_HISTORY
import logging

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self):
        """Инициализация базы данных"""
        self.db_path = DATABASE_PATH
        self._init_database()
    
    def _init_database(self):
        """Создание таблиц"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                plan TEXT DEFAULT 'free',
                premium_expires TEXT,
                daily_requests INTEGER DEFAULT 0,
                last_request_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица промокодов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                type TEXT,
                days INTEGER,
                requests INTEGER,
                uses_left INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица использованных промокодов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS used_promocodes (
                user_id INTEGER,
                code TEXT,
                used_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, code)
            )
        """)
        
        # Таблица истории диалогов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована")
    
    # ========================================
    # ПОЛЬЗОВАТЕЛИ
    # ========================================
    
    def get_user(self, user_id: int):
        """Получить пользователя"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        return dict(user) if user else None
    
    def create_user(self, user_id: int, username: str):
        """Создать пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, last_request_date, daily_requests)
            VALUES (?, ?, ?, 0)
        """, (user_id, username, today))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Новый пользователь: {user_id}")
    
    def update_user_plan(self, user_id: int, plan: str, days: int = None):
        """Обновить тарифный план (с поддержкой PRO)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if plan == 'vip':
            cursor.execute("""
                UPDATE users SET plan = 'vip', premium_expires = NULL
                WHERE user_id = ?
            """, (user_id,))
        
        elif plan in ['premium', 'pro'] and days:  # 🔥 PRO добавлен
            expires = (datetime.now() + timedelta(days=days)).isoformat()
            cursor.execute("""
                UPDATE users SET plan = ?, premium_expires = ?
                WHERE user_id = ?
            """, (plan, expires, user_id))
        
        else:
            cursor.execute("""
                UPDATE users SET plan = 'free', premium_expires = NULL
                WHERE user_id = ?
            """, (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_remaining_requests(self, user_id: int) -> int:
        """Получить оставшиеся запросы (с поддержкой PRO)"""
        user = self.get_user(user_id)
        if not user:
            return 0
        
        plan = user['plan']
        
        # VIP - бесконечно
        if plan == 'vip':
            return 999999
        
        # Premium - проверяем срок
        if plan == 'premium':
            if user['premium_expires']:
                expires = datetime.fromisoformat(user['premium_expires'])
                if expires > datetime.now():
                    return 999999
                else:
                    self.update_user_plan(user_id, 'free')
        
        # 🔥 PRO - 20 запросов/день
        if plan == 'pro':
            if user['premium_expires']:
                expires = datetime.fromisoformat(user['premium_expires'])
                if expires > datetime.now():
                    # Проверяем дневной лимит PRO
                    today = datetime.now().strftime("%Y-%m-%d")
                    if user['last_request_date'] != today:
                        self._reset_daily_requests(user_id)
                        return PRO_DAILY_LIMIT
                    return max(0, PRO_DAILY_LIMIT - user['daily_requests'])
                else:
                    self.update_user_plan(user_id, 'free')
        
        # FREE - 10 запросов/день
        today = datetime.now().strftime("%Y-%m-%d")
        if user['last_request_date'] != today:
            self._reset_daily_requests(user_id)
            return FREE_DAILY_LIMIT
        
        return max(0, FREE_DAILY_LIMIT - user['daily_requests'])
    
    def _reset_daily_requests(self, user_id: int):
        """Сброс дневного счётчика"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            UPDATE users SET daily_requests = 0, last_request_date = ?
            WHERE user_id = ?
        """, (today, user_id))
        
        conn.commit()
        conn.close()
    
    def use_request(self, user_id: int):
        """Использовать один запрос"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users SET daily_requests = daily_requests + 1
            WHERE user_id = ?
        """, (user_id,))
        
        conn.commit()
        conn.close()
    
    # ========================================
    # ПРОМОКОДЫ
    # ========================================
    
    def create_promocode(self, code: str, promo_type: str, days: int = None, 
                        requests: int = None, uses: int = 1):
        """Создать промокод"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO promocodes (code, type, days, requests, uses_left)
            VALUES (?, ?, ?, ?, ?)
        """, (code.upper(), promo_type, days, requests, uses))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Промокод создан: {code}")
    
    def activate_promocode(self, user_id: int, code: str):
        """Активировать промокод (с поддержкой PRO)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        code = code.upper()
        
        cursor.execute("SELECT * FROM promocodes WHERE code = ?", (code,))
        promo = cursor.fetchone()
        
        if not promo:
            conn.close()
            return {"success": False, "error": "Промокод не найден"}
        
        cursor.execute("SELECT * FROM used_promocodes WHERE user_id = ? AND code = ?", 
                      (user_id, code))
        if cursor.fetchone():
            conn.close()
            return {"success": False, "error": "Уже использован"}
        
        if promo['uses_left'] <= 0:
            conn.close()
            return {"success": False, "error": "Промокод исчерпан"}
        
        # Активация
        if promo['type'] == 'vip':
            self.update_user_plan(user_id, 'vip')
        
        elif promo['type'] == 'premium':
            self.update_user_plan(user_id, 'premium', promo['days'])
        
        elif promo['type'] == 'pro':  # 🔥 НОВЫЙ PRO
            self.update_user_plan(user_id, 'pro', promo['days'])
        
        elif promo['type'] == 'requests':
            cursor.execute("UPDATE users SET daily_requests = daily_requests - ? WHERE user_id = ?", 
                          (promo['requests'], user_id))
        
        cursor.execute("INSERT INTO used_promocodes (user_id, code) VALUES (?, ?)", 
                      (user_id, code))
        cursor.execute("UPDATE promocodes SET uses_left = uses_left - 1 WHERE code = ?", 
                      (code,))
        
        conn.commit()
        conn.close()
        
        return {"success": True, "promo": dict(promo)}
    
    # ========================================
    # ИСТОРИЯ ДИАЛОГОВ
    # ========================================
    
    def save_message(self, user_id: int, role: str, content: str):
        """Сохранить сообщение"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO conversations (user_id, role, content)
            VALUES (?, ?, ?)
        """, (user_id, role, content))
        
        conn.commit()
        conn.close()
    
    def get_conversation_history(self, user_id: int, limit: int = MAX_HISTORY):
        """Получить историю"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT role, content FROM conversations
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit))
        
        messages = cursor.fetchall()
        conn.close()
        
        return [(msg['role'], msg['content']) for msg in reversed(messages)]
    
    def clear_history(self, user_id: int):
        """Очистить историю"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        
        conn.commit()
        conn.close()
        logger.info(f"🗑️ История очищена для {user_id}")
    
    def get_user_stats(self, user_id: int):
        """Статистика"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as total FROM conversations
            WHERE user_id = ? AND role = 'user'
        """, (user_id,))
        
        total = cursor.fetchone()[0]
        conn.close()
        
        return {"total_messages": total}