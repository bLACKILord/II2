# utils/chunker.py - разбивка длинных сообщений
import re

MAX_MESSAGE_LENGTH = 4096  # лимит Telegram


def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list:
    """
    Разбивает длинное сообщение на части по 4096 символов
    
    Старается разбивать по параграфам или предложениям
    
    Args:
        text: текст для разбивки
        max_length: максимальная длина одного сообщения
    
    Returns:
        list: список частей текста
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Разбиваем по параграфам
    paragraphs = text.split('\n\n')
    
    for paragraph in paragraphs:
        # Если параграф слишком длинный, разбиваем по предложениям
        if len(paragraph) > max_length:
            sentences = re.split(r'(?<=[.!?])\s+', paragraph)
            
            for sentence in sentences:
                # Если предложение слишком длинное, режем принудительно
                if len(sentence) > max_length:
                    for i in range(0, len(sentence), max_length - 100):
                        chunk = sentence[i:i + max_length - 100]
                        chunks.append(chunk)
                    continue
                
                if len(current_chunk) + len(sentence) + 1 <= max_length:
                    current_chunk += sentence + " "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + " "
        
        else:
            # Добавляем параграф целиком
            if len(current_chunk) + len(paragraph) + 2 <= max_length:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"
    
    # Добавляем последний chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


def split_by_code_blocks(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list:
    """
    Разбивка с учётом блоков кода
    
    Гарантирует, что блоки кода не будут разорваны
    """
    chunks = []
    current = ""
    
    # Найти все блоки кода
    code_blocks = re.finditer(r'```[\w]*\n.*?```', text, re.DOTALL)
    last_end = 0
    
    for match in code_blocks:
        # Текст до блока кода
        before = text[last_end:match.start()]
        code_block = match.group()
        
        # Если текст + код влезает
        if len(current + before + code_block) <= max_length:
            current += before + code_block
        else:
            # Сохраняем текущий chunk
            if current + before:
                chunks.append((current + before).strip())
            current = code_block
        
        last_end = match.end()
    
    # Оставшийся текст
    remaining = text[last_end:]
    if len(current + remaining) <= max_length:
        chunks.append((current + remaining).strip())
    else:
        if current:
            chunks.append(current.strip())
        if remaining:
            chunks.extend(split_message(remaining, max_length))
    
    return [c for c in chunks if c]