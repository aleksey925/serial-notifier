"""
Реализация загрузки html страниц
"""
import asyncio
import logging

import aiohttp

from configparsers import SerialsUrls


class Downloader:
    """
    Асинхронный загрузчик HTML страниц сайтов с сериалами
    """
    def __init__(self, target_urls: SerialsUrls, limit=1000):
        self.limit = limit  # Количество одновременно скачиваемых страниц
        self.target_urls = target_urls
        self.semaphore = None
        self._logger = logging.getLogger('main')
        # todo хранить тут не только скачанные страницы, но ещё и ошибки
        self._downloaded_pages = {}

    @asyncio.coroutine
    def get(self, *args, **kwargs):
        response = yield from aiohttp.request('GET', *args, **kwargs)
        if response.status == 404:
            self._logger.error(
                'Сервер "{}" недоступен (404 error)'.format(args[0])
            )
            response.close()
            return '<html></html>'

        return (yield from response.text())

    @asyncio.coroutine
    def download_html(self, site_name, film_name, url):
        """
        Скачивает страницу и передает html для обработки куда-то дальше
        """
        with (yield from self.semaphore):
            try:
                page = yield from self.get(url)
            except ValueError:
                self._logger.error(
                    'URL "{}" имеет неправильный формат'.format(url)
                )
            except aiohttp.errors.ClientConnectionError:
                self._logger.error(
                    'Ошибка подключени к "{}". Возможно отсутствует '
                    'подключение к интернету.'.format(url)
                )
            else:
                self._downloaded_pages[site_name].append([film_name, page])

    @asyncio.coroutine
    def _task_wrapper(self, tasks: list, future: asyncio.Future):
        try:
            yield from asyncio.get_event_loop().create_task(
                asyncio.wait_for(asyncio.wait(tasks), 100)
            )
        except asyncio.TimeoutError:
            self._logger.error(
                'TimeoutError, первышено время обновления. Получены данные '
                'только с части сайтов'
            )

        future.set_result(self._downloaded_pages)

    def run(self, future: asyncio.Future):
        """
        Создает задачи и запускает их на исполнение
        """
        tasks = []
        self._downloaded_pages.clear()
        for site_name, urls in self.target_urls.urls.items():
            if len(urls) == 1 and urls[0][0] == '':
                continue

            self._downloaded_pages[site_name] = []
            for i in urls:
                tasks.append(self.download_html(site_name, *i))

        if not tasks:
            future.set_result({})
            return

        self.semaphore = asyncio.Semaphore(self.limit)
        asyncio.get_event_loop().create_task(self._task_wrapper(tasks, future))


if __name__ == '__main__':
    from configs import base_dir

    def res(data):
        print(data)
        print(data.result())
        loop.stop()

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    future = asyncio.Future()
    future.add_done_callback(res)

    urls = SerialsUrls(base_dir)
    d = Downloader(urls, logging.getLogger())
    d.run(future)

    loop.run_forever()