import os
import logging

from sqlalchemy import create_engine

from model import Base
from project_settings import db_url
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.session import Session


def create_db():
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)


def create_db_session() -> Session:
    """
    Создает сессию работы с БД
    """
    if not os.path.exists(db_url.replace('sqlite:////', '')):
        create_db()

    engine = create_engine(db_url)
    new_session = scoped_session(sessionmaker(bind=engine))
    return new_session()


def create_logger(path):
    """
    Создаёт объект, который отвечат за логирование

    :argument path: str Путь в который будут писаться логи
    """
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)

    # Создаётся обработчик,который будет писать сообщения в файл
    file_handler = logging.FileHandler(path)
    file_handler.setLevel(logging.DEBUG)
    # Определяется формат логов и добавляется к обработчику
    file_formatter = logging.Formatter(
        '#%(levelname)-s [%(asctime)s]  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(('#%(levelname)-s, line %(lineno)d:'
                                           ' %(message)s'))
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(console_formatter)

    # добавляем обработчики в logger
    log.addHandler(file_handler)
    log.addHandler(console_handler)

    return log