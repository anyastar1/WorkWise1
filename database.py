# database.py - ИСПРАВЛЕННЫЙ И ДОПОЛНЕННЫЙ КОД ДЛЯ MVP

from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import hashlib
import json 
import os
import uuid 

# --- 1. Инициализация базы данных ---
DATABASE_URL = "sqlite:///workwise.db"
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# --- 2. Модели (Таблицы) ---

# 2.1. Company
class Company(Base):
    __tablename__ = 'companies'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    corporate_email = Column(String(120), unique=True, nullable=False)
    keys = relationship("KeyCompany", back_populates="company")
    users = relationship("User", back_populates="company")
    def __repr__(self): return f"<Company(name='{self.name}')>"

# 2.2. KeyCompany
class KeyCompany(Base):
    __tablename__ = 'key_companies'
    id = Column(Integer, primary_key=True)
    key_value = Column(String(50), unique=True, nullable=False)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    is_active = Column(Boolean, default=True)
    company = relationship("Company", back_populates="keys")

# 2.3. GOST (Стандарты)
class GOST(Base):
    __tablename__ = 'gosts'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)  # Добавлено описание ГОСТа
    file_path = Column(String(255), nullable=True)  # Путь к файлу ГОСТа (опционально)
    client_type_for = Column(String(10), nullable=False)  # 'all' или 'company'

# 2.4. User
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    login = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    client_type = Column(String(10), nullable=False)  # 'private' или 'company'
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True)
    activity_type = Column(String(100), nullable=True)  # Студент, Инженер и т.д.

    company = relationship("Company", back_populates="users")
    uploads = relationship("UserUpload", back_populates="user", order_by="UserUpload.upload_date.desc()")
    
    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        
    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode('utf-8')).hexdigest()

# 2.5. UserUpload (Загруженные работы)
class UserUpload(Base):
    __tablename__ = 'user_uploads'
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)  # Сохраненное уникальное имя файла
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    gost_id = Column(Integer, ForeignKey('gosts.id'), nullable=True)
    status = Column(String(50), default='Ожидает проверки')
    upload_date = Column(DateTime, default=datetime.now)
    report_json = Column(Text, nullable=True)  # Поле для хранения отчета в формате JSON

    user = relationship("User", back_populates="uploads")
    gost = relationship("GOST")


# --- 3. Управление сессиями ---
Session = sessionmaker(bind=engine)

def get_session():
    """Возвращает новую сессию для работы с БД."""
    return Session()


def initialize_database():
    """УДАЛЯЕТ СТАРУЮ БД (для гарантированного MVP) и инициализирует новую с тестовыми данными."""
    global engine, Session
    
    # Удаляем старый файл БД, если он есть
    db_file_path = "workwise.db"
    if os.path.exists(db_file_path):
        print(f"Обнаружен старый файл БД '{db_file_path}'. Удаляю для чистого старта MVP...")
        try:
            os.remove(db_file_path)
            # Пересоздаем engine и Session
            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)
        except OSError as e:
            print(f"Ошибка при удалении файла БД: {e}. Возможно, он заблокирован.")
            
    print("Проверка/создание базы данных и таблиц...")
    Base.metadata.create_all(engine)
    
    session = Session()
    
    # Проверяем, есть ли тестовые данные
    if session.query(User).count() == 0:
        print("Заполнение базы данных тестовыми данными...")
        
        # 1. Тестовая компания
        comp_a = Company(name='TechSolutions', corporate_email='@techsol.com')
        session.add(comp_a)
        session.commit()
        
        # 2. Тестовые ключи для компании
        session.add(KeyCompany(key_value='COMPANYKEY123', company_id=comp_a.id, is_active=True))
        session.commit()
        
        # 3. Тестовые ГОСТы - ОБНОВЛЕНО: добавлен второй ГОСТ
        gost_bibliography = GOST(
            name='ГОСТ Р 7.0.5-2008 (Библиографические ссылки)',
            description='Проверка оформления библиографических ссылок и списка литературы. '
                        'Анализирует правильность оформления ссылок на книги, статьи, '
                        'электронные ресурсы, диссертации и другие источники.',
            file_path='gost_7.0.5.pdf',
            client_type_for='all'
        )
        
        gost_report = GOST(
            name='ГОСТ 7.32-2001 (Оформление отчёта о НИР)',
            description='Проверка структуры и оформления документа: реферат, титульный лист, '
                        'ключевые слова, содержание. Анализирует наличие обязательных элементов '
                        'и их соответствие требованиям стандарта.',
            file_path='gost_7.32.pdf',
            client_type_for='all'
        )
        
        gost_corporate = GOST(
            name='Корпоративный стандарт TechSolutions',
            description='Внутренний стандарт оформления документации компании TechSolutions.',
            file_path='corp_std_1.pdf',
            client_type_for='company'
        )
        
        session.add_all([gost_bibliography, gost_report, gost_corporate])
        session.commit()
        
        # Получаем ID для связей
        gost_id_1 = session.query(GOST.id).filter_by(name='ГОСТ Р 7.0.5-2008 (Библиографические ссылки)').one()[0]
        comp_a_id = session.query(Company.id).filter_by(name='TechSolutions').one()[0]

        # 4. Добавление тестовых пользователей
        user_private = User(
            login='private_user', 
            email='private@mail.com', 
            client_type='private', 
            activity_type='Student'
        )
        user_private.set_password('1234567890')
        
        user_company = User(
            login='company_user', 
            email='company@techsol.com', 
            client_type='company', 
            company_id=comp_a_id, 
            activity_type='Engineer'
        )
        user_company.set_password('1234567890')
        
        session.add_all([user_private, user_company])
        session.commit()

        # 5. Добавление тестовой загрузки для демонстрации
        user_private_obj = session.query(User).filter_by(login='private_user').one()
        
        test_report = json.dumps({
            "version": 1, 
            "errors": [
                "Заголовок не по центру (п. 2.1)", 
                "Отсутствует нумерация страниц (п. 4.5)", 
                "Размер шрифта не соответствует ГОСТу (п. 1.2)"
            ], 
            "ai_recommendation": "Сосредоточьтесь на оформлении титульного листа и правилах цитирования."
        }, ensure_ascii=False)

        session.add(UserUpload(
            filename='Test_Laba_v1.docx', 
            file_path=os.path.join("uploads", str(uuid.uuid4()) + ".docx"), 
            user_id=user_private_obj.id, 
            gost_id=gost_id_1, 
            status='Проверено',
            report_json=test_report, 
            upload_date=datetime.now()
        ))
        session.commit()
        
        print("База данных успешно заполнена тестовыми данными.")
        print("-" * 50)
        print("Доступные стандарты ГОСТ:")
        print("  1. ГОСТ Р 7.0.5-2008 - Библиографические ссылки")
        print("  2. ГОСТ 7.32-2001 - Оформление отчёта о НИР")
        print("  3. Корпоративный стандарт (только для company)")
        print("-" * 50)
        print("Тестовые аккаунты:")
        print("  Private: private_user / 1234567890")
        print("  Company: company_user / 1234567890 (Ключ: COMPANYKEY123)")
        print("-" * 50)

    session.close()


# Для тестирования модуля напрямую
if __name__ == "__main__":
    initialize_database()