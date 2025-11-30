# gemini_api.py - с улучшенной обработкой ошибок
import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL, BOT_PERSONALITY, MAX_MESSAGE_LENGTH
import logging
import time

logger = logging.getLogger(__name__)


class GeminiAPI:
    def __init__(self):
        """Инициализация Gemini"""
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Настройки генерации
        generation_config = {
            "temperature": 0.9,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        
        # Создаём модель
        self.model = genai.GenerativeModel(
            GEMINI_MODEL,
            generation_config=generation_config
        )
        
        # Системный промпт
        self.system_prompt = "\n".join(BOT_PERSONALITY)
        logger.info(f"✅ Gemini API инициализирован (модель: {GEMINI_MODEL})")
    
    def generate_response(self, message: str, history: list = None, user_plan: str = "free") -> str:
        """
        Генерация ответа с retry логикой
        
        Args:
            message: сообщение пользователя
            history: история диалога [(role, content), ...]
            user_plan: тарифный план
        
        Returns:
            str: ответ AI
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Формируем контекст
                full_context = self._build_context(message, history, user_plan)
                
                logger.info(f"📝 Попытка {attempt + 1}/{max_retries} - Запрос к Gemini")
                
                # Генерация с таймаутом
                response = self.model.generate_content(
                    full_context,
                    request_options={'timeout': 30}
                )
                
                if not response or not response.text:
                    logger.warning(f"⚠️ Пустой ответ на попытке {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return "😔 Не смог сгенерировать ответ. Попробуй /clear и напиши снова!"
                
                ai_response = response.text.strip()
                
                # Очистка артефактов
                ai_response = self._clean_response(ai_response)
                
                # Обрезка
                if len(ai_response) > MAX_MESSAGE_LENGTH:
                    ai_response = ai_response[:MAX_MESSAGE_LENGTH] + "\n\n...(обрезано)"
                
                logger.info(f"✅ Ответ получен (длина: {len(ai_response)})")
                return ai_response
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Ошибка на попытке {attempt + 1}: {error_msg}")
                
                # Проверяем тип ошибки
                if "429" in error_msg or "quota" in error_msg.lower():
                    return "😔 Превышен лимит запросов к Gemini API. Попробуй через минуту! ⏰"
                
                elif "404" in error_msg:
                    return f"😔 Модель {GEMINI_MODEL} не найдена. Проверь config.py!"
                
                elif "timeout" in error_msg.lower():
                    logger.warning(f"⏱️ Таймаут на попытке {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return "😔 Превышено время ожидания. Попробуй /clear или напиши короче!"
                
                # Если не последняя попытка - пробуем снова
                if attempt < max_retries - 1:
                    logger.info(f"🔄 Повтор через {retry_delay} сек...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Увеличиваем задержку
                    continue
        
        # Все попытки исчерпаны
        logger.error(f"❌ Все {max_retries} попытки исчерпаны")
        return "😔 Ошибка после 3 попыток. Попробуй:\n1️⃣ /clear - очистить историю\n2️⃣ Написать короче\n3️⃣ Подождать минуту"
    
    def _build_context(self, message: str, history: list, user_plan: str) -> str:
        """Формирование контекста для Gemini"""
        full_context = f"{self.system_prompt}\n\n"
        full_context += f"[ИНФОРМАЦИЯ: Тариф '{user_plan}']\n\n"
        
        # Добавляем историю (только последние сообщения)
        if history and len(history) > 0:
            full_context += "=== История ===\n"
            for role, content in history[-4:]:  # Берём только 4 последних
                if role == "user":
                    full_context += f"👤: {content[:200]}\n"  # Обрезаем длинные сообщения
                else:
                    full_context += f"🤖: {content[:200]}\n"
            full_context += "=== Конец ===\n\n"
        
        # Текущее сообщение
        full_context += f"👤: {message}\n🤖:"
        
        return full_context
    
    def _clean_response(self, text: str) -> str:
        """Очистка ответа от артефактов"""
        text = text.replace("🤖 Ассистент:", "").strip()
        text = text.replace("Ассистент:", "").strip()
        text = text.replace("🤖:", "").strip()
        return text
    
    def test_connection(self) -> bool:
        """Тест подключения"""
        try:
            response = self.model.generate_content(
                "Скажи привет",
                request_options={'timeout': 10}
            )
            return response and response.text is not None
        except Exception as e:
            logger.error(f"❌ Ошибка подключения: {e}")
            return False