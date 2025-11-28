"""
Вспомогательные функции для аутентификации и авторизации
"""
from functools import wraps
from flask import session, redirect, url_for, g
from database import User, GOST


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


def get_return_route(user):
    """
    Получает маршрут возврата в зависимости от типа клиента.
    
    Args:
        user: Объект User
        
    Returns:
        str: URL маршрута возврата
    """
    if user.client_type == "company":
        return url_for("main.lk_company")
    else:
        return url_for("main.lk_private")


def get_available_gosts(db_session, user):
    """
    Получает список доступных ГОСТов для пользователя.
    
    Args:
        db_session: Сессия базы данных
        user: Объект User
        
    Returns:
        list: Список объектов GOST
    """
    if user.client_type == "company":
        return db_session.query(GOST).all()
    else:
        return db_session.query(GOST).filter_by(client_type_for="all").all()


def check_upload_access(upload, user):
    """
    Проверяет права доступа пользователя к загрузке.
    
    Args:
        upload: Объект UserUpload
        user: Объект User
        
    Returns:
        bool: True если доступ разрешен, False иначе
    """
    # Пользователь может видеть свои загрузки
    if upload.user_id == user.id:
        return True
    
    # Компания может видеть загрузки всех своих пользователей
    if user.client_type == "company" and upload.user.company_id == user.company_id:
        return True
    
    return False


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
