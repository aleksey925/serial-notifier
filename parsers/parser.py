from PyQt5 import QtCore
from PyQt5.QtCore import Qt

from parsers.services import parse_serial_page


class AsyncHtmlParser(QtCore.QThread):
    """
    Запускает в отдельном потоке парсинг HTML старниц
    """
    s_data_ready = QtCore.pyqtSignal(object, object, name='data_ready')

    def __init__(self, s_send_parser_task):
        super(AsyncHtmlParser, self).__init__()
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
        serials_data, errors = parse_serial_page(self.data)
        self.s_data_ready.emit(serials_data, errors)

        self.data.clear()
