import asyncio
import logging
import concurrent.futures

import aiohttp
import async_timeout
from PyQt5 import QtCore

from config_readers import SerialsUrls, ConfigsProgram
from downloaders.base_downloader import BaseDownloader
from upgrade_state import UpgradeState


# todo добавить поддержку прокси
class AsyncDownloader(BaseDownloader):
    """
    Асинхронных загрузчик данных с web страниц основанный на коррутинах
    """
    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger('serial-notifier')

        self._gather_tasks = None
        self._downloaded_pages = {}
        self._urls_errors = []

    async def _fetch(self, session, site_name, serial_name, url):
        try:
            async with session.get(url) as response:
                page = await response.text()
                self._downloaded_pages[site_name].append([serial_name, page])
        except ValueError:
            message = f'URL {url} имеет неправильный формат'
            self._urls_errors.append(message)
            self._logger.error(message)
        except aiohttp.ClientConnectionError:
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

    async def _run(self):
        tasks = []

        async with aiohttp.ClientSession() as session:
            for site_name, site_data in self.target_urls.data.items():
                if len(site_data['urls']) == 0:
                    continue

                self._downloaded_pages[site_name] = []
                for i in site_data['urls']:
                    tasks.append(asyncio.ensure_future(
                        self._fetch(session, site_name, *i))
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
                        self.conf_program['async_downloader']['timeout_update'],
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
        """
        self._downloaded_pages.clear()
        self._urls_errors.clear()
        self._gather_tasks = None

    def start(self):
        """
        Запускает асинхронное скачивание информации о новых сериях
        """
        self.get_internet_status()

    def check_internet_access(self, is_available: bool):
        if not is_available:
            self.s_download_complete.emit(
                UpgradeState.ERROR, ['Отстуствует соединение с интернетом'],
                [], {}
            )
            return

        asyncio.ensure_future(self._run())

    def cancel_download(self):
        """
        Отменяет загрузку
        """
        self._gather_tasks.cancel()


if __name__ == '__main__':
    import dependency_injector.containers as cnt
    import dependency_injector.providers as prv
    from quamash import QEventLoop

    from downloaders import base_downloader
    from configs import base_dir

    class DIServises(cnt.DeclarativeContainer):
        conf_program = prv.Singleton(ConfigsProgram, base_dir=base_dir)
        serials_urls = prv.Singleton(SerialsUrls, base_dir=base_dir)

    base_downloader.DIServises.override(DIServises)

    class SelfTest(QtCore.QObject):
        def __init__(self):
            super().__init__()
            self.downloader = AsyncDownloader()

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
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    test = SelfTest()

    with loop:
        loop.run_forever()
