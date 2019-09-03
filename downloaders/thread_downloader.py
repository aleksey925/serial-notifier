import logging
import threading
from copy import deepcopy
from threading import Lock
from urllib.parse import urlsplit

import gopac
import requests
from PyQt5 import QtCore
from gopac.exceptions import GoPacException, ErrorDecodeOutput

from config_readers import ConfigsProgram, SerialsUrls
from downloaders.base_downloader import BaseDownloader, DownloadCancel
from enums import UpgradeState


class ThreadDownloader(BaseDownloader):
    """
    Асинхронных загрузчик данных с web страниц основанный на потоках
    """
    s_serial_downloaded = QtCore.pyqtSignal(
        str, str, str, str, list, name='s_serial_downloaded'
    )
    s_worker_complete = QtCore.pyqtSignal(name='s_worker_complete')

    def __init__(self):
        super().__init__()

        self.f_cancel_download = False

        self._lock = Lock()
        self._workers = []
        self._count_urls = 0
        self._count_completed_workers = 0
        self._timeout_update_timer = QtCore.QTimer()

        self.s_serial_downloaded.connect(
            self._serial_downloaded, QtCore.Qt.QueuedConnection
        )
        self.s_worker_complete.connect(
            self._worker_complete, QtCore.Qt.QueuedConnection
        )
        self._timeout_update_timer.timeout.connect(
            lambda: self.cancel_download('timeout')
        )

    def calculate_thread_count(self):
        thread_count = self._conf_program['thread_downloader']['thread_count']
        if self._count_urls < thread_count:
            thread_count = self._count_urls

        return thread_count

    def _before_start(self):
        self._workers.clear()
        self._count_completed_workers = 0
        self.f_cancel_download = False

        self._count_urls = sum(
            map(lambda i: len(i['urls']), self._target_urls.values())
        )

        if self._count_urls == 0:
            self.s_download_complete.emit(
                UpgradeState.CANCELLED,
                ['sites.conf пуст, нет сериалов для отслеживания'], {}, {}
            )
            return

    def _start(self, internet_available: bool, downloaded_pac_file: str):
        if not internet_available:
            self.s_download_complete.emit(
                UpgradeState.ERROR, ['Отстуствует соединение с интернетом'],
                {}, {}
            )
            return

        self._downloaded_pac_file = downloaded_pac_file
        self._logger.info(
            'Проксирвание запросов {}'.format(
                'ВКЛЮЧЕНО' if self._conf_program['downloader']['use_proxy'] else
                'ВЫКЛЮЧЕНО'
            )
        )

        target_urls = deepcopy(self._target_urls.get_config_data())
        for i in range(self.calculate_thread_count()):
            worker = Worker(
                target_urls, self._conf_program, self._downloaded_pac_file,
                self._lock, self.s_serial_downloaded, self.s_worker_complete
            )
            worker.start()
            self._workers.append(worker)

        self._timeout_update_timer.start(
            self._conf_program['thread_downloader']['timeout']
        )

    def _serial_downloaded(self, site_name: str, serial_name: str, html: str,
                           url: str, url_errors: list):

        if html:
            self._downloaded_pages.setdefault(site_name, []).append(
                [serial_name, url, html]
            )
        if url_errors:
            self._urls_errors.setdefault(
                f'{site_name}_{serial_name}', list()
            ).extend(url_errors)

    def _worker_complete(self):
        self._count_completed_workers += 1

        if (self._count_completed_workers == len(self._workers)
                and self.f_cancel_download is False):

            self._timeout_update_timer.stop()

            self.s_download_complete.emit(
                UpgradeState.OK, self._error_msgs, self._urls_errors,
                self._downloaded_pages
            )

    def cancel_download(self, reason='cancel'):
        self._downloader_initializer.cancel()

        self.f_cancel_download = True
        for i in self._workers:
            i.f_cancel_download = True

        self._timeout_update_timer.stop()

        if reason == 'cancel':
            self.s_download_complete.emit(
                UpgradeState.CANCELLED,
                ['Обновленние отменено пользователем'], {}, {}
            )
        elif reason == 'timeout':
            message = ('Первышено время обновления. Получены данные только '
                       'с части сайтов')
            self._error_msgs.append(message)
            self._logger.warning(message)
            self.s_download_complete.emit(
                UpgradeState.WARNING, self._error_msgs, self._urls_errors,
                self._downloaded_pages
            )

    def clear(self):
        self._error_msgs.clear()
        self._urls_errors.clear()
        self._downloaded_pages.clear()
        map(lambda worker: worker.terminate(), self._workers)


class Worker(QtCore.QThread):
    """
    Поток производящий скачивание web страниц
    """
    def __init__(self, target_urls: dict, conf_program: ConfigsProgram,
                 downloaded_pac_file: str, lock: Lock, s_serial_downloaded,
                 s_worker_complete):

        super().__init__()

        self._target_urls: dict = target_urls
        self.console_encoding = conf_program['gopac']['console_encoding']
        self._check_internet_access_url: str = conf_program['downloader'][
            'check_internet_access_url'
        ]
        self._use_proxy: bool = conf_program['downloader']['use_proxy']
        self._downloaded_pac_file: str = downloaded_pac_file
        self._lock: Lock = lock
        self.s_serial_downloaded = s_serial_downloaded
        self.s_worker_complete = s_worker_complete

        self.f_cancel_download = False
        self._session = requests.Session()
        self._downloaded_pages = {}
        self._logger = logging.getLogger('serial-notifier')

    def set_proxy_for_session(self, url: str, url_errors: set):
        if not self._use_proxy or not self._downloaded_pac_file:
            return

        domain = "{0.scheme}://{0.netloc}/".format(urlsplit(url))
        try:
            proxy = gopac.find_proxy(
                self._downloaded_pac_file, domain, self.console_encoding
            )
        except (ValueError, ErrorDecodeOutput, GoPacException) as e:
            message = f'Не удалось получить прокси для: {url}'
            self._session.proxies = {}
            url_errors.add(message)
            self._logger.error(message, exc_info=True)
        else:
            self._session.proxies = proxy

    def clear_proxy_cache(self):
        if not self._use_proxy:
            return

        gopac.find_proxy.cache_clear()

    def fetch(self, url: str, url_errors: set, recursion_deep=0):
        if recursion_deep == 2:
            return

        try:
            self.set_proxy_for_session(url, url_errors)
            return self._session.get(
                url, hooks={'response': self.terminate_download}
            )
        except DownloadCancel:
            raise
        except requests.exceptions.ConnectionError:
            self.clear_proxy_cache()
            message = f'Ошибка при подключении к: {url}'
            self._logger.error(message)
            url_errors.add(message)
            self.fetch(url, url_errors, recursion_deep + 1)
        except Exception:
            self.clear_proxy_cache()
            message = f'Непредвиденная ошибка при доступе к : {url}'
            self._logger.error(message, exc_info=True)
            url_errors.add(message)
            self.fetch(url, url_errors, recursion_deep + 1)

    def run(self):
        while True:
            with self._lock:
                try:
                    site_name = list(self._target_urls.keys())[0]
                except IndexError:
                    break

                try:
                    serial_name, url = self._target_urls[
                        site_name
                    ]['urls'].popitem()
                    encoding = self._target_urls[site_name]['encoding']
                except KeyError:
                    del self._target_urls[site_name]
                    continue

            url_errors = set()
            try:
                html = self.fetch(url, url_errors)
            except DownloadCancel:
                self._logger.debug(
                    f'Работа Worker {threading.current_thread().name} отменена'
                )
                return

            if html is None:
                self.s_serial_downloaded.emit(
                    site_name, serial_name, '', url, list(url_errors)
                )
                continue
            if encoding:
                html.encoding = encoding

            if not self.f_cancel_download:
                self.s_serial_downloaded.emit(
                    site_name, serial_name, html.text, url, list(url_errors)
                )

        if not self.f_cancel_download:
            self.s_worker_complete.emit()

        self._logger.debug(
            f'Worker {threading.current_thread().name} завершил работу'
        )

    def terminate_download(self, *args, **kwargs):
        """
        Прерывает скачивание
        """
        if self.f_cancel_download:
            raise DownloadCancel()


if __name__ == '__main__':
    import dependency_injector.containers as cnt
    import dependency_injector.providers as prv

    from downloaders import base_downloader
    from configs import base_dir

    class TestDIServices(cnt.DeclarativeContainer):
        conf_program = prv.Singleton(ConfigsProgram, base_dir=base_dir)
        serials_urls = prv.Singleton(SerialsUrls, base_dir=base_dir)

    base_downloader.DIServices.override(TestDIServices)

    class SelfTest(QtCore.QObject):
        def __init__(self):
            super().__init__()
            self.downloader = ThreadDownloader()

            self.downloader.s_download_complete.connect(
                self.download_complete, QtCore.Qt.QueuedConnection
            )

            self.downloader.start_download()

        def download_complete(self, status: UpgradeState, error_msgs: list,
                              urls_errors: list, downloaded_pages: dict):
            print('status:', status)
            print('error_msgs:', error_msgs)
            print('urls_errors:', urls_errors)
            print(
                'downloaded_pages:',
                ', '.join(
                    f'{site} - {i[0]}' for site, s in downloaded_pages.items()
                    for i in s
                )
            )
            exit(0)


    app = QtCore.QCoreApplication([])
    test = SelfTest()
    app.exec()
