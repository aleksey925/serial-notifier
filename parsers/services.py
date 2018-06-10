"""
Реализация парсинга скаченых html страниц
Парсеры страниц сайта должны выдает словари вида:
{'Серия': [21], 'Сезон': 1}
{'Серия': [12, 13], 'Сезон': 3}
"""
import re
import logging
import traceback
from typing import Iterable, Union

import lxml.html


def filintv(page):
    """
    Извлекает c filin.tv текущую информацию о сезоне и сериях
    с переданного url
    P.S не отслеживает, если обновится целый сезон или несколько
    """
    parser = lxml.html.fromstring(page)

    # Ищем сезон в заголовке названия сериала
    season = parser.cssselect('div.block div.mainf noindex a')[0].text
    season = re.findall('\(.{0,}-{0,1},{0,1}((\d+) сезон)', season, re.I)

    try:
        season = season[0][1]
    except IndexError:
        # Возникает, когда на пример 1 сезон только идет и в названии
        # не указаны вышедшие сезоны
        season = '1'

    series = parser.cssselect(
        'div.ssc table tr td strong:nth-child(1)'
    )[0].text.lower()

    if '(Оригинал)' in series:
        return
    elif 'серия' in series and 'сезон' in series:
        # Правильный номер серии и сезона у некоторых сериалов указывается
        # в скобках рядом с номер серии
        series = series.replace('c', 'с')  # меняем латинскую букву на русскую
        series, season = re.findall('(\d+) серия.*(\d+) сезон', series, re.I)[0]
    else:
        series = series.split()[0]

    # Проверяем сколько серий вышло, 1 или несколько
    if '-' in series:
        series = list(range(*list(map(int, series.split('-')))))
        series.append(series[-1] + 1)
    else:
        series = [int(series)]

    return {'Серия': series, 'Сезон': int(season)}


def seasonvar(page):
    parser = lxml.html.fromstring(page)

    for i in parser.cssselect('div.svtabr_wrap.show.seasonlist h2'):
        try:  # Только у последнего сезона есть тег span
            data = i.cssselect('a')[0].text + i.cssselect('a span')[0].text
        except IndexError:
            pass
        else:
            season = re.findall('(\d+) сезон', data)
            season = int(season[0]) if season else 1

            try:
                series = re.findall('(\d+-{0,1}\d{0,}) серия.{0,}\)', data)[0]
            except IndexError:
                # Возникает если попадается строка без указания вышедшей серии
                # (25.05.2016 сезон полностью (Субтитры) из 16)
                series = re.findall('из (\d+)', data)[0]

            # Проверяем сколько серий вышло, 1 или несколько
            if '-' in series:
                series = list(range(*list(map(int, series.split('-')))))
                series.append(series[-1] + 1)
            else:
                series = [int(series)]

            return {'Серия': series, 'Сезон': season}


def filmixme(page):
    parser = lxml.html.fromstring(page)
    data = parser.cssselect('.added-info')[0].text
    series = re.findall('([\d-]+) серия', data, re.IGNORECASE)
    season = re.findall('([\d-]+) сезон', data, re.IGNORECASE)

    if not series:
        raise Exception

    season = 1 if not season else int(season[0])

    if series[0].find('-') != -1:
        series = list(range(*list(map(int, series[0].split('-')))))
        series.append(series[-1] + 1)
    else:
        series = [int(series[0])]

    return {'Серия': series, 'Сезон': season}


parsers = {
    'filin.tv': filintv,
    'seasonvar': seasonvar,
    'filmix.me': filmixme
}


def parse_serial_page(serial_raw_data: dict) -> Iterable[Union[dict, dict]]:
    """
    Вытаскивает с html страниц данные о последней вышешей серии
    :param serial_raw_data HTML страницы с информацией о сериалах
    """
    result = {}
    errors = {}
    logger = logging.getLogger('serial-notifier')

    for site_name, pages in serial_raw_data.items():
        result[site_name] = {}
        for serial_name, html_page in pages:
            try:
                res = parsers[site_name](html_page)
            except Exception:
                message = f'Ошибка парсинга. {site_name}: {serial_name}'
                errors[f'{site_name}_{serial_name}'] = [message]
                logger.error(message + f'\n{traceback.format_exc()}')
            else:
                if res:
                    result[site_name][serial_name] = res

    return result, errors
