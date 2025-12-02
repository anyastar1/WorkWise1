"""
Модели базы данных для авторизации и аутентификации
"""

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    DateTime,
    Text,
    Float,
    Enum,
)
import enum
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import hashlib
import os

# Инициализация базы данных
DATABASE_URL = "sqlite:///aikor.db"
engine = create_engine(DATABASE_URL)
Base = declarative_base()


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
    """Модель ключей компании для регистрации"""
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
        """Устанавливает хеш пароля"""
        self.password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    def check_password(self, password):
        """Проверяет пароль"""
        return (
            self.password_hash == hashlib.sha256(password.encode("utf-8")).hexdigest()
        )
    
    documents = relationship("Document", back_populates="user")


class Document(Base):
    """Модель документа"""
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_type = Column(String(10), nullable=False)  # 'PDF' или 'DOCX'
    operation_type = Column(String(100), nullable=False)  # Тип операции
    hash = Column(String(64), nullable=False, unique=True)  # SHA-256 хеш
    all_pages_processed = Column(Boolean, default=False, nullable=False)
    gost_check_completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    user = relationship("User", back_populates="documents")
    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Document(id={self.id}, file_type='{self.file_type}')>"


class PageStatus(enum.Enum):
    """Статусы обработки страницы"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class Page(Base):
    """Модель страницы документа"""
    __tablename__ = "pages"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    image_path = Column(String(500), nullable=False)
    status = Column(String(20), default=PageStatus.QUEUED.value, nullable=False)
    processing_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    
    document = relationship("Document", back_populates="pages")
    blocks = relationship("Block", back_populates="page", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Page(document_id={self.document_id}, page_number={self.page_number}, status={self.status})>"


class Block(Base):
    """Модель блока на странице"""
    __tablename__ = "blocks"
    id = Column(Integer, primary_key=True)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    short_description = Column(String(200), nullable=False)  # заголовок, основной текст и т.д.
    position_x = Column(Float, nullable=False)
    position_y = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    page = relationship("Page", back_populates="blocks")
    text_elements = relationship("TextElement", back_populates="block", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Block(page_id={self.page_id}, description='{self.short_description}')>"


class TextElement(Base):
    """Модель текстового элемента в блоке"""
    __tablename__ = "text_elements"
    id = Column(Integer, primary_key=True)
    block_id = Column(Integer, ForeignKey("blocks.id"), nullable=False)
    text = Column(Text, nullable=False)
    font_family = Column(String(100), nullable=True)
    font_size = Column(Float, nullable=True)
    color = Column(String(10), nullable=True)  # HEX цвет
    position_x = Column(Float, nullable=False)
    position_y = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    block = relationship("Block", back_populates="text_elements")
    
    def __repr__(self):
        return f"<TextElement(block_id={self.block_id}, text='{self.text[:50]}...')>"


class GOSTReport(Base):
    """Модель отчета о соответствии ГОСТу"""
    __tablename__ = "gost_reports"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, unique=True)
    verdict = Column(String(20), nullable=False)  # да/нет/частично
    report_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    document = relationship("Document", backref="gost_report")
    
    def __repr__(self):
        return f"<GOSTReport(document_id={self.document_id}, verdict='{self.verdict}')>"


# Управление сессиями базы данных
Session = sessionmaker(bind=engine)


def get_session():
    """Возвращает новую сессию для работы с БД."""
    return Session()


def initialize_database():
    """Инициализирует базу данных и создает тестовые данные при первом запуске."""
    global engine, Session

    # Удаляем старый файл БД, если он есть (для разработки)
    db_file_path = "aikor.db"
    if os.path.exists(db_file_path):
        print(f"Обнаружен старый файл БД '{db_file_path}'. Удаляю для чистого старта...")
        try:
            os.remove(db_file_path)
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

        # Тестовая компания
        comp_a = Company(name="TechSolutions", corporate_email="@techsol.com")
        session.add(comp_a)
        session.commit()

        # Тестовые ключи для компании
        session.add(
            KeyCompany(key_value="COMPANYKEY123", company_id=comp_a.id, is_active=True)
        )
        session.commit()

        comp_a_id = session.query(Company.id).filter_by(name="TechSolutions").one()[0]

        # Тестовые пользователи
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
        print("-" * 50)

    session.close()


if __name__ == "__main__":
    initialize_database()
