import logging
from copy import deepcopy
from threading import Lock
from urllib.parse import urlsplit

import gopac
import requests
from PyQt5 import QtCore
from gopac.exceptions import GoPacException, ErrorDecodeOutput

from config_readers import ConfigsProgram, SerialsUrls
from downloaders.base_downloader import BaseDownloader
from upgrade_state import UpgradeState


class ThreadDownloader(BaseDownloader):
    """
    Асинхронных загрузчик данных с web страниц основанный на потоках
    """
    s_worker_complete = QtCore.pyqtSignal(
        list, list, dict, name='worker_complete'
    )

    def __init__(self):
        super().__init__()

        self._lock = Lock()
        self.count_urls = 0
        self.count_completed_workers = 0
        self.f_cancel_download = False
        self.f_timeout_update = False
        self.timeout_update_timer = QtCore.QTimer()
        self._workers = []
        self._urls_errors = []
        self._error_msgs = []
        self._downloaded_pages = {}
        self._logger = logging.getLogger('serial-notifier')

        self.s_worker_complete.connect(
            self._worker_complete, QtCore.Qt.QueuedConnection
        )
        self.timeout_update_timer.timeout.connect(self._stop_download)

    def start(self):
        """
        Запускает процесс скачивания web страниц
        """
        self._workers.clear()
        self.count_completed_workers = 0
        self.f_cancel_download = False
        self.f_timeout_update = False

        self.count_urls = sum(
            map(lambda i: len(i['urls']), self.target_urls.data.values())
        )

        if self.count_urls == 0:
            self.s_download_complete.emit(
                UpgradeState.CANCELLED,
                ['sites.conf пуст, нет сериалов для отслеживания'], [], {}
            )
            return

        self.get_internet_status()

    def check_internet_access(self, is_available):
        if not is_available:
            self.s_download_complete.emit(
                UpgradeState.ERROR, ['Отстуствует соединение с интернетом'],
                [], {}
            )
            return

        self._run()

    def _run(self):
        if self.f_cancel_download:
            # Если обновление отменили на моменте инициализации загрузчика
            # то предотвращаем создание воркеров и т д
            return

        target_urls = deepcopy(self.target_urls.data)

        thread_count = self.conf_program['thread_downloader']['thread_count']
        if self.count_urls < thread_count:
            thread_count = self.count_urls

        self._logger.info(
            'Запросы выполняются {}'.format(
                'через прокси' if self.conf_program['downloader']['use_proxy']
                else 'на прямую'
            )
        )

        for i in range(thread_count):
            worker = Worker(
                target_urls, self.conf_program, self._lock,
                self.s_worker_complete
            )
            worker.start()
            self._workers.append(worker)

        self.timeout_update_timer.start(
            self.conf_program['thread_downloader']['timeout']
        )

    def _worker_complete(self, urls_errors: list, error_msgs: list,
                         downloaded_pages: dict):
        """
        Вызывается, когда worker закончил скачивание
        :param downloaded_pages: страницы загруженные worker
        """
        self.count_completed_workers += 1

        for site_name, data in downloaded_pages.items():
            self._downloaded_pages.setdefault(site_name, []).extend(data)

        self._urls_errors.extend(urls_errors)
        self._error_msgs.extend(error_msgs)

        if (self.count_completed_workers == len(self._workers)
                and self.f_cancel_download is False):

            state = UpgradeState.OK
            if self.f_timeout_update:
                message = ('Первышено время обновления. Получены данные только'
                           ' с части сайтов')
                state = UpgradeState.WARNING
                self._error_msgs.append(message)
                self._logger.error(message)

            self.timeout_update_timer.stop()

            self.s_download_complete.emit(
                state, self._error_msgs, self._urls_errors,
                self._downloaded_pages
            )

    def _stop_download(self):
        self.f_timeout_update = True

        for i in self._workers:
            i.f_timeout_update = True

        self.timeout_update_timer.stop()

    def cancel_download(self):
        """
        Отменяет загрузку
        """
        self.f_cancel_download = True

        for i in self._workers:
            i.f_cancel_download = True

        self.timeout_update_timer.stop()

        self.s_download_complete.emit(
            UpgradeState.CANCELLED,
            ['Обновленние отменено пользователем'], [], {}
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
        self._urls_errors = []
        self._downloaded_pages = {}

    def set_proxy_for_session(self, url):
        if not self._use_proxy:
            return

        domain = "{0.scheme}://{0.netloc}/".format(urlsplit(url))
        try:
            proxy = gopac.find_proxy(self._pac_url, domain)
        except (ValueError, ErrorDecodeOutput, GoPacException) as e:
            self._session.proxies = {}
            self._urls_errors.append(f'Не удалось получить прокси для: {url}')
            self._logger.error(f'Не удалось получить прокси для {url}', e)
        else:
            self._session.proxies = proxy

    def clear_proxy_cache(self):
        if not self._use_proxy:
            return

        gopac.find_proxy.cache_clear()

    def fetch(self, url, recursion_deep=0):
        if recursion_deep == 2:
            return

        try:
            self.set_proxy_for_session(url)
            return self._session.get(
                url, timeout=5, hooks={'response': self.terminate_download}
            )
        except (DownloadCancel, TimeoutUpdate):
            raise
        except requests.exceptions.ConnectionError:
            self.clear_proxy_cache()
            message = f'Ошибка при подключении к: {url}'
            self._logger.error(message)
            self._urls_errors.append(message)
            self.fetch(url, recursion_deep + 1)
        except Exception as e:
            self.clear_proxy_cache()
            message = f'Непредвиденная ошибка при доступе к : {url}'
            self._logger.error(message, e)
            self._urls_errors.append(message)
            self.fetch(url, recursion_deep + 1)

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
                html = self.fetch(url)
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


class DownloadCancel(Exception):
    """
    Исключение сообщающие, что загрузку необходимо отметить
    """
    pass


class TimeoutUpdate(Exception):
    """
    Исключение сообщающие, что загрузку необходимо прервать
    """
    pass


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
