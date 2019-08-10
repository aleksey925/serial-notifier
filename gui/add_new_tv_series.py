import logging

import dependency_injector.containers as cnt
import dependency_injector.providers as prv
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QMessageBox


class DIServises(cnt.DeclarativeContainer):
    serials_urls = prv.Provider()


class AddNewTvSeriesWindows(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(400, 180)
        self.setModal(True)
        self.setLayout(QtWidgets.QVBoxLayout())

        self.logger = logging.getLogger('serial-notifier')

        self.tv_serials_name_edit_label = QtWidgets.QLabel(
            'Введите название сериала'
        )
        self.tv_serials_name_edit = QtWidgets.QLineEdit()
        self.url_edit_label = QtWidgets.QLabel('Введите url сериала')
        self.url_edit = QtWidgets.QLineEdit()
        self.add_button = QtWidgets.QPushButton('Добавить сериал')

        self.init()

    def init(self):
        self.layout().addWidget(self.tv_serials_name_edit_label)
        self.layout().addWidget(self.tv_serials_name_edit)
        self.layout().addWidget(self.url_edit_label)
        self.layout().addWidget(self.url_edit)
        self.layout().addWidget(self.add_button)

        self.add_button.clicked.connect(self.adding_new_tv_serials)

    def adding_new_tv_serials(self):
        try:
            DIServises.serials_urls().add(
                self.tv_serials_name_edit.text(), self.url_edit.text()
            )
        except ValueError as err:
            QMessageBox.warning(self, 'Ошибка', ', '.join(err.args))
        except Exception as err:
            msg = 'При добавлении сериала возникла непрдвиденная ошибка'
            self.logger.exception()
            QMessageBox.warning(self, 'Ошибка', msg)
        else:
            self.close()

    def __call__(self, *args, **kwargs):
        self.show()
