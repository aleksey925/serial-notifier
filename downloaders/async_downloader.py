import asyncio
from urllib.parse import urlsplit

import aiohttp
import async_timeout
from PyQt5 import QtCore
from gopac import gopac
from gopac.exceptions import ErrorDecodeOutput, GoPacException

from config_readers import SerialsUrls, ConfigsProgram
from downloaders.base_downloader import BaseDownloader
from upgrade_state import UpgradeState


class AsyncDownloader(BaseDownloader):
    """
    Асинхронных загрузчик данных с web страниц основанный на коррутинах
    """
    def __init__(self):
        super().__init__()

        self.console_encoding = self._conf_program['gopac']['console_encoding']
        self._use_proxy = self._conf_program['downloader']['use_proxy']

        self._semaphore: asyncio.BoundedSemaphore = None
        self._gather_tasks = None

    async def _get_proxy(self, url, site_name, serial_name):
        if not self._use_proxy or not self._downloaded_pac_file:
            return

        domain = "{0.scheme}://{0.netloc}/".format(urlsplit(url))
        try:
            proxy = await asyncio.get_event_loop().run_in_executor(
                None, gopac.find_proxy, self._downloaded_pac_file, domain,
                self.console_encoding
            )
        except (ValueError, ErrorDecodeOutput, GoPacException):
            message = f'Не удалось получить прокси для: {url}'
            self._urls_errors.setdefault(
                f'{site_name}_{serial_name}', list()
            ).append(message)
            self._logger.error(message, exc_info=True)
            return None
        else:
            return proxy.get('http', None)

    def clear_proxy_cache(self):
        if not self._use_proxy:
            return

        gopac.find_proxy.cache_clear()

    async def _fetch(self, session, site_name, serial_name, url):
        proxy = await self._get_proxy(url, site_name, serial_name)
        for i in range(2):
            try:
                async with self._semaphore, session.get(
                        url, proxy=proxy, allow_redirects=True) as response:
                    page = await response.text()
                    self._downloaded_pages[site_name].append(
                        [serial_name, page])
                    return
            except asyncio.CancelledError:
                # Пробрасываем ошибку дальше, потому что она сообщает об отмене
                # пользователем загрузки данных
                raise
            except ValueError:
                self.clear_proxy_cache()
                message = f'URL {url} имеет неправильный формат'
                self._urls_errors.setdefault(
                    f'{site_name}_{serial_name}', list()
                ).append(message)
                self._logger.error(message)
            except aiohttp.ClientConnectionError:
                self.clear_proxy_cache()
                message = f'Ошибка подключени к {url}'
                self._urls_errors.setdefault(
                    f'{site_name}_{serial_name}', list()
                ).append(message)
                self._logger.error(message)
            except Exception:
                message = (
                    f'Возникла непредвиденная ошибка при подключении к {url}'
                )
                self.clear_proxy_cache()
                self._urls_errors.setdefault(
                    f'{site_name}_{serial_name}', list()
                ).append(message)
                self._logger.error(message, exc_info=True)

    async def _wrapper_for_tasks(self):
        tasks = []

        async with aiohttp.ClientSession() as session:
            for site_name, site_data in self._target_urls.items():
                if len(site_data['urls']) == 0:
                    continue

                self._downloaded_pages[site_name] = []
                for i in site_data['urls']:
                    tasks.append(self._fetch(session, site_name, *i))

            if not tasks:
                self.s_download_complete.emit(
                    UpgradeState.CANCELLED,
                    ['sites.conf пуст, нет сериалов для отслеживания'],
                    self._urls_errors, self._downloaded_pages
                )
                return

            try:
                with async_timeout.timeout(
                        self._conf_program['async_downloader']['timeout'],
                        loop=session.loop):
                    self._gather_tasks = asyncio.gather(*tasks)
                    await self._gather_tasks
            except asyncio.TimeoutError:
                message = ('Первышено время обновления. Получены данные только'
                           ' с части сайтов')
                self.s_download_complete.emit(
                    UpgradeState.WARNING, [message], self._urls_errors,
                    self._downloaded_pages
                )
                self._logger.warning(message)
                return
            except asyncio.CancelledError:
                self.s_download_complete.emit(
                    UpgradeState.CANCELLED,
                    ['Обновленние отменено пользователем'], {}, {}
                )
                return

            self.s_download_complete.emit(
                UpgradeState.OK, [], self._urls_errors, self._downloaded_pages
            )

    def _before_start(self):
        self._semaphore = asyncio.BoundedSemaphore(
            self._conf_program['async_downloader']['concurrent_requests_count']
        )

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
                'ВКЛЮЧЕНО' if self._use_proxy else 'ВЫКЛЮЧЕНО'
            )
        )

        asyncio.ensure_future(self._wrapper_for_tasks())

    def cancel_download(self):
        self._downloader_initializer.cancel()
        if self._gather_tasks is not None:
            self._gather_tasks.cancel()
        else:
            self.s_download_complete.emit(
                UpgradeState.CANCELLED,
                ['Обновленние отменено пользователем'], {}, {}
            )

    def clear(self):
        self._downloaded_pages.clear()
        self._urls_errors.clear()
        self._gather_tasks = None


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
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    test = SelfTest()

    with loop:
        loop.run_forever()
