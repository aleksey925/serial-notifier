import asyncio
from queue import Queue

import dependency_injector.containers as cnt
import dependency_injector.providers as prv
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, pyqtSignal

from config_readers import SerialsUrls, ConfigsProgram
from update_status import UpgradeStatus
from downloaders import ThreadDownloader
from parsers import AsyncParserHTML


class DIServises(cnt.DeclarativeContainer):
    db_manager = prv.Provider()

    conf_program = prv.Provider()
    serials_urls = prv.Provider()


class UpgradesScheduler(QtCore.QTimer):
    """
    Планировщик отвечающий за обновление информации о новых сериях
    """

    # Отправляет данные для парсинга
    s_send_data_parser = pyqtSignal(object, name='send_data_parser')

    s_upgrade_complete = pyqtSignal(object, object, object,
                                    name='upgrade_complete')

    def __init__(self):
        super().__init__()

        # Сигнализирует производится уже обработка данных или нет
        self.flag_progress = Queue(maxsize=1)
        self.urls: SerialsUrls = DIServises.serials_urls()
        self.conf_program: ConfigsProgram = DIServises.conf_program()

        self.loader = ThreadDownloader(self.urls, self.conf_program)

        self.db_manager = DIServises.db_manager()
        self.db_manager.s_status_update.connect(
            self.upgrade_db_complete, Qt.QueuedConnection
        )

        self.parser = AsyncParserHTML(self.s_send_data_parser)
        self.parser.s_data_ready.connect(self.parse_complete)

        # Запускаем таймер
        self.timeout.connect(lambda: self.run('timer'))
        self.start(self.conf_program.data['general']['refresh_interval'])

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

            f_download_complete = asyncio.Future()
            f_download_complete.add_done_callback(self.download_complete)

            self.loader.start(f_download_complete)

    def download_complete(self, download_result: asyncio.Future):
        """
        Вызывается после того как загрузка была завершена и инициирует парсинг
        html страниц
        :param download_result: объект future содержащий список со статусом и
        скачанными данными.
        """
        data = download_result.result()
        if data[0] == UpgradeStatus.CANCELLED:
            self.upgrade_db_complete(data[0], {})
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
        self.db_manager.s_send_db_task.emit(
            lambda: self.db_manager.upgrade_db(serials_data)
        )

    def upgrade_db_complete(self, status: UpgradeStatus,
                            serials_with_updates: dict):
        """
        :param status Указывает успешно или нет завершилась операция обновления
        базы данных.
        :param serials_with_updates
        """
        type_run = self.flag_progress.get()
        self.s_upgrade_complete.emit(status, serials_with_updates, type_run)
