import sys
import time
from os.path import join, exists, split

from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QCoreApplication

from gui.widgets import SearchLineEdit, SortFilterProxyModel, BoardNotification
from workers import UpgradeTimer
from db.managers import DbManager
from loggers import create_logger
from configparsers import SerialsUrls, ConfigsProgram
from configs import base_dir


class SystemTrayIcon(QtGui.QSystemTrayIcon):
    def __init__(self, parent=None):
        super(SystemTrayIcon, self).__init__(parent)
        self.setIcon(QtGui.QIcon(join(base_dir, 'icons/app-icon-48x48.png')))
        self.activated.connect(self.click_trap)

        self.main_window = parent

        # Элементы меню
        self.a_open = None
        self.a_update = None
        # self.a_load_from_bd = None
        self.a_exit = None

        self.build_menu()
        self.show()

    def click_trap(self, reason):
        """
        Вызывается при взаимодействии с иконой в трее и определяет, какое
        действие произошло
        """
        # left click!
        if reason == self.Trigger and sys.platform != 'darwin':
            self.show_hide_window()

    def show_hide_window(self):
        if self.main_window.isVisible() and self.main_window.isActiveWindow():
            self.main_window.hide()
        else:
            self.show_window()

    def build_menu(self):
        menu = QtGui.QMenu(self.parent())

        self.a_open = menu.addAction('Открыть', self.show_window)
        self.a_update = menu.addAction('Обновить')
        # self.a_load_from_bd = menu.addAction('Синхронизировать с БД')
        self.a_exit = menu.addAction('Выйти', QCoreApplication.instance().exit)

        self.setContextMenu(menu)

    def show_window(self):
        self.parent().show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    @staticmethod
    def prepare_message(data):
        result_message = ''
        for site_name, serials in data.items():
            result_message += '{}\n'.format(site_name)
            for serial_name, i in serials.items():
                result_message += '{}: Сезон {}, Серия {}\n'.format(
                    serial_name, i['Сезон'], ', '.join(map(str, i['Серия']))
                )
            result_message += '\n'
        return result_message.strip()

    def update(self):
        self.a_update.setDisabled(True)
        # self.a_load_from_bd.setDisabled(True)

    def update_done(self):
        self.a_update.setDisabled(False)
        # self.a_load_from_bd.setDisabled(False)


class SerialTree(QtGui.QWidget):
    """
    Виджет для отображения списка сериалов
    """
    def __init__(self, parent=None):
        super(SerialTree, self).__init__(parent)
        self.main_window = parent

        # Сюда заносится элемент для которого вызвали контекстное меню
        self._selected_element = ()

        self.looked_status = {
            'True': QtGui.QIcon(join(base_dir, 'icons/tick_green.png')),
            'False': QtGui.QIcon(join(base_dir, 'icons/tick_red.png'))
        }

        # Виджеты
        self.view = QtGui.QTreeView()
        self.model = QtGui.QStandardItemModel()
        self.filter_by_name = SortFilterProxyModel()
        self.context_menu = QtGui.QMenu()

        self.build_widgets()
        self.create_context_menu()

    def build_widgets(self):
        self.view.setIconSize(QtCore.QSize(18, 18))
        self.view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._open_menu)
        self.view.setSortingEnabled(True)

        self.model.setHorizontalHeaderLabels(['Сериалы'])
        self.view.setModel(self.model)

        # Создаем фильтры
        # Фильрует отображаемые сериалы во view
        self.filter_by_name.setSourceModel(self.model)
        self.view.setModel(self.filter_by_name)

        main_layout = QtGui.QVBoxLayout()
        main_layout.addWidget(self.view)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

    def create_context_menu(self):
        self.context_menu.addAction('Смотрел',
                                    lambda: self.change_status(True))
        self.context_menu.addAction('Не смотрел',
                                    lambda: self.change_status(False))

    def change_status(self, status):
        res = {'name': None, 'season': None, 'series': ''}
        root = self._get_root_parent(self._selected_element[1])
        for i in root:
            if 'Сезон' not in i[0] and 'Серия' not in i[0]:
                res['name'] = i[0]
            elif 'Сезон' in i[0]:
                res['season'] = i[0].replace('Сезон ', '')
            elif 'Серия' in i[0]:
                res['series'] = i[0].replace('Серия ', '')

        self.main_window.s_send_db_task.emit(
            lambda: self.main_window.db_worker.change_status(
                res, status, self._selected_element[0])
        )

    def _get_root_parent(self, element):
        """
        Возврщает дерево родителей элемента по которму щелкнули в виджете
        """
        all_parents = []

        while True:
            data = element.data()
            if data:
                all_parents.append((data, element.parent()))
            else:
                break
            element = element.parent()

        return all_parents[::-1]

    def _open_menu(self, position):
        """
        Создает контекстное меню по щелчку
        """
        indexes = self.view.selectedIndexes()

        if len(indexes) > 0:
            level = 0
            index = indexes[0]
            while index.parent().isValid():
                index = index.parent()
                level += 1

        self._selected_element = (level, indexes[0])
        self.context_menu.exec_(self.view.viewport().mapToGlobal(position))

    def add_items(self, elements: list):
        for i in elements:
            self.add_item(i)

    def add_item(self, element: dict):
        """
        Осуществляет загрузку сериала в виджет
        :argument element: dict Сериал со всеми даными, которые потребудется
        загрузить в виджет
        """
        root = QtGui.QStandardItem(element['name'])
        root.setEditable(False)
        root.setIcon(self.looked_status[str(element['serial_looked'])])
        self.model.appendRow(root)

        for num_season, series in element['seasons'].items():
            season = QtGui.QStandardItem('Сезон {}'.format(num_season))
            season.setEditable(False)
            if num_season in element['not_looked_season']:
                season.setIcon(self.looked_status['False'])
            else:
                season.setIcon(self.looked_status['True'])
            root.appendRow(season)

            for i in series:
                s = QtGui.QStandardItem('Серия {}'.format(i[0]))
                s.setEditable(False)
                s.setIcon(self.looked_status[str(i[1])])
                season.appendRow(s)


class MainWindow(QtGui.QMainWindow):

    # Служит для отправки заданий в DbManager
    s_send_db_task = QtCore.pyqtSignal(object, name='send_task')

    def __init__(self):
        super(MainWindow, self).__init__()

        # Настройки данного окна
        self.set_position()
        self.main_layout = QtGui.QGridLayout()
        main_widget = QtGui.QWidget()
        main_widget.setLayout(self.main_layout)
        self.setCentralWidget(main_widget)

        # Виджеты
        self.tray_icon = SystemTrayIcon(parent=self)
        self.search_field = SearchLineEdit(self)
        self.lab_search_field = QtGui.QLabel('Поиск: ')
        self.serial_tree = SerialTree(parent=self)
        self.notice = BoardNotification()

        self.logger = create_logger(join(base_dir, 'log.txt'), self.tray_icon)
        self.urls = SerialsUrls(base_dir)
        self.conf_program = ConfigsProgram(base_dir)

        # Различные асинхронные обработчики
        self.db_worker = DbManager(self.s_send_db_task)
        self.db_worker.s_serials_extracted.connect(self.update_list_serial,
                                                   QtCore.Qt.QueuedConnection)

        self.upgrade_timer = UpgradeTimer(self.db_worker, self.urls,
                                          self.conf_program, self.logger)
        self.upgrade_timer.s_upgrade_complete.connect(self.upgrade_complete)

        self.init_widgets()
        self.load_serials_from_db()

    def init_widgets(self):
        self.tray_icon.a_update.triggered.connect(self.run_upgrade)
        # self.tray_icon.a_load_from_bd.triggered.connect(self.load_serials_from_db)

        self.main_layout.addWidget(self.lab_search_field, 0, 0)

        self.search_field.textChanged.connect(self.change_filter_str)
        self.main_layout.addWidget(self.search_field, 0, 1)

        self.serial_tree.setMinimumSize(270, 100)
        self.main_layout.addWidget(self.serial_tree, 1, 0, 1, 2)

        self.main_layout.addWidget(self.notice, 1, 2, 1, 2)

    def set_position(self):
        screen = QtGui.QDesktopWidget().screenGeometry()
        self.setGeometry(0, 0, 430, 500)
        self.move(screen.width() - 320, 0)

    def change_filter_str(self, new_str):
        filter_string = QtCore.QRegExp(
            new_str, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.RegExp
        )
        self.serial_tree.filter_by_name.setFilterRegExp(filter_string)

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def run_upgrade(self, future):
        """
        Запускает процесс получения и парсинга новых данных с сайтов
        """
        self.upgrade_timer.run('user')
        self.tray_icon.a_update.setDisabled(True)
        # self.tray_icon.a_load_from_bd.setDisabled(True)

    def upgrade_complete(self, status, serials_with_updates, type_run):
        """
        Вызывается после завершения обновления БД, чтобы включить отключеные
        кнопки меню и уведомить пользователя о новых сериях если таковые
        появились
        """
        # todo выводить сообщения об ошибке в 1 месте, а не тут и через логер
        if serials_with_updates and status == 'ok':
            self.load_serials_from_db()
            message = self.tray_icon.prepare_message(serials_with_updates)
            self.tray_icon.showMessage('В курсе новых серий', message)
            self.notice.add_notification(message)

            if exists(split(self.conf_program.conf['file_notifications'])[0]):
                with open(self.conf_program.conf['file_notifications'], 'a') as out:
                    out.write('{time} {message}\n'.format(
                        time=time.strftime('(%Y-%m-%d) (%H:%M:%S)'),
                        message=message + '\n\n')
                    )

        elif status == 'ok' and type_run == 'user':
            self.tray_icon.showMessage(
                'В курсе новых серий',
                'Обновление базы завершено, новых серий не выходило')
        elif status == 'error':
            self.tray_icon.showMessage('В курсе новых серий',
                                       'При обновлении базы возникла ошибка')

        self.tray_icon.a_update.setDisabled(False)
        # self.tray_icon.a_load_from_bd.setDisabled(False)

    def load_serials_from_db(self):
        """
        Запускает синхронизацию виджета с БД
        """
        self.tray_icon.a_update.setDisabled(True)
        # self.tray_icon.a_load_from_bd.setDisabled(True)
        self.s_send_db_task.emit(self.db_worker.get_serials)

    def update_list_serial(self, all_serials):
        """
        Обновляет в виджете список сериалов
        """
        self.serial_tree.model.clear()
        self.serial_tree.model.setHorizontalHeaderLabels(['Сериалы'])
        self.serial_tree.add_items(all_serials)
        self.serial_tree.view.sortByColumn(0, QtCore.Qt.AscendingOrder)

        self.tray_icon.a_update.setDisabled(False)
        # self.tray_icon.a_load_from_bd.setDisabled(False)