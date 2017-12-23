import logging
from copy import deepcopy

import requests
import serial_notifier_go_downloader as downloader
from PyQt5 import QtCore

from configs import log_path
from config_readers import ConfigsProgram, SerialsUrls
from upgrade_state import UpgradeState


class GoDownloader(QtCore.QObject):
    """
    Асинхронных загрузчик web страниц использующий реализацию на go
    """
    s_download_complete = QtCore.pyqtSignal(tuple, name='download_complete')
    s_worker_complete = QtCore.pyqtSignal(dict, name='worker_complete')
    s_init_completed = QtCore.pyqtSignal(object, name='init_completed')

    def __init__(self, target_urls: SerialsUrls, conf_program: ConfigsProgram):
        super().__init__()
        self.target_urls = target_urls
        self.conf_program = conf_program.data['general']

        self._internet_is_available: bool = None
        self._worker: Worker = None
        self.initializer: AsyncInitDownloader = None
        self.f_stop_download = False
        self._logger = logging.getLogger('main')

        self.s_worker_complete.connect(
            self._worker_complete, QtCore.Qt.QueuedConnection
        )
        self.s_init_completed.connect(
            self._initialization_completed, QtCore.Qt.QueuedConnection
        )

    def start(self):
        """
        Запускает процесс скачивания web страниц
        """
        self.f_stop_download = False
        count_urls = sum(
            map(lambda i: len(i['urls']), self.target_urls.data.values())
        )

        if count_urls == 0:
            self.s_download_complete.emit((UpgradeState.OK, {}))
            return

        self.initializer = AsyncInitDownloader(self.s_init_completed)
        self.initializer.start()

    def _initialization_completed(self, internet_is_available: bool):
        """
        Вызывается при завершении инициализации и запускает процесс скачивания
        web страниц
        :param internet_is_available: флаг отображающий доступность интернета
        """
        self._internet_is_available = internet_is_available
        self._run()

    def _run(self):
        if self.f_stop_download:
            # Если обновление отменили на моменте инициализации
            # то предотвращаем запуск загрузки
            return

        if not self._internet_is_available:
            self.s_download_complete.emit((UpgradeState.CANCELLED, {}))
            return

        self._worker = Worker(
            self.target_urls.data, self.conf_program['pac_file'],
            self.s_worker_complete
        )
        self._worker.start()

    def cancel_download(self):
        """
        Отменяет загрузку
        """
        self.f_stop_download = True
        downloader.cancel_download()
        self.s_download_complete.emit((UpgradeState.CANCELLED, {}))

    def _worker_complete(self, downloaded_pages: dict):
        """
        Вызывается, когда скачиваение было завершено
        :param downloaded_pages: загруженные страницы
        """
        if not self.f_stop_download:
            self.s_download_complete.emit((UpgradeState.OK, downloaded_pages))


class Worker(QtCore.QThread):
    """
    Поток производящий скачивание web страниц
    """
    def __init__(self, target_urls: dict, pac_url: str, s_worker_complete):
        super().__init__()
        self.pac_url: str = pac_url
        self.target_urls: dict = deepcopy(target_urls)
        self.s_worker_complete = s_worker_complete
        self._logger = logging.getLogger('main')

    def run(self):
        for site_name in self.target_urls.keys():
            del self.target_urls[site_name]['encoding']

        downloaded_pages, download_state, err = downloader.start_download(
            self.target_urls, self.pac_url, log_path
        )

        self.s_worker_complete.emit(downloaded_pages)


class AsyncInitDownloader(QtCore.QThread):
    """
    В отдельном потоке проверяет доступность интернета
    """
    def __init__(self, s_init_completed):
        super().__init__()
        self.s_init_completed = s_init_completed

        self._logger = logging.getLogger('main')

    def run(self):
        try:
            requests.get('http://google.com')
            self.s_init_completed.emit(True)
        except requests.exceptions.ConnectionError:
            self._logger.info(
                'Отстуствует доступ в интернет, проверьте подключение'
            )
            self.s_init_completed.emit(False)


if __name__ == '__main__':
    from configs import base_dir

    class SelfTest(QtCore.QObject):
        def __init__(self):
            super().__init__()
            self.urls = SerialsUrls(base_dir)
            self.conf_program = ConfigsProgram(base_dir)
            self.downloader = GoDownloader(self.urls, self.conf_program)

            self.downloader.s_download_complete.connect(
                self.download_complete, QtCore.Qt.QueuedConnection
            )

            self.downloader.start()

        def download_complete(self, download_result: tuple):
            print(download_result[0])
            print(download_result[1])
            exit(0)


    app = QtCore.QCoreApplication([])
    test = SelfTest()
    app.exec_()
