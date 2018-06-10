import logging
from queue import Queue

import dependency_injector.containers as cnt
import dependency_injector.providers as prv
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, pyqtSignal

from config_readers import SerialsUrls, ConfigsProgram
from upgrade_state import UpgradeState
from downloaders import downloader, ThreadDownloader
from parsers import AsyncHtmlParser


class DIServises(cnt.DeclarativeContainer):
    db_manager = prv.Provider()

    conf_program = prv.Provider()
    serials_urls = prv.Provider()


class UpgradesScheduler(QtCore.QTimer):
    """
    Планировщик отвечающий за обновление информации о новых сериях
    """

    # Отправляет данные для парсинга
    s_send_data_parser = pyqtSignal(dict, name='send_data_parser')

    s_upgrade_complete = pyqtSignal(UpgradeState, list, dict, dict, str,
                                    name='upgrade_complete')

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger('serial-notifier')

        # Сигнализирует производится уже обработка данных или нет
        self.flag_progress = Queue(maxsize=1)
        self.urls: SerialsUrls = DIServises.serials_urls()
        self.conf_program: ConfigsProgram = DIServises.conf_program()

        # Храним состояние загрузки
        self.downloader_state: UpgradeState = None
        self.error_msgs: list = []
        self.urls_errors: dict = {}

        self.downloader = downloader.get(
            self.conf_program['downloader']['target_downloader'],
            ThreadDownloader
        )()
        self.logger.info(
            f'Для скачивания данных используется '
            f'{self.downloader.__class__.__name__}'
        )

        self.downloader.s_download_complete.connect(
            self.download_complete, Qt.QueuedConnection
        )

        self.db_manager = DIServises.db_manager()
        self.db_manager.s_status_update.connect(
            self.upgrade_db_complete, Qt.QueuedConnection
        )

        self.parser = AsyncHtmlParser(self.s_send_data_parser)
        self.parser.s_data_ready.connect(self.parse_complete)

        # Запускаем таймер
        self.timeout.connect(lambda: self.run('timer'))
        self.start(self.conf_program['general']['refresh_interval'])

    def run(self, type_run):
        """
        Запускает процесс обновления данных в базе
        :argument type_run Определяет как было запущено обновление (вручную или
        по таймеру). Принимает значения: timer или user
        """
        # Если обновление базы не производится прямо сейчас, то можно запустить
        # процесс обновления
        if self.flag_progress.empty():
            self.flag_progress.put(type_run)

            self.urls.read()
            self.conf_program.read()

            self.downloader.start_download()

    def download_complete(self, status: UpgradeState, error_msgs: list,
                          urls_errors: dict, downloaded_pages: dict):
        """
        Вызывается после того как загрузка была завершена и инициирует парсинг
        html страниц
        :param status: статус обновления
        :param error_msgs: ошибок возникших при обновлении
        :param urls_errors: описание проблем возниших при обработке ссылок
        Пример:
        {'filin.tv_Вызов': ['ошибка 1'], 'filmix.me_Вызов': ['ошибка 1']}
        :param downloaded_pages: скачанные страницы
        """
        self.error_msgs = error_msgs
        self.urls_errors = urls_errors
        self.downloader_state = status
        if status in (UpgradeState.CANCELLED, UpgradeState.ERROR):
            self.upgrade_db_complete(status, [], {})
        else:
            self.s_send_data_parser.emit(downloaded_pages)

    def parse_complete(self, serials_data: dict, errors: dict):
        """
        Получает данные извлеченные из скаченых HTML старниц отпрвляет их
        для обновления БД

        :param serials_data Данные о сериалах полученые после парсинга HTML
        Пример:
        {'filin.tv': {'Теория Большого взрыва': {'Серия': [17], 'Сезон': 1},}
        :param errors список сериалов страницы с которыми не удалось распарсить
        """
        for serial, err_msgs in errors.items():
            self.urls_errors.setdefault(serial, list()).extend(err_msgs)

        self.db_manager.s_send_db_task.emit(
            lambda: self.db_manager.upgrade_db(serials_data)
        )

    def upgrade_db_complete(self, status: UpgradeState, error_msgs: list,
                            serials_with_updates: dict):
        """
        :param status Указывает успешно или нет завершилась операция обновления
        базы данных
        :param error_msgs сообщения об ошибках
        :param serials_with_updates обновившиеся сериалы
        """
        if status < self.downloader_state:
            status = self.downloader_state

        type_run = self.flag_progress.get()
        self.error_msgs.extend(error_msgs)
        self.s_upgrade_complete.emit(
            status, self.error_msgs, self.urls_errors, serials_with_updates,
            type_run
        )

    def clear_downloader(self):
        if self.flag_progress.empty():
            self.downloader.clear()
            self.error_msgs.clear()
            self.urls_errors.clear()
