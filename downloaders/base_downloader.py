from abc import ABCMeta, abstractmethod

from PyQt5 import QtCore
from sip import wrappertype

from upgrade_state import UpgradeState


class BaseDownloaderMetaClass(wrappertype, ABCMeta):
    """
    Нужен для решения конфликта при наследовании двух метаклассов
    """
    pass


class BaseDownloader(QtCore.QObject, metaclass=BaseDownloaderMetaClass):

    s_download_complete = QtCore.pyqtSignal(
        UpgradeState, list, list, dict, name='download_complete'
    )

    @abstractmethod
    def start(self):
        raise NotImplementedError

    @abstractmethod
    def cancel_download(self):
        raise NotImplementedError

    @abstractmethod
    def clear(self):
        raise NotImplementedError
