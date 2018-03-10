import asyncio
import logging
import concurrent.futures

import requests
import aiohttp
import async_timeout
from PyQt5 import QtCore

from config_readers import SerialsUrls, ConfigsProgram
from upgrade_state import UpgradeState


class AsyncDownloader(QtCore.QObject):
    """
    Асинхронных загрузчик данных с web страниц основанный на коррутинах
    """
    s_download_complete = QtCore.pyqtSignal(
        UpgradeState, list, list, dict, name='download_complete'
    )

    def __init__(self, target_urls: SerialsUrls, conf_program: ConfigsProgram):
        super().__init__()
        self.target_urls = target_urls
        self.conf_program = conf_program.data['general']
        self._logger = logging.getLogger('main')

        self._gather_tasks = None
        self._downloaded_pages = {}
        self._urls_errors = []

    async def fetch(self, session, site_name, serial_name, url):
        try:
            async with session.get(url) as response:
                page = await response.text()
                self._downloaded_pages[site_name].append([serial_name, page])
        except ValueError:
            message = f'URL {url} имеет неправильный формат'
            self._urls_errors.append(message)
            self._logger.error(message)
        except aiohttp.errors.ClientConnectionError:
            message = f'Ошибка подключени к {url}'
            self._urls_errors.append(message)
            self._logger.error(message)
        except Exception as e:
            if isinstance(e, asyncio.CancelledError):
                # Пробрасываем ошибку дальше, потому что она сообщает об отмене
                # пользователем загрузки данных
                raise
            else:
                self._urls_errors.append(
                    f'Возникла непредвиденная ошибка при подключении к {url}'
                )
                self._logger.error(f'{e.__class__.__name__} {url}')

    def _check_internet_access(self):
        try:
            requests.get('http://google.com')
            return True
        except requests.exceptions.ConnectionError:
            self._logger.info(
                'Отстуствует соединения с интернетом'
            )
            return False

    async def run(self):
        if not self._check_internet_access():
            self.s_download_complete.emit(
                UpgradeState.ERROR, ['Отстуствует соединения с интернетом'],
                self._urls_errors, self._downloaded_pages
            )
            return

        tasks = []

        async with aiohttp.ClientSession() as session:
            for site_name, site_data in self.target_urls.data.items():
                if len(site_data['urls']) == 0:
                    continue

                self._downloaded_pages[site_name] = []
                for i in site_data['urls']:
                    tasks.append(asyncio.ensure_future(
                        self.fetch(session, site_name, *i))
                    )

            if not tasks:
                self.s_download_complete.emit(
                    UpgradeState.CANCELLED,
                    ['sites.conf пуст, нет сериалов для отслеживания'],
                    self._urls_errors, self._downloaded_pages
                )
                return

            try:
                with async_timeout.timeout(
                        self.conf_program['timeout_update'],
                        loop=session.loop):
                    try:
                        self._gather_tasks = asyncio.gather(*tasks)
                        await self._gather_tasks
                    except concurrent.futures.CancelledError:
                        self.s_download_complete.emit(
                            UpgradeState.CANCELLED,
                            ['Обновленние отменено пользователем'], [], {}
                        )
                        return
            except asyncio.TimeoutError:
                message = ('TimeoutError, первышено время обновления. '
                           'Получены данные только с части сайтов')
                self.s_download_complete.emit(
                    UpgradeState.WARNING, [message], self._urls_errors,
                    self._downloaded_pages
                )
                self._logger.error(message)
                return

            self.s_download_complete.emit(
                UpgradeState.OK, [], self._urls_errors, self._downloaded_pages
            )

    def clear(self):
        """
        Очищается структуры данных используемые downloader`ом
        :return:
        """
        self._downloaded_pages.clear()
        self._urls_errors.clear()
        self._gather_tasks = None

    def start(self):
        """
        Запускает асинхронное скачивание информации о новых сериях
        """
        asyncio.ensure_future(self.run())

    def cancel_download(self):
        """
        Отменяет загрузку
        """
        self._gather_tasks.cancel()


if __name__ == '__main__':
    from quamash import QEventLoop
    from configs import base_dir

    class SelfTest(QtCore.QObject):
        def __init__(self):
            super().__init__()
            self.urls = SerialsUrls(base_dir)
            self.conf_program = ConfigsProgram(base_dir)
            self.downloader = AsyncDownloader(self.urls, self.conf_program)

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

    loop = asyncio.get_event_loop()
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    test = SelfTest()

    loop.run_forever()
