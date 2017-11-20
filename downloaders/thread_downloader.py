import asyncio
import logging
from copy import deepcopy
from threading import Lock

import requests
from PyQt5 import QtCore
from pypac import PACSession, get_pac
from pypac.parser import PACFile

from config_readers import ConfigsProgram, SerialsUrls


class ThreadDownloader(QtCore.QObject):
    """
    Асинхронных загрузчик данных с web страниц основанный на потоках
    """
    # todo реализовать timeout для всех потоков
    s_worker_complete = QtCore.pyqtSignal(dict, name='worker_complete')
    s_init_completed = QtCore.pyqtSignal(object, object, name='init_completed')

    def __init__(self, target_urls: SerialsUrls, conf_program: ConfigsProgram):
        super().__init__()
        self.target_urls = target_urls
        self.conf_program = conf_program.data['general']

        self._lock = Lock()
        self._pac: PACFile = None
        self._future: asyncio.Future = None
        self._internet_is_available: bool = None
        self.initializer: AsyncInitDownloader = None
        self.count_urls = 0
        self.count_completed_workers = 0
        self._workers = []
        self._downloaded_pages = {}
        self._logger = logging.getLogger('main')

        self.s_worker_complete.connect(
            self._worker_complete, QtCore.Qt.QueuedConnection
        )
        self.s_init_completed.connect(
            self._initialization_completed, QtCore.Qt.QueuedConnection
        )

    def start(self, future: asyncio.Future):
        """
        Запускает процесс скачивания web страниц
        :param future: объект feature через который скачаные страницы
        будут переданы для дальнейшей обработки
        """
        self._future = future
        self.count_urls = sum(map(len, self.target_urls.data.values()))

        if self.count_urls == 0:
            self._future.set_result(['normal', {}])
            return

        self.initializer = AsyncInitDownloader(
            self.conf_program, self.s_init_completed
        )
        self.initializer.start()

    def cancel_download(self):
        """
        Отменяет загрузку
        """
        for i in self._workers:
            i.f_stop_download = True

        self._future.set_result(['cancelled', {}])

    def _run(self):
        self._workers.clear()
        self._downloaded_pages.clear()
        self.count_completed_workers = 0

        if not self._internet_is_available:
            self._future.set_result(['cancelled', {}])
            return

        target_urls = deepcopy(self.target_urls.data)

        if self.count_urls < self.conf_program['thread_count']:
            thread_count = self.count_urls
        else:
            thread_count = self.conf_program['thread_count']

        for i in range(thread_count):
            worker = Worker(target_urls, self._pac, self._lock,
                            self.s_worker_complete)
            worker.start()
            self._workers.append(worker)

    def _initialization_completed(self, pac: PACFile, internet_is_available: bool):
        """
        Вызывается при завершении инициализации и запускает процесс скачивания
        web страниц
        :param pac: pac файл для автоматической настройки proxy
        :param internet_is_available: флаг отображающий доступность интернета
        """
        self._pac = pac
        self._internet_is_available = internet_is_available

        self._run()

    def _worker_complete(self, downloaded_pages: dict):
        """
        Вызывается, когда worker закончил скачивание
        :param downloaded_pages: страницы загруженные worker
        """
        self.count_completed_workers += 1
        self._downloaded_pages.update(downloaded_pages)

        if self.count_completed_workers == len(self._workers):
            self._future.set_result(['normal', self._downloaded_pages])


class Worker(QtCore.QThread):
    """
    Поток производящий скачивание web страниц
    """
    def __init__(self, target_urls: dict, pac: PACFile, lock: Lock,
                 s_worker_complete):
        super().__init__()
        self.target_urls = target_urls
        self._lock = lock
        self.session = PACSession(pac=pac)
        self.s_worker_complete = s_worker_complete
        self._logger = logging.getLogger('main')

        self.f_stop_download = False
        self._downloaded_pages = {}

    def run(self):
        while True:
            with self._lock:
                try:
                    site_name = list(self.target_urls.keys())[0]
                except IndexError:
                    break

                try:
                    serial_name, url = self.target_urls[site_name].pop()
                except IndexError:
                    del self.target_urls[site_name]
                    continue

            html = self.session.get(
                url, hooks={'response': self.terminate_download}
            ).text
            self._downloaded_pages.setdefault(
                site_name, []
            ).append([serial_name, html])

        self.s_worker_complete.emit(self._downloaded_pages)

    def terminate_download(self, *args, **kwargs):
        """
        Прерывает скачивание
        """
        if self.f_stop_download:
            self.terminate()
            self.wait(0)


class AsyncInitDownloader(QtCore.QThread):
    """
    Выполняет асинхронную инициализацию загрузчика (проверяет доступность
    интернета, скачивает pac файл для автоматической настройки proxy)
    """
    def __init__(self, conf_program, s_init_completed):
        super().__init__()
        self.conf_program = conf_program
        self.s_init_completed = s_init_completed

        self._logger = logging.getLogger('main')

    def run(self):
        internet_is_available = self._check_internet_access()
        pac = None

        if self.conf_program['pac_file'] != '':
            try:
                pac = get_pac(url=self.conf_program['pac_file'])
            except Exception as e:
                self._logger.exception(e)
            if not pac:
                self._logger.error('Не удалось скачать pac файл для '
                                   'автоматической настройки proxy')
        else:
            self._logger.info('Прокси не используется, pac файл не задан')

        self.s_init_completed.emit(pac, internet_is_available)

    def _check_internet_access(self):
        try:
            requests.get('http://google.com')
            return True
        except requests.exceptions.ConnectionError:
            self._logger.info(
                'Отстуствует доступ в интернет, проверьте подключение'
            )
            return False


if __name__ == '__main__':
    from quamash import QEventLoop
    from configs import base_dir

    app = QtCore.QCoreApplication([])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    def print_res(data):
        print(data.result())
        exit(0)

    future = asyncio.Future()
    future.add_done_callback(print_res)

    urls = SerialsUrls(base_dir)
    conf_program = ConfigsProgram(base_dir)
    d = ThreadDownloader(urls, conf_program)
    d.start(future)

    with loop:
        loop.run_forever()

