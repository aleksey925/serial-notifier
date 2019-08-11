import logging

import dependency_injector.containers as cnt
import dependency_injector.providers as prv
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QMessageBox


class DIServises(cnt.DeclarativeContainer):
    serials_urls = prv.Provider()


class AddNewTvSeriesWindows(QtWidgets.QDialog):

    validators = {
        '{} не может содержать ";"': lambda i: ';' in i,
        '{} не может быть пустым': lambda i: len(i) == 0,
    }

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

        self.list_input_field = (
            (self.url_edit, 'url сериала'),
            (self.tv_serials_name_edit, 'название сериала')
        )

        self.init()

    def init(self):
        layout = self.layout()
        layout.addWidget(self.tv_serials_name_edit_label)
        layout.addWidget(self.tv_serials_name_edit)
        layout.addWidget(self.url_edit_label)
        layout.addWidget(self.url_edit)
        layout.addWidget(self.add_button)

        self.add_button.clicked.connect(self.adding_new_tv_serials)

    def adding_new_tv_serials(self):
        errors = self._validate_input()
        if errors:
            QMessageBox.warning(self, 'Ошибка', "\n".join(errors))
            return

        try:
            DIServises.serials_urls().add(
                self.tv_serials_name_edit.text(), self.url_edit.text()
            )
        except ValueError as err:
            QMessageBox.warning(self, 'Ошибка', ', '.join(err.args))
        except Exception:
            msg = 'При добавлении сериала возникла непредвиденная ошибка'
            self.logger.exception(msg)
            QMessageBox.warning(self, 'Ошибка', msg)
        else:
            self.close()

    def _validate_input(self):
        errors = []

        for field, field_name in self.list_input_field:
            for error_msg, validator in self.validators.items():
                if validator(field.text()):
                    errors.append(
                        f'<center>'
                        f'{error_msg.format(field_name.capitalize())}'
                        f'</center>'
                    )

        return errors

    def __call__(self, *args, **kwargs):
        self.show()
