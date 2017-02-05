import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.session import Session

from .models import Base
from configs import db_url


def create_db():
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)


def create_db_session() -> Session:
    """
    Создает сессию работы с БД
    """
    if not os.path.exists(db_url.replace('sqlite:///', '')):
        create_db()

    engine = create_engine(db_url)
    new_session = scoped_session(sessionmaker(bind=engine))
    return new_session()