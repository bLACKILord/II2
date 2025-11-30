# admin.py - админ панель с PRO тарифом
from firebase_service import DatabaseService
from config import ADMIN_IDS
import random
import string

db = DatabaseService()


def generate_random_code(length=8):
    """Генерация случайного промокода"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def create_vip_promocode(code=None, uses=1):
    """Создать VIP промокод (навсегда)"""
    if not code:
        code = f"VIP-{generate_random_code(6)}"
    
    db.create_promocode(code, 'vip', uses=uses)
    print(f"✅ VIP промокод создан: {code}")
    print(f"   Использований: {uses}")
    return code


def create_premium_promocode(days, code=None, uses=1):
    """Создать Premium промокод"""
    if not code:
        code = f"PREMIUM-{days}-{generate_random_code(4)}"
    
    db.create_promocode(code, 'premium', days=days, uses=uses)
    print(f"✅ Premium промокод создан: {code}")
    print(f"   Срок: {days} дней")
    print(f"   Использований: {uses}")
    return code


def create_pro_promocode(days, code=None, uses=1):
    """🔥 Создать PRO промокод (20 запросов/день)"""
    if not code:
        code = f"PRO-{days}-{generate_random_code(4)}"
    
    db.create_promocode(code, 'pro', days=days, uses=uses)
    print(f"✅ PRO промокод создан: {code}")
    print(f"   Срок: {days} дней")
    print(f"   Лимит: 20 запросов/день")
    print(f"   Использований: {uses}")
    return code


def create_requests_promocode(requests, code=None, uses=1):
    """Создать промокод на запросы"""
    if not code:
        code = f"REQ-{requests}-{generate_random_code(4)}"
    
    db.create_promocode(code, 'requests', requests=requests, uses=uses)
    print(f"✅ Промокод на запросы создан: {code}")
    print(f"   Запросов: +{requests}")
    print(f"   Использований: {uses}")
    return code


def admin_menu():
    """Админ панель с PRO"""
    print("\n" + "="*50)
    print("🔧 АДМИН ПАНЕЛЬ - СОЗДАНИЕ ПРОМОКОДОВ")
    print("="*50)
    
    while True:
        print("\n1. VIP промокод (навсегда, безлимит)")
        print("2. Premium промокод (безлимит на дни)")
        print("3. PRO промокод (20 запросов/день)")  # 🔥 НОВЫЙ
        print("4. Промокод на запросы")
        print("5. Массовое создание")
        print("0. Выход")
        
        choice = input("\nВыбери: ").strip()
        
        if choice == "1":
            print("\n--- VIP ---")
            code = input("Код (Enter = авто): ").strip().upper() or None
            uses = int(input("Использований: ") or 1)
            create_vip_promocode(code, uses)
        
        elif choice == "2":
            print("\n--- Premium ---")
            days = int(input("Дней (30/90): "))
            code = input("Код (Enter = авто): ").strip().upper() or None
            uses = int(input("Использований: ") or 1)
            create_premium_promocode(days, code, uses)
        
        elif choice == "3":  # 🔥 НОВЫЙ PRO
            print("\n--- PRO (20 запросов/день) ---")
            days = int(input("Дней (30/90): "))
            code = input("Код (Enter = авто): ").strip().upper() or None
            uses = int(input("Использований: ") or 1)
            create_pro_promocode(days, code, uses)
        
        elif choice == "4":
            print("\n--- Запросы ---")
            requests = int(input("Количество: "))
            code = input("Код (Enter = авто): ").strip().upper() or None
            uses = int(input("Использований: ") or 1)
            create_requests_promocode(requests, code, uses)
        
        elif choice == "5":
            print("\n--- Массовое ---")
            promo_type = input("Тип (vip/premium/pro/requests): ").lower()
            count = int(input("Количество: "))
            uses = int(input("Использований каждого: "))
            
            if promo_type == "vip":
                for _ in range(count):
                    create_vip_promocode(uses=uses)
            
            elif promo_type == "premium":
                days = int(input("Дней: "))
                for _ in range(count):
                    create_premium_promocode(days, uses=uses)
            
            elif promo_type == "pro":  # 🔥 НОВЫЙ
                days = int(input("Дней: "))
                for _ in range(count):
                    create_pro_promocode(days, uses=uses)
            
            elif promo_type == "requests":
                requests = int(input("Запросов: "))
                for _ in range(count):
                    create_requests_promocode(requests, uses=uses)
        
        elif choice == "0":
            print("\n👋 Пока!")
            break
        
        else:
            print("❌ Неверный выбор")


if __name__ == "__main__":
    admin_menu()