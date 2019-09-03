import logging

import dependency_injector.containers as cnt
import dependency_injector.providers as prv
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QMessageBox


class DIServices(cnt.DeclarativeContainer):
    serials_urls = prv.Provider()


class ValidatorMixin:
    _common_validators = {
        '{} не может содержать ";"': lambda i: ';' in i,
        '{} не может быть пустым': lambda i: len(i) == 0,
    }

    def validate_input(self, validators: dict = None) -> list:
        errors = []
        for i in (self._common_validators, validators or {}):
            errors.extend(self._validate_input(i))

        return errors

    def _validate_input(self, validators: dict):
        errors = []

        for field, field_name in self.list_input_field:
            for error_msg, validator in validators.items():
                if validator(field.text()):
                    errors.append(
                        f'<center>'
                        f'{error_msg.format(field_name.capitalize())}'
                        f'</center>'
                    )
        return errors


class AddNewTvSeriesWindows(QtWidgets.QDialog, ValidatorMixin):
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
        errors = self.validate_input()
        if errors:
            QMessageBox.warning(self, 'Ошибка', "\n".join(errors))
            return

        try:
            DIServices.serials_urls().add(
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

    def __call__(self, *args, **kwargs):
        self.show()


class RenameTvSeriesWindows(QtWidgets.QDialog, ValidatorMixin):
    def __init__(self, parent, serial_tree):
        super().__init__(parent)
        self.setFixedSize(400, 120)
        self.setModal(True)
        self.setLayout(QtWidgets.QVBoxLayout())

        self.main_window = parent
        self.serial_tree = serial_tree
        self.logger = logging.getLogger('serial-notifier')

        self.tv_serials_name_edit_label = QtWidgets.QLabel(
            'Введите новое название сериала'
        )
        self.new_tv_serials_name_edit = QtWidgets.QLineEdit()
        self.add_button = QtWidgets.QPushButton('Переименовать')

        self.list_input_field = (
            (self.new_tv_serials_name_edit, 'название сериала'),
        )

        self.init()

    def init(self):
        layout = self.layout()
        layout.addWidget(self.tv_serials_name_edit_label)
        layout.addWidget(self.new_tv_serials_name_edit)
        layout.addWidget(self.add_button)

        self.add_button.clicked.connect(self.rename_tv_serials)

    def rename_tv_serials(self):
        errors = self.validate_input()
        if errors:
            QMessageBox.warning(self, 'Ошибка', "\n".join(errors))
            return

        new_name = self.new_tv_serials_name_edit.text()
        if new_name == self.old_name:
            self.close()
            return

        try:
            DIServices.serials_urls().rename(
                self.old_name, new_name
            )
            self.serial_tree.model.setData(
                self.serial_tree.selected_element[1], new_name
            )
            self.main_window.s_send_db_task.emit(
                lambda: self.main_window.db_manager.rename_serial(
                    self.old_name, new_name
                )
            )
        except ValueError as err:
            QMessageBox.warning(self, 'Ошибка', ', '.join(err.args))
        except Exception:
            msg = 'При добавлении сериала возникла непредвиденная ошибка'
            self.logger.exception(msg)
            QMessageBox.warning(self, 'Ошибка', msg)
        else:
            self.close()

    def __call__(self, old_name):
        self.old_name = old_name
        self.new_tv_serials_name_edit.setText(old_name)
        self.show()


def unhandled_exception_message_box():
    QMessageBox.critical(
        None, 'Непредвиденная ошибка',
        'Возникла непредвиденная ошибка, приложение будет закрыто.'
    )
