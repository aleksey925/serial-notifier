"""
Реализация загрузки html страниц
"""
import asyncio
import logging

import aiohttp

from setting import SerialsUrls


class Downloader:
    """
    Асинхронный загрузчик HTML страниц для парсинга
    """
    def __init__(self, target_urls: SerialsUrls, logger: logging.Logger, limit=1000):
        self.limit = limit  # Количество одновременно скачиваемых страниц
        self.target_urls = target_urls
        self.semaphore = None
        self.logger = logger
        self._downloaded_pages = {}

    @asyncio.coroutine
    def get(self, *args, **kwargs):
        response = yield from aiohttp.request('GET', *args, **kwargs)
        if response.status == 404:
            self.logger.error('Сервер "{}" недоступен (404 error)'.format(args[0]))
            response.close()
            return '<html></html>'

        return (yield from response.text())

    @asyncio.coroutine
    def downlaod_html(self, site_name, film_name, url):
        """
        Скачивает страницу и передает html для обработки куда-то дальше
        """
        with (yield from self.semaphore):
            try:
                page = yield from self.get(url)
            except ValueError:
                self.logger.error(
                    'URL "{}" имеет неправильный формат'.format(url)
                )
            except aiohttp.errors.ClientConnectionError:
                self.logger.error(
                    'Ошибка подключени к "{}". Возможно отсутствует '
                    'подключение к интернету.'.format(url)
                )
            else:
                self._downloaded_pages[site_name].append([film_name, page])

    @asyncio.coroutine
    def _run_wrapper(self, tasks: list, future: asyncio.Future):
        yield from asyncio.get_event_loop().create_task(asyncio.wait(tasks))
        future.set_result(self._downloaded_pages)

    def run(self, future: asyncio.Future):
        """
        Создает задачи и запускает их на исполнение
        """
        tasks = []
        self._downloaded_pages.clear()
        for site_name, urls in self.target_urls.urls.items():
            self._downloaded_pages[site_name] = []
            for i in urls:
                tasks.append(self.downlaod_html(site_name, *i))

        self.semaphore = asyncio.Semaphore(self.limit)
        asyncio.get_event_loop().create_task(self._run_wrapper(tasks, future))


if __name__ == '__main__':
    def res(data):
        print(data)
        print(data.result())
        loop.stop()

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    future = asyncio.Future()
    future.add_done_callback(res)

    urls = {
        'filin.tv': [
            ['Флэш 2', 'http://filin.tv/fantastika/3825-flesh-the-flash-2-sezon.html'],
            ['Колония', "http://filin.tv/fantastika/3973-koloniya-colony-1-sezon.html"],
            ['Пространство', "http://filin.tv/fantastika/3919-prostranstvo-the-expanse.html"],
            ['Гримм', "http://filin.tv/fantastika/1176-grimm-grimm-1-sezon-onlajn.html"],
        ],
        'seasonvar': [
            ['Вызов', 'http://seasonvar.ru/serial-11851-Vyzov_2013-3-season.html']
        ]
    }
    d = Downloader(urls, logging.getLogger())
    d.run(future)

    loop.run_forever()
