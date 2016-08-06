"""
Моудль с асинхронными обработчиками данных
"""
import asyncio

from queue import Queue

from PyQt4 import QtCore
from PyQt4.QtCore import Qt, pyqtSignal
from sqlalchemy import and_

from common.downloader import Downloader
from common.parser import parse_serial_page
from common.common import create_db_session
from model import Serial, Series


class UpgradeTimer(QtCore.QTimer):
    """
    Планировщик обновления данных в бд. Запускает через заданный промежуток
    времени обновление данных. Поддерживает ручной вызов обновления.
    """

    # Отправляет данные для парсинга
    s_send_data_parser = pyqtSignal(object, name='send_data_parser')

    s_upgrade_complete = pyqtSignal(object, object, object,
                                    name='upgrade_complete')

    def __init__(self, db_worker, urls, conf_program, logger):
        super(UpgradeTimer, self).__init__()

        # Сигнализирует производится уже обработка данных или нет
        self.flag_progress = Queue(maxsize=1)
        self.urls = urls
        self.conf_program = conf_program
        self.logger = logger

        self.loader = Downloader(self.urls, self.logger)

        self.db_worker = db_worker
        self.db_worker.s_status_update.connect(self.upgrade_db_complete,
                                               Qt.QueuedConnection)

        self.parser = ParserHTML(self.s_send_data_parser)
        self.parser.s_data_ready.connect(self.parse_complete)

        # Запускаем таймер
        self.timeout.connect(lambda: self.run('timer'))
        self.start(self.conf_program.conf['timeout_refresh'])

    def run(self, type_run):
        """
        Запускает процесс обновления данных в базе
        :argument type_run Определяет как было запущено обновление (вручную или
        по таймеру). Принимает значения: timer или user
        """
        # Если обновление базы не производится прямо сейчас, то можно запустить
        # процесс
        if self.flag_progress.empty():
            self.urls.read()
            self.flag_progress.put(type_run)
            f_download_complete = asyncio.Future()
            f_download_complete.add_done_callback(self.download_complete)

            self.loader.run(f_download_complete)

    def download_complete(self, downloaded_pages: asyncio.Future):
        """
        Получает HTML старницы и запускает парсинг
        """
        self.s_send_data_parser.emit(downloaded_pages.result())

    def parse_complete(self, serials_data: dict):
        """
        Получает данные извлеченные из скаченых HTML старниц отпрвляет их
        для обновления БД

        :param serials_data Данные о сериалах полученые после парсинга HTML
        Пример:
        {'filin.tv': {'Теория Большого взрыва': {'Серия': [17], 'Сезон': 1},}
        """
        self.db_worker.s_send_db_task.emit(
            lambda: self.db_worker.upgrade_db(serials_data)
        )

    def upgrade_db_complete(self, status: str, serials_with_updates: dict):
        """
        :param status Указывает успешно или нет завершилась операция обновления
        базы данных. Может получить "ok" или  "error".
        :param serials_with_updates
        """
        type_run = self.flag_progress.get()
        self.s_upgrade_complete.emit(status, serials_with_updates, type_run)


class ParserHTML(QtCore.QThread):
    """
    Запускает в отдельном потоке парсинг HTML старниц
    """
    s_data_ready = QtCore.pyqtSignal(object, name='data_ready')

    def __init__(self, s_send_parser_task):
        super(ParserHTML, self).__init__()
        self.s_send_data_parser = s_send_parser_task
        self.s_send_data_parser.connect(self.set_data, Qt.QueuedConnection)

        self.data = {}  # Данные для парсинга

    def set_data(self, data):
        """
        Принимает данные, которые нужно разобрать и запускает парсинг
        :argument data Данные для парсинга
        """
        self.data = data
        self.start()

    def run(self):
        serials_data = parse_serial_page(self.data)
        self.s_data_ready.emit(serials_data)

        self.data.clear()  # fixme


class DBWorker(QtCore.QThread):
    """
    Выполняет запросы к БД в отдельном потоке, для того, чтобы не
    блокировать GUI
    """
    s_serials_extracted = QtCore.pyqtSignal(object, name='serials_extracted')
    s_status_update = QtCore.pyqtSignal(object, object, name='status_update')

    def __init__(self, s_send_db_task):
        super(DBWorker, self).__init__()
        self.target = object
        self.s_send_db_task = s_send_db_task

        self.db_session = None

        self.s_send_db_task.connect(self.fill_target, Qt.QueuedConnection)

    def run(self):
        self.db_session = create_db_session()
        try:
            self.target()
        except Exception:
            self.db_session.rollback()
        finally:
            self.db_session.close()

    def fill_target(self, func):
        self.target = func
        self.start()

    def get_serials(self):
        """
        Извлекает из базы все сериалы и все данные о них
        """
        all_serials = self.db_session.query(Serial).all()

        result = [self._parse_serial(serial) for serial in all_serials]
        self.s_serials_extracted.emit(result)

    def _parse_serial(self, current_serial):
        """
        Приводит данные о сериале полученные из базы данных в вид необходимый
        для дальнейшей работы вид.
        :argument current_serial: Serial сериал данные которого будут
        разбираться
        """
        result = {'name': current_serial.name}

        not_viewed_season = self.db_session.query(
            Series.season_number.distinct()
        ).filter(
            Series.id_serial == current_serial.id, Series.looked.is_(False)
        ).all()

        result['not_looked_season'] = [i[0] for i in not_viewed_season]
        result['serial_looked'] = not bool(result['not_looked_season'])

        # Собираем серии в сезоны
        seasons = {}
        for j in current_serial.all_series:
            seasons.setdefault(j.season_number, []).append((j.series_number,
                                                            j.looked))
            result['seasons'] = seasons

        return result

    def change_status(self, data, status, level):
        """
        Ставит у сериала пометку, что серия/серии просмотрены
        """
        if level == 0:
            series = self.db_session.query(Series).filter(
                Serial.name == data['name'], Series.id_serial == Serial.id
            ).all()
        elif level == 1:
            series = self.db_session.query(Series).filter(
                Serial.name == data['name'], Series.id_serial == Serial.id,
                Series.season_number == data['season']
            ).all()
        elif level == 2:
            series = self.db_session.query(Series).filter(
                Serial.name == data['name'], Series.id_serial == Serial.id,
                Series.season_number == data['season'],
                Series.series_number == data['series']
            ).all()

        for i in series:
            i.looked = status

        try:
            self.db_session.commit()
        except Exception:
            self.db_session.rollback()
        else:
            self.get_serials()

    def upgrade_db(self, serials_data: dict):
        """
        Получает распарсенные данные и тех, что нету в БД добавляет.

        :argument serials_data Данные о сериалах
        Пример:
        {'filin.tv': {'Незабываемое': {'Серия': (13,), 'Сезон': 4}}}
        """
        new_data = {}

        for site_name, serials_data in serials_data.items():
            serials_in_db = tuple(
                i[0] for i in self.db_session.query(Serial.name).all()
            )
            for serial_name, data in serials_data.items():

                if serial_name in serials_in_db:
                    # Обновляем в базе инфомрацию о сериале
                    temp = self.update_serial(serial_name, data)
                    if temp:
                        new_data.setdefault(site_name, {})[serial_name] = temp
                else:
                    # Добавляем в базу информацию о новом сериале
                    self.add_new_serial(serial_name, data)
                    new_data.setdefault(site_name, {})[serial_name] = data
        try:
            self.db_session.commit()
            self.s_status_update.emit('ok', new_data)
        except Exception:
            self.db_session.rollback()
            self.s_status_update.emit('error', new_data)

    def update_serial(self, serial_name, serial_data):
        """
        Проверяет, что добавляемых о сериале данных нет в БД и если данных
        действительно нет, то добавляет их

        :param serial_name Название сериала
        :param serial_data Данные сериала (текущий сезон, новые серии и т д)
        """
        current_serial = self.db_session.query(Serial).filter(
            Serial.name == serial_name,
        ).first()

        kwargs = {
            'id_serial': current_serial.id,
            'season_number': serial_data['Сезон']
        }

        new_data = self._check_updates(serial_name, serial_data['Сезон'],
                                       serial_data['Серия'])

        if new_data:
            current_serial.all_series.extend(
                [Series(series_number=i, **kwargs) for i in new_data['Серия']]
            )
            return new_data
        else:
            return None

    def add_new_serial(self, serial_name, serial_data):
        """
        Добавляет в базу сериал, которого там ещё нет
        :param serial_name Название сериала
        :param serial_data Данные сериала (текущий сезон, серии и т д)
        """
        current_serial = Serial(name=serial_name)

        kwargs = {
            'id_serial': current_serial.id,
            'season_number': serial_data['Сезон']
        }

        current_serial.all_series.extend(
            [Series(series_number=i, **kwargs) for i in serial_data['Серия']]
        )

        self.db_session.add(current_serial)

    def _check_updates(self, serial_name: str, season: str, series: list):
        """
        Проверяет появились новые серии или нет. Если есть новые серии, то
        возврщаются те, которых нет в базе, если ничего нового не появилось
        возращается None
        """
        res = self.db_session.query(Series.series_number).filter(
            and_(
                Serial.name == serial_name,
                Serial.id == Series.id_serial,
                Series.season_number == season,
                Series.series_number.in_(series)
            )
        ).all()
        res = tuple(set(series).difference({i[0] for i in res}))
        if res:
            return {'Сезон': season, 'Серия': res}
        else:
            return