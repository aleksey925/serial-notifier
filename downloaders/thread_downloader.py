import logging
from copy import deepcopy
from threading import Lock
from urllib.parse import urlsplit

import gopac
import requests
from PyQt5 import QtCore
from gopac.exceptions import GoPacException, ErrorDecodeOutput

from config_readers import ConfigsProgram, SerialsUrls
from downloaders.base_downloader import (
    BaseDownloader, DownloadCancel, TimeoutUpdate
)
from upgrade_state import UpgradeState


class ThreadDownloader(BaseDownloader):
    """
    Асинхронных загрузчик данных с web страниц основанный на потоках
    """
    s_worker_complete = QtCore.pyqtSignal(
        dict, list, dict, name='worker_complete'
    )

    def __init__(self):
        super().__init__()

        self._lock = Lock()
        self._timeout_update_timer = QtCore.QTimer()
        self._count_urls = 0
        self._count_completed_workers = 0
        self.f_cancel_download = False
        self.f_timeout_update = False
        self._workers = []

        self.s_worker_complete.connect(
            self._worker_complete, QtCore.Qt.QueuedConnection
        )
        self._timeout_update_timer.timeout.connect(self._terminate_download)

    def _before_start(self):
        self._workers.clear()
        self._count_completed_workers = 0
        self.f_cancel_download = False
        self.f_timeout_update = False

        self._count_urls = sum(
            map(lambda i: len(i['urls']), self.target_urls.data.values())
        )

        if self._count_urls == 0:
            self.s_download_complete.emit(
                UpgradeState.CANCELLED,
                ['sites.conf пуст, нет сериалов для отслеживания'], {}, {}
            )
            return

    def _start(self, internet_available: bool):
        if not internet_available:
            self.s_download_complete.emit(
                UpgradeState.ERROR, ['Отстуствует соединение с интернетом'],
                {}, {}
            )
            return

        self._logger.info(
            'Запросы выполняются {}'.format(
                'через прокси' if self.conf_program['downloader']['use_proxy']
                else 'без использования прокси'
            )
        )

        target_urls = deepcopy(self.target_urls.data)

        thread_count = self.conf_program['thread_downloader']['thread_count']
        if self._count_urls < thread_count:
            thread_count = self._count_urls

        for i in range(thread_count):
            worker = Worker(
                target_urls, self.conf_program, self._lock,
                self.s_worker_complete
            )
            worker.start()
            self._workers.append(worker)

        self._timeout_update_timer.start(
            self.conf_program['thread_downloader']['timeout']
        )

    def _worker_complete(self, urls_errors: dict, error_msgs: list,
                         downloaded_pages: dict):
        """
        Вызывается, когда worker закончил скачивание
        :param downloaded_pages: страницы загруженные worker
        """
        self._count_completed_workers += 1

        for site_name, data in downloaded_pages.items():
            self._downloaded_pages.setdefault(site_name, []).extend(data)

        for serial, err_msg in urls_errors.items():
            self._urls_errors.setdefault(serial, []).extend(err_msg)

        self._error_msgs.extend(error_msgs)

        if (self._count_completed_workers == len(self._workers)
                and self.f_cancel_download is False):

            state = UpgradeState.OK
            if self.f_timeout_update:
                message = ('Первышено время обновления. Получены данные только'
                           ' с части сайтов')
                state = UpgradeState.WARNING
                self._error_msgs.append(message)
                self._logger.error(message)

            self._timeout_update_timer.stop()

            self.s_download_complete.emit(
                state, self._error_msgs, self._urls_errors,
                self._downloaded_pages
            )

    def _terminate_download(self):
        self.f_timeout_update = True

        for i in self._workers:
            i.f_timeout_update = True

        self._timeout_update_timer.stop()

    def cancel_download(self):
        self._internet_status_checker.cancel()

        self.f_cancel_download = True
        for i in self._workers:
            i.f_cancel_download = True

        self._timeout_update_timer.stop()

        self.s_download_complete.emit(
            UpgradeState.CANCELLED,
            ['Обновленние отменено пользователем'], {}, {}
        )

    def clear(self):
        self._error_msgs.clear()
        self._urls_errors.clear()
        self._downloaded_pages.clear()


class Worker(QtCore.QThread):
    """
    Поток производящий скачивание web страниц
    """
    def __init__(self, target_urls: dict, conf_program: dict, lock: Lock,
                 s_worker_complete):

        super().__init__()
        self._target_urls = target_urls
        self._lock = lock
        self._check_internet_access_url = conf_program['downloader'][
            'check_internet_access_url'
        ]
        self._use_proxy = conf_program['downloader']['use_proxy']
        self._pac_url = conf_program['downloader']['pac_file']
        self._session = requests.Session()
        self.s_worker_complete = s_worker_complete
        self._logger = logging.getLogger('serial-notifier')

        self.f_cancel_download = False
        self.f_timeout_update = False
        self._error_msgs = []
        self._urls_errors = {}
        self._downloaded_pages = {}

    def set_proxy_for_session(self, url, site_name, serial_name):
        if not self._use_proxy or not self._pac_url:
            return

        domain = "{0.scheme}://{0.netloc}/".format(urlsplit(url))
        try:
            proxy = gopac.find_proxy(self._pac_url, domain)
        except (ValueError, ErrorDecodeOutput, GoPacException) as e:
            message = f'Не удалось получить прокси для: {url}'
            self._session.proxies = {}
            self._urls_errors.setdefault(
                f'{site_name}_{serial_name}', []
            ).append(message)
            self._logger.error(message, exc_info=True)
        else:
            self._session.proxies = proxy

    def clear_proxy_cache(self):
        if not self._use_proxy:
            return

        gopac.find_proxy.cache_clear()

    def fetch(self, url, site_name, serial_name, recursion_deep=0):
        if recursion_deep == 2:
            return

        try:
            self.set_proxy_for_session(url, site_name, serial_name)
            return self._session.get(
                url, hooks={'response': self.terminate_download}
            )
        except (DownloadCancel, TimeoutUpdate):
            raise
        except requests.exceptions.ConnectionError:
            self.clear_proxy_cache()
            message = f'Ошибка при подключении к: {url}'
            self._logger.error(message)
            self._urls_errors.setdefault(
                f'{site_name}_{serial_name}', []
            ).append(message)
            self.fetch(url, site_name, serial_name, recursion_deep + 1)
        except Exception:
            self.clear_proxy_cache()
            message = f'Непредвиденная ошибка при доступе к : {url}'
            self._logger.error(message, exc_info=True)
            self._urls_errors.setdefault(
                f'{site_name}_{serial_name}', []
            ).append(message)
            self.fetch(url, site_name, serial_name, recursion_deep + 1)

    def run(self):
        while True:
            with self._lock:
                try:
                    site_name = list(self._target_urls.keys())[0]
                except IndexError:
                    break

                try:
                    serial_name, url = self._target_urls[site_name]['urls'].pop()
                    encoding = self._target_urls[site_name]['encoding']
                except IndexError:
                    del self._target_urls[site_name]
                    continue

            try:
                html = self.fetch(url, site_name, serial_name)
            except DownloadCancel:
                return
            except TimeoutUpdate:
                self.s_worker_complete.emit(
                    self._urls_errors, self._error_msgs, self._downloaded_pages
                )
                return

            if html is None:
                continue
            if encoding:
                html.encoding = encoding

            self._downloaded_pages.setdefault(site_name, []).append(
                [serial_name, html.text]
            )

        self.s_worker_complete.emit(
            self._urls_errors, self._error_msgs, self._downloaded_pages
        )

    def terminate_download(self, *args, **kwargs):
        """
        Прерывает скачивание
        """
        if self.f_cancel_download:
            raise DownloadCancel()
        if self.f_timeout_update:
            raise TimeoutUpdate()


if __name__ == '__main__':
    import dependency_injector.containers as cnt
    import dependency_injector.providers as prv

    from downloaders import base_downloader
    from configs import base_dir

    class DIServises_(cnt.DeclarativeContainer):
        conf_program = prv.Singleton(ConfigsProgram, base_dir=base_dir)
        serials_urls = prv.Singleton(SerialsUrls, base_dir=base_dir)

    base_downloader.DIServises.override(DIServises_)

    class SelfTest(QtCore.QObject):
        def __init__(self):
            super().__init__()
            self.downloader = ThreadDownloader()

            self.downloader.s_download_complete.connect(
                self.download_complete, QtCore.Qt.QueuedConnection
            )

            self.downloader.start()

        def download_complete(self, status: UpgradeState, error_msgs: list,
                              urls_errors: list, downloaded_pages: dict):
            print('status:', status)
            print('error_msgs:', error_msgs)
            print('urls_errors:', urls_errors)
            print('downloaded_pages:', downloaded_pages)
            exit(0)


    app = QtCore.QCoreApplication([])
    test = SelfTest()
    app.exec()
