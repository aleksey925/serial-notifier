"""
Реализация загрузки html страниц
"""
import asyncio
import logging

import requests
import aiohttp
import async_timeout

from configparsers import SerialsUrls, ConfigsProgram


class Downloader:
    """
    Асинхронный загрузчик HTML страниц сайтов с сериалами
    """
    def __init__(self, target_urls: SerialsUrls, conf_program: ConfigsProgram):
        self.target_urls = target_urls
        self.conf_program = conf_program.conf
        self._logger = logging.getLogger('main')

        self._downloaded_pages = {}

    async def fetch(self, session, site_name, serial_name, url):
        try:
            async with session.get(url) as response:
                page = await response.text()
                self._downloaded_pages[site_name].append([serial_name, page])
        except ValueError:
            self._logger.error(
                'URL "{}" имеет неправильный формат'.format(url)
            )
        except aiohttp.errors.ClientConnectionError:
            self._logger.error(
                'Ошибка подключени к "{}". Возможно отсутствует '
                'подключение к интернету.'.format(url)
            )

    def _check_internet_access(self):
        try:
            requests.get('http://google.com')
            return True
        except requests.exceptions.ConnectionError:
            self._logger.info(
                'Отстуствует доступ в интернет, проверьте подключение'
            )
            return False

    async def run(self, future: asyncio.Future):
        if not self._check_internet_access():
            future.set_result({})
            return

        tasks = []

        async with aiohttp.ClientSession() as session:
            for site_name, urls in self.target_urls.urls.items():
                if len(urls) == 1 and urls[0][0] == '':
                    continue

                self._downloaded_pages[site_name] = []
                for i in urls:
                    tasks.append(asyncio.ensure_future(
                        self.fetch(session, site_name, *i))
                    )

            if not tasks:
                future.set_result({})
                return

            try:
                with async_timeout.timeout(self.conf_program['timeout_update'],
                                           loop=session.loop):
                    await asyncio.gather(*tasks)
            except asyncio.TimeoutError:
                self._logger.error(
                    'TimeoutError, первышено время обновления. Получены данные'
                    ' только с части сайтов'
                )

            future.set_result(self._downloaded_pages)


if __name__ == '__main__':
    from configs import base_dir

    def print_res(data):
        print(data.result())
        loop.stop()

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    future = asyncio.Future()
    future.add_done_callback(print_res)

    urls = SerialsUrls(base_dir)
    conf_program = ConfigsProgram(base_dir)
    d = Downloader(urls, conf_program)
    asyncio.ensure_future(d.run(future))

    loop.run_forever()
