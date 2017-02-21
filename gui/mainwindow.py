import re
import sys
import time
from os.path import join, exists, split

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QCoreApplication, QModelIndex

from gui.widgets import SearchLineEdit, SortFilterProxyModel, BoardNotification
from workers import UpgradeTimer
from db.managers import DbManager
from configparsers import SerialsUrls, ConfigsProgram
from configs import base_dir


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, parent=None):
        super(SystemTrayIcon, self).__init__(parent)
        self.main_window = parent

        self.setToolTip('В курсе новых серий')
        self.activated.connect(self.click_trap)

        self.icons = {
            'normal': QtGui.QIcon(join(base_dir, 'icons/app-48x48.png')),
            'update': QtGui.QIcon(join(base_dir, 'icons/app-sync-48x48.png'))
        }
        self.setIcon(self.icons['normal'])

        # Элементы меню
        self.a_open = None
        self.a_update = None
        self.a_exit = None

        self.build_menu()

        self.show()

    def build_menu(self):
        menu = QtWidgets.QMenu(self.parent())

        self.a_open = menu.addAction('Открыть', self.show_window)
        self.a_update = menu.addAction('Обновить')
        self.a_update.setDisabled(True)
        self.a_exit = menu.addAction('Выйти', QCoreApplication.instance().exit)

        self.setContextMenu(menu)

    def change_icon(self, state):
        self.setIcon(self.icons[state])
        if state == 'normal':
            self.setToolTip('В курсе новых серий')
        else:
            self.setToolTip('Ищем новые серии...')

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

    def show_window(self):
        self.parent().show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def update_start(self):
        self.change_icon('update')
        self.a_update.setDisabled(True)

    def update_done(self):
        self.change_icon('normal')
        self.a_update.setDisabled(False)


class SerialTree(QtWidgets.QWidget):
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
        self.view = QtWidgets.QTreeView()
        self.model = QtGui.QStandardItemModel()
        self.filter_by_name = SortFilterProxyModel()
        self.context_menu = QtWidgets.QMenu()

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

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(self.view)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

    def hide_items(self, selected_element):
        """
        Позволяет скрыть просмотренные/не просмотренные сериалы
        :param selected_element: индекс выбранного в qcombobox варианта
            0 - показать все сериалы
            1 - показать досмотренные сериалы
            2 - показать сериалы с новыми сериями
        """
        def get_icon(row, column):
            index = self.view.model().index(row, column)
            index = self.view.model().mapToSource(index)
            item = self.model.itemFromIndex(index)
            return item.icon().cacheKey() if item else 0

        count = self.model.rowCount()
        parent_index = self.model.invisibleRootItem().index()
        icons = [
            self.looked_status['True'].cacheKey(),
            self.looked_status['False'].cacheKey()
        ]

        for i in range(count):
            self.view.setRowHidden(i, parent_index, False)

        if selected_element == 1:
            for i in range(count):
                if get_icon(i, 0) != icons[0]:
                    self.view.setRowHidden(i, parent_index, True)
        elif selected_element == 2:
            for i in range(count):
                if get_icon(i, 0) != icons[1]:
                    self.view.setRowHidden(i, parent_index, True)

    def create_context_menu(self):
        self.context_menu.addAction('Смотрел',
                                    lambda: self.change_status('True'))
        self.context_menu.addAction('Не смотрел',
                                    lambda: self.change_status('False'))

    def change_status(self, status):
        """
        Меняет статус выбранного элемента (смотрел/не смотрел)
        """
        serial_index = self._get_root_element(self._selected_element[1])
        updated_inf = {'name': serial_index.data(), 'season': '', 'series': ''}

        if self._selected_element[0] == 0:
            # Меняем статусы у всех сезонов и серий сериала
            self._change_serial_status(serial_index, status)
        elif self._selected_element[0] == 1:
            # Меняем статус сезона
            season_index = self._selected_element[1]
            self.model.itemFromIndex(season_index).setIcon(self.looked_status[status])

            # Меняем статусы у всех серий сезона
            for i in self._iter_qstandarditem(season_index):
                self.model.itemFromIndex(i).setIcon(self.looked_status[status])

            self._change_season_status(season_index)

            updated_inf['season'] = season_index.data().split('Сезон ')[1]
        else:
            # Меняю статус серии
            season_index = self._selected_element[1].parent()
            series_index = self._selected_element[1]
            self.model.itemFromIndex(series_index).setIcon(self.looked_status[status])

            # Проверяю, что остальные серии имеют тот же статус
            series = {self.model.itemFromIndex(i).icon().cacheKey() for i in
                      self._iter_qstandarditem(season_index)}

            # Ставлю статус сезону в зависимости от статуса их серий
            if len(series) == 1 and series.pop() == self.looked_status['True'].cacheKey():
                self.model.itemFromIndex(season_index).setIcon(
                    self.looked_status['True']
                )
            else:
                self.model.itemFromIndex(season_index).setIcon(
                    self.looked_status['False']
                )

            self._change_season_status(season_index)

            updated_inf['season'] = season_index.data().split('Сезон ')[1]
            updated_inf['series'] = series_index.data().split('Серия ')[1]

        self.main_window.s_send_db_task.emit(
            lambda: self.main_window.db_worker.change_status(
                updated_inf, status, self._selected_element[0]
            )
        )

    def _change_serial_status(self, element: QModelIndex, status):
        """
        Принимает ссылку на сериал и рекурсивно меняет статус всех его серий
        """
        self.model.itemFromIndex(element).setIcon(self.looked_status[status])
        for i in self._iter_qstandarditem(element):
            self.model.itemFromIndex(i).setIcon(self.looked_status[status])
            if self.element_has_children(i):
                self._change_serial_status(i, status)

    def _change_season_status(self, index: QModelIndex):
        """
        Проверяет статус (смотрел/не смотрел) сезонов и выставляет в
        зависимости от этого нужный статус всему сериалу
        """
        index = index.parent()
        seasons = {self.model.itemFromIndex(i).icon().cacheKey() for i in
                   self._iter_qstandarditem(index)}

        if len(seasons) == 1 and seasons.pop() == self.looked_status['True'].cacheKey():
            self.model.itemFromIndex(index).setIcon(self.looked_status['True'])
        else:
            self.model.itemFromIndex(index).setIcon(self.looked_status['False'])

    @staticmethod
    def _iter_qstandarditem(element: QModelIndex):
        """
        Пробегает по всем дочерним элементам элементам (без рекурсии)
        """
        index = 0
        while True:
            # Возвращает дочерний элемент, если дочернего элемента с таким
            # индексом нет метод isValid вернет False
            next_element = element.child(index, 0)
            index += 1
            if next_element.isValid():
                yield next_element
            else:
                raise StopIteration

    @staticmethod
    def element_has_children(elem: QModelIndex):
        return True if elem.child(0, 0).isValid() else False

    @staticmethod
    def _get_root_element(element: QModelIndex) -> QModelIndex:
        root = element

        while True:
            temp = root.parent()
            if temp.isValid():
                root = root.parent()
            else:
                break

        return root

    def _open_menu(self, position):
        """
        Создает контекстное меню по щелчку
        """
        indexes = self.view.selectedIndexes()
        level = -1

        if len(indexes) > 0:
            level = 0
            index = indexes[0]
            while index.parent().isValid():
                index = index.parent()
                level += 1

        # Так как используется прокси модель, то сначала нужно извлечь индекс
        # ссылающийся на исходную модель
        proxy_index = self.view.model().mapToSource(indexes[0])
        self._selected_element = (level, proxy_index)
        self.context_menu.exec_(self.view.viewport().mapToGlobal(position))

    def add_items(self, elements: list):
        for i in elements:
            self.add_item(i)

    def add_item(self, element: dict):
        """
        Осуществляет загрузку сериала в виджет
        :argument element: dict Сериал со всеми даными, которые потребуется
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


class MainWindow(QtWidgets.QMainWindow):

    # Служит для отправки заданий в DbManager
    s_send_db_task = QtCore.pyqtSignal(object, name='send_task')

    def __init__(self):
        super(MainWindow, self).__init__()
        self.installEventFilter(self)

        # Инициализация основных виджетов окна
        self.main_layout = QtWidgets.QGridLayout()
        main_widget = QtWidgets.QWidget()
        main_widget.setLayout(self.main_layout)
        self.setCentralWidget(main_widget)

        # Виджеты
        self.tray_icon = SystemTrayIcon(parent=self)
        self.search_field = SearchLineEdit(self)
        self.lab_search_field = QtWidgets.QLabel('Поиск: ')
        self.serial_tree = SerialTree(parent=self)
        self.notice = BoardNotification(self.search_field)
        self.filter_by_status = QtWidgets.QComboBox()

        self.urls = SerialsUrls(base_dir)
        self.conf_program = ConfigsProgram(base_dir)

        # Различные асинхронные обработчики
        self.db_worker = DbManager(self.s_send_db_task)
        self.db_worker.s_serials_extracted.connect(self.update_list_serial,
                                                   QtCore.Qt.QueuedConnection)

        self.upgrade_timer = UpgradeTimer(self.tray_icon, self.db_worker,
                                          self.urls, self.conf_program)
        self.upgrade_timer.s_upgrade_complete.connect(self.upgrade_complete)

        self.init_widgets()

        self.set_position()

    def init_widgets(self):
        self.tray_icon.a_update.triggered.connect(self.run_upgrade)

        # Загружаем информацию о серилах в в БД
        self.s_send_db_task.emit(self.db_worker.get_serials)

        self.main_layout.addWidget(self.lab_search_field, 0, 0)

        self.search_field.textChanged.connect(self.change_filter_str)
        self.main_layout.addWidget(self.search_field, 0, 1)

        self.filter_by_status.addItems(
            ['Все', 'Смотрел', 'Не смотрел'])
        self.filter_by_status.setItemIcon(
            0, QtGui.QIcon(join(base_dir, 'icons/tick-black.png')))
        self.filter_by_status.setItemIcon(
            1, self.serial_tree.looked_status['True'])
        self.filter_by_status.setItemIcon(
            2, self.serial_tree.looked_status['False'])
        self.filter_by_status.currentIndexChanged.connect(
            self.serial_tree.hide_items)
        self.main_layout.addWidget(self.filter_by_status, 1, 0, 1, 2)

        self.serial_tree.setMinimumSize(270, 100)
        self.main_layout.addWidget(self.serial_tree, 2, 0, 1, 2)

        self.main_layout.addWidget(self.notice, 0, 2, 3, 2)

    def eventFilter(self, obj, event):
        """
        Устанавливает и снимает захват клавиатуры
        """
        if event.type() == QtCore.QEvent.WindowActivate:
            self.search_field.grabKeyboard()
        elif event.type() == QtCore.QEvent.WindowDeactivate:
            self.search_field.releaseKeyboard()

        return False

    def set_position(self, width=430, height=500):
        self.setGeometry(0, 0, width, height)
        screen = QtWidgets.QDesktopWidget().availableGeometry()
        self.move(screen.width() - width, 0)

    def fix_filter_conflict(self):
        """
        Нужен, чтоб сбросить состояние комбобокса к настойкам по умолчанию,
        так как при поиске конкретного сериала прокси модель отобразит скрытые
        элементы и комбобокс будет показывать неправильную информацию
        """
        self.filter_by_status.currentIndexChanged.disconnect(
            self.serial_tree.hide_items
        )
        self.filter_by_status.setCurrentIndex(0)
        self.filter_by_status.currentIndexChanged.connect(
            self.serial_tree.hide_items
        )

    def change_filter_str(self, new_str):
        self.fix_filter_conflict()

        filter_string = QtCore.QRegExp(
            new_str, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.RegExp
        )
        self.serial_tree.filter_by_name.setFilterRegExp(filter_string)

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def run_upgrade(self):
        """
        Запускает процесс получения и парсинга новых данных с сайтов
        """
        self.tray_icon.update_start()
        self.upgrade_timer.run('user')

    def upgrade_complete(self, status, serials_with_updates, type_run):
        """
        Вызывается после завершения обновления БД, чтобы включить отключеные
        кнопки меню и уведомить пользователя о новых сериях если таковые
        появились
        """
        if serials_with_updates and status == 'ok':
            self.s_send_db_task.emit(self.db_worker.get_serials)
            message = self.prepare_message(serials_with_updates)
            self.tray_icon.showMessage('В курсе новых серий', message)
            self.notice.add_notification(serials_with_updates)

            if exists(split(self.conf_program.conf['file_notif'])[0]):
                with open(self.conf_program.conf['file_notif'], 'a') as out:
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

        self.tray_icon.update_done()

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

    def update_list_serial(self, all_serials):
        """
        Обновляет в виджете список сериалов
        """
        self.serial_tree.model.clear()
        self.serial_tree.model.setHorizontalHeaderLabels(['Сериалы'])
        self.serial_tree.add_items(all_serials)
        self.serial_tree.view.sortByColumn(0, QtCore.Qt.AscendingOrder)

        self.tray_icon.update_done()
