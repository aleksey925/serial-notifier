import logging
from abc import ABCMeta, abstractmethod

import gopac
import gopac.exceptions
import requests
import dependency_injector.containers as cnt
import dependency_injector.providers as prv
from PyQt5 import QtCore
from sip import wrappertype

from config_readers import SerialsUrls, ConfigsProgram
from upgrade_state import UpgradeState


class DIServises(cnt.DeclarativeContainer):
    conf_program = prv.Provider()
    serials_urls = prv.Provider()


class BaseDownloaderMetaClass(wrappertype, ABCMeta):
    """
    Нужен для решения конфликта при наследовании двух метаклассов
    """
    pass


class BaseDownloader(QtCore.QObject, metaclass=BaseDownloaderMetaClass):

    s_download_complete = QtCore.pyqtSignal(
        UpgradeState, list, dict, dict, name='download_complete'
    )

    def __init__(self):
        super().__init__()

        self._urls_errors = {}
        self._error_msgs = []
        self._downloaded_pages = {}
        self._downloaded_pac_file: str = ''
        self._target_urls: SerialsUrls = DIServises.serials_urls()
        self._conf_program: ConfigsProgram = DIServises.conf_program()
        self._downloader_initializer = DownloaderInitializer()
        self._logger = logging.getLogger('serial-notifier')

        self._downloader_initializer.s_init_complete.connect(
            self._start, QtCore.Qt.QueuedConnection
        )

    def start_download(self):
        """
        Запускает загрузку информации о новых сериях
        """
        self._before_start()
        self._downloader_initializer.run_init()

    def _before_start(self):
        pass

    @abstractmethod
    def _start(self, internet_available: bool, downloaded_pac_file: str):
        """
        Запускает скачивание если интернет доступен
        :param internet_available: логический параметр отражающий доступность
        интернета
        :param downloaded_pac_file: путь к скачанному pac файлу
        """
        raise NotImplementedError()

    @abstractmethod
    def cancel_download(self):
        """
        Отменяет загрузку
        """
        raise NotImplementedError()

    @abstractmethod
    def clear(self):
        """
        Очищает структуры данных используемые downloader`ом
        """
        raise NotImplementedError()


class DownloaderInitializer(QtCore.QThread):

    s_init_complete = QtCore.pyqtSignal(bool, str, name='init_complete')

    def __init__(self):
        super().__init__()
        self.f_stop = False
        self.logger = logging.getLogger('serial-notifier')
        self.conf_program = DIServises.conf_program()

    def run(self):
        self.f_stop = False

        try:
            requests.get(
                self.conf_program['downloader']['check_internet_access_url'],
                timeout=15,
                hooks={'response': self._terminate_check}
            )
        except DownloadCancel:
            self.logger.debug(
                'Загрузка отменена на этапе проверки доступности интернета'
            )
            return
        except Exception:
            self.logger.error('Отстуствует доступ в интернет')
            self.s_init_complete.emit(False, '')
            return

        downloaded_pac_file = ''
        if self.conf_program['downloader']['use_proxy']:
            try:
                downloaded_pac_file = gopac.download_pac_file(
                    self.conf_program['downloader']['pac_file']
                )
            except gopac.exceptions.DownloadCancel:
                self.logger.debug(
                    'Загрузка отменена на этапе загрузки PAC файла'
                )
                return
            except gopac.exceptions.SavePacFileException:
                self.logger.error(
                    'Возникла ошибка при сохранении pac файла', exc_info=True
                )
            except Exception:
                self.logger.error(
                    'Ошибка при получении pac файла', exc_info=True
                )

        self.s_init_complete.emit(True, downloaded_pac_file)

    def run_init(self):
        self.start()

    def cancel(self):
        gopac.terminate_download_pac_file()
        self.f_stop = True

    def _terminate_check(self, *args, **kwargs):
        if self.f_stop:
            raise DownloadCancel()


class DownloadCancel(Exception):
    """
    Исключение сообщающие, что загрузку необходимо отметить
    """
    pass
