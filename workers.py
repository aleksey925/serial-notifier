"""
Моудль с асинхронными обработчиками данных
"""
import asyncio

from queue import Queue

from PyQt4 import QtCore
from PyQt4.QtCore import Qt, pyqtSignal

from parser import AsyncParserHTML
from downloader import Downloader


class UpgradeTimer(QtCore.QTimer):
    """
    Планировщик обновления данных в бд. Запускает через заданный промежуток
    времени обновление данных. Поддерживает ручной вызов обновления.
    """

    # Отправляет данные для парсинга
    s_send_data_parser = pyqtSignal(object, name='send_data_parser')

    s_upgrade_complete = pyqtSignal(object, object, object,
                                    name='upgrade_complete')

    def __init__(self, db_worker, urls, conf_program, logger):
        super(UpgradeTimer, self).__init__()

        # Сигнализирует производится уже обработка данных или нет
        self.flag_progress = Queue(maxsize=1)
        self.urls = urls
        self.conf_program = conf_program
        self.logger = logger

        self.loader = Downloader(self.urls, self.logger)

        self.db_worker = db_worker
        self.db_worker.s_status_update.connect(self.upgrade_db_complete,
                                               Qt.QueuedConnection)

        self.parser = AsyncParserHTML(self.s_send_data_parser)
        self.parser.s_data_ready.connect(self.parse_complete)

        # Запускаем таймер
        self.timeout.connect(lambda: self.run('timer'))
        self.start(self.conf_program.conf['timeout_refresh'])

    def run(self, type_run):
        """
        Запускает процесс обновления данных в базе
        :argument type_run Определяет как было запущено обновление (вручную или
        по таймеру). Принимает значения: timer или user
        """
        # Если обновление базы не производится прямо сейчас, то можно запустить
        # процесс
        if self.flag_progress.empty():
            self.urls.read()
            self.flag_progress.put(type_run)
            f_download_complete = asyncio.Future()
            f_download_complete.add_done_callback(self.download_complete)

            self.loader.run(f_download_complete)

    def download_complete(self, downloaded_pages: asyncio.Future):
        """
        Получает HTML старницы и запускает парсинг
        """
        self.s_send_data_parser.emit(downloaded_pages.result())

    def parse_complete(self, serials_data: dict):
        """
        Получает данные извлеченные из скаченых HTML старниц отпрвляет их
        для обновления БД

        :param serials_data Данные о сериалах полученые после парсинга HTML
        Пример:
        {'filin.tv': {'Теория Большого взрыва': {'Серия': [17], 'Сезон': 1},}
        """
        self.db_worker.s_send_db_task.emit(
            lambda: self.db_worker.upgrade_db(serials_data)
        )

    def upgrade_db_complete(self, status: str, serials_with_updates: dict):
        """
        :param status Указывает успешно или нет завершилась операция обновления
        базы данных. Может получить "ok" или  "error".
        :param serials_with_updates
        """
        type_run = self.flag_progress.get()
        self.s_upgrade_complete.emit(status, serials_with_updates, type_run)
