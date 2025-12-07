"""
Вспомогательные функции для аутентификации и авторизации
"""
from functools import wraps
from flask import session, redirect, url_for, g
from database import User


def get_current_user(db_session):
    """
    Получает текущего пользователя из сессии.
    
    Args:
        db_session: Сессия базы данных
        
    Returns:
        User или None если пользователь не авторизован
    """
    user_id = session.get("user_id")
    if user_id:
        return db_session.query(User).get(user_id)
    return None


def require_login(f):
    """
    Декоратор для проверки авторизации пользователя.
    Перенаправляет на страницу входа, если пользователь не авторизован.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user(g.db_session)
        if not user:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


def validate_user_exists(db_session, login=None, email=None):
    """
    Проверяет существование пользователя с указанным логином или email.
    
    Args:
        db_session: Сессия базы данных
        login: Логин для проверки (опционально)
        email: Email для проверки (опционально)
        
    Returns:
        tuple: (login_exists: bool, email_exists: bool)
    """
    login_exists = False
    email_exists = False
    
    if login:
        login_exists = db_session.query(User).filter_by(login=login).count() > 0
    
    if email:
        email_exists = db_session.query(User).filter_by(email=email).count() > 0
    
    return login_exists, email_exists


def validate_company_key(db_session, company_key):
    """
    Проверяет валидность ключа компании.
    
    Args:
        db_session: Сессия базы данных
        company_key: Ключ компании для проверки
        
    Returns:
        KeyCompany или None если ключ невалиден
    """
    from database import KeyCompany
    
    return (
        db_session.query(KeyCompany)
        .filter_by(key_value=company_key, is_active=True)
        .one_or_none()
    )
