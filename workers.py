"""
Моудль с асинхронными обработчиками данных
"""
import asyncio

from queue import Queue

from PyQt5 import QtCore
from PyQt5.QtCore import Qt, pyqtSignal

from config_readers import SerialsUrls, ConfigsProgram
from parsers import AsyncParserHTML
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

    def __init__(self, tray_icon, db_worker, urls: SerialsUrls,
                 conf_program: ConfigsProgram):
        super(UpgradeTimer, self).__init__()

        # Сигнализирует производится уже обработка данных или нет
        self.flag_progress = Queue(maxsize=1)
        self.tray_icon = tray_icon
        self.urls = urls
        self.conf_program = conf_program

        self.loader = Downloader(self.urls, self.conf_program)

        self.db_worker = db_worker
        self.db_worker.s_status_update.connect(self.upgrade_db_complete,
                                               Qt.QueuedConnection)

        self.parser = AsyncParserHTML(self.s_send_data_parser)
        self.parser.s_data_ready.connect(self.parse_complete)

        # Запускаем таймер
        self.timeout.connect(lambda: self.run('timer'))
        self.start(self.conf_program.data['timeout_refresh'])

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
            self.tray_icon.update_start()

            self.urls.read()
            self.conf_program.read()

            f_download_complete = asyncio.Future()
            f_download_complete.add_done_callback(self.download_complete)

            asyncio.ensure_future(self.loader.run(f_download_complete))

    def download_complete(self, download_result: asyncio.Future):
        """
        Получает HTML старницы и запускает парсинг
        :param download_result: объект future содержащий список со статусом и
        скачанными данными. Статус может быть "normal" или "cancelled"
        """
        data = download_result.result()
        if data[0] == 'cancelled':
            self.upgrade_db_complete(*data)
        else:
            self.s_send_data_parser.emit(data[1])

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
        базы данных. Может получить "ok", "cancelled" или "error".
        :param serials_with_updates
        """
        type_run = self.flag_progress.get()
        self.s_upgrade_complete.emit(status, serials_with_updates, type_run)
