# database.py - Модуль базы данных для авторизации

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
import hashlib
import os

# --- 1. Инициализация базы данных ---
DATABASE_URL = "sqlite:///workwise.db"
engine = create_engine(DATABASE_URL)
Base = declarative_base()


# --- 2. Модели (Таблицы) ---

class Company(Base):
    """Модель компании"""
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    corporate_email = Column(String(120), unique=True, nullable=False)
    keys = relationship("KeyCompany", back_populates="company")
    users = relationship("User", back_populates="company")

    def __repr__(self):
        return f"<Company(name='{self.name}')>"


class KeyCompany(Base):
    """Модель ключа компании для регистрации сотрудников"""
    __tablename__ = "key_companies"
    id = Column(Integer, primary_key=True)
    key_value = Column(String(50), unique=True, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    company = relationship("Company", back_populates="keys")


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    login = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    client_type = Column(String(10), nullable=False)  # 'private' или 'company'
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    activity_type = Column(String(100), nullable=True)  # Студент, Инженер и т.д.

    company = relationship("Company", back_populates="users")

    def set_password(self, password):
        """Установка пароля с хешированием"""
        self.password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    def check_password(self, password):
        """Проверка пароля"""
        return self.password_hash == hashlib.sha256(password.encode("utf-8")).hexdigest()


# --- 3. Управление сессиями ---
Session = sessionmaker(bind=engine)


def get_session():
    """Возвращает новую сессию для работы с БД."""
    return Session()


def initialize_database():
    """Инициализирует базу данных и создаёт тестовые данные при необходимости."""
    global engine, Session

    # Удаляем старый файл БД, если он есть
    db_file_path = "workwise.db"
    if os.path.exists(db_file_path):
        print(f"Обнаружен старый файл БД '{db_file_path}'. Удаляю для чистого старта...")
        try:
            os.remove(db_file_path)
            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)
        except OSError as e:
            print(f"Ошибка при удалении файла БД: {e}. Возможно, он заблокирован.")

    print("Создание базы данных и таблиц...")
    Base.metadata.create_all(engine)

    session = Session()

    # Проверяем, есть ли тестовые данные
    if session.query(User).count() == 0:
        print("Заполнение базы данных тестовыми данными...")

        # 1. Тестовая компания
        comp_a = Company(name="TechSolutions", corporate_email="@techsol.com")
        session.add(comp_a)
        session.commit()

        # 2. Тестовые ключи для компании
        session.add(
            KeyCompany(key_value="COMPANYKEY123", company_id=comp_a.id, is_active=True)
        )
        session.commit()

        comp_a_id = session.query(Company.id).filter_by(name="TechSolutions").one()[0]

        # 3. Тестовые пользователи
        user_private = User(
            login="private_user",
            email="private@mail.com",
            client_type="private",
            activity_type="Student",
        )
        user_private.set_password("1234567890")

        user_company = User(
            login="company_user",
            email="company@techsol.com",
            client_type="company",
            company_id=comp_a_id,
            activity_type="Engineer",
        )
        user_company.set_password("1234567890")

        test_user = User(
            login="test",
            email="test@test.ru",
            client_type="company",
            company_id=comp_a_id,
            activity_type="Engineer",
        )
        test_user.set_password("12345678")

        session.add_all([user_private, user_company, test_user])
        session.commit()

        print("База данных успешно заполнена тестовыми данными.")
        print("-" * 50)
        print("Тестовые аккаунты:")
        print("  Private: private_user / 1234567890")
        print("  Company: company_user / 1234567890 (Ключ: COMPANYKEY123)")
        print("  Test:    test / 12345678 (Ключ: COMPANYKEY123)")
        print("-" * 50)

    session.close()


# Для тестирования модуля напрямую
if __name__ == "__main__":
    initialize_database()
