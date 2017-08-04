"""
Дополнительные виджеты для gui
"""
import re

from os.path import join

from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtWidgets import QStyle
from PyQt5.QtCore import QModelIndex

from configs import base_dir


class SearchLineEdit(QtWidgets.QLineEdit):
    """
    QLineEdit с кнопкой для очистки поля
    """
    def __init__(self, parent=None):
        super(SearchLineEdit, self).__init__(parent)

        self.button = QtWidgets.QToolButton(self)
        self.button.setIcon(QtGui.QIcon(join(base_dir, 'icons/clear.png')))
        self.button.setStyleSheet('border: 0px; padding: 0px;')
        self.button.setCursor(QtCore.Qt.PointingHandCursor)
        self.button.clicked.connect(self.clear)

        frame_width = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        button_size = self.button.sizeHint()

        self.setStyleSheet(
            'QLineEdit {{padding-right: {}px; }}'.format(
                button_size.width() + frame_width + 1)
        )
        self.setMinimumSize(
            max(self.minimumSizeHint().width(),
                button_size.width() + frame_width * 2 + 2),
            max(self.minimumSizeHint().height(),
                button_size.height() + frame_width * 2 + 2)
        )

    def resizeEvent(self, event):
        button_size = self.button.sizeHint()
        frame_width = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        self.button.move(
            self.rect().right() - frame_width - button_size.width(),
            (self.rect().bottom() - button_size.height() + 1) / 2
        )
        super(SearchLineEdit, self).resizeEvent(event)


class Notification(QtWidgets.QLabel):
    """
    Уведомление, которое отображается на доске уведомлений. Содержит текст
    уведомления и крестик для его удаления
    """
    icon_close = lambda self: QtGui.QIcon(join(base_dir, 'icons/cross.png'))

    def __init__(self, massage, *args, **kwargs):
        super(Notification, self).__init__(*args, **kwargs)

        if callable(self.icon_close):
            self.icon_close = self.icon_close()

        self.setText('<br>{}<br>'.format(massage))

        self.button = QtWidgets.QToolButton(self)
        self.button.setIcon(self.icon_close)
        self.button.setStyleSheet('border: 0px; padding: 0px;')
        self.button.setCursor(QtCore.Qt.PointingHandCursor)

        frame_width = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        button_size = self.button.sizeHint()

        self.setStyleSheet("""padding-right: {0}px;
                            padding-left: 2px;
                            color: #fff;
                            background-color: #45494d;
                            border-width: 2px;
                            border-radius: 5px;
                            border-color: gray;
                            """.format(button_size.width() + frame_width + 1))

        self.setMinimumSize(
            max(self.minimumSizeHint().width(),
                button_size.width() + frame_width * 2 + 2),
            max(self.minimumSizeHint().height(),
                button_size.height() + frame_width * 2 + 2)
        )

    def resizeEvent(self, event):
        width = self.rect().right()
        height = self.rect().height()

        button_size = self.button.sizeHint()
        frame_width = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        self.button.move(width - frame_width - button_size.width(),
                         height * 5 // 100)
        super(Notification, self).resizeEvent(event)


class BoardNotices(QtWidgets.QWidget):
    """
    Доска на которой отображаются уведомления о выходе новых серий
    """
    def __init__(self, search_field):
        super(BoardNotices, self).__init__()
        self.search_field = search_field

        self.all_notification = []

        self.scroll_layout = QtWidgets.QVBoxLayout()

        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_widget.setLayout(self.scroll_layout)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.scroll_widget)

        self.main_layout = QtWidgets.QVBoxLayout()
        margins = self.main_layout.contentsMargins()
        margins.setTop(0)
        margins.setBottom(0)
        self.main_layout.setContentsMargins(margins)
        self.main_layout.addWidget(self.scroll_area)
        self.setLayout(self.main_layout)

        self.default_label = QtWidgets.QLabel(
            '{}Уведомлений нет{}'.format(' ' * 14, ' ' * 5)
        )
        self.scroll_layout.addWidget(self.default_label)
        self.scroll_layout.addStretch(0)
        self.all_notification.append(self.default_label)

        self._update_width_area()

    def add_notification(self, serials_with_updates):
        if len(self.all_notification) == 1:
            self.all_notification[0].hide()

        notification = Notification(self.prepare_message(serials_with_updates))
        notification.linkActivated.connect(self._link_activated)
        notification.button.clicked.connect(
            lambda i, widget=notification: self.remove_notification(widget)
        )
        self.scroll_layout.insertWidget(
            len(self.all_notification), notification
        )
        self.all_notification.append(notification)

        self._update_width_area()

    def _link_activated(self, link):
        self.search_field.setText(link)

    def prepare_message(self, data):
        result_message = ''
        msg_pattern = ('<a style="color: white" href="{0}">{0}</a>: '
                       'Сезон {1}, Серия {2}<br>')
        for site_name, serials in data.items():
            result_message += '{}<br>'.format(site_name)
            for serial_name, i in serials.items():
                result_message += msg_pattern.format(
                    serial_name, i['Сезон'], ', '.join(map(str, i['Серия']))
                )
            result_message += '<br>'
        return re.sub('(<br>)*$', '', result_message)

    def remove_notification(self, widget):
        widget.deleteLater()
        self.all_notification.remove(widget)

        if len(self.all_notification) == 1:
            self.all_notification[0].show()

        self._update_width_area()

    def _calculate_width(self, widget):
        """
        Вычисляет новое ширину виджета Notification, который размещается
        в QScrollArea
        """
        # todo вычисление требуемой ширины выполняется пока недостаточно точно
        widget_width = widget.sizeHint().width()
        sb_width = self.scroll_area.verticalScrollBar().sizeHint().width()
        margin_width = sum(self.scroll_layout.getContentsMargins())
        return widget_width + sb_width + margin_width + 5

    def _update_width_area(self):
        """
        Обновляет размер области уведомлений (подстраивает под
        размер сообщений)
        """
        new_width = [self._calculate_width(i) for i in self.all_notification]
        self.setMinimumWidth(max(new_width))


class SortFilterProxyModel(QtCore.QSortFilterProxyModel):
    """
    По умолчанию у найденного элемента не отображаются дочерние элементы
    в данной реализации это изменено
    """
    def __init__(self):
        super(SortFilterProxyModel, self).__init__()

    def filterAcceptsRow(self, row_num, source_parent):
        """
        Перегружаем родительскую функцию
        """
        # Проверяет, что текущая строка совпадает
        if self.filter_accepts_row_itself(row_num, source_parent):
            return True

        # Пройти весь путь до корня и проверить, что любой из них совпадает
        if self.filter_accepts_any_parent(source_parent):
            return True

        return False

    def filter_accepts_row_itself(self, row_num, parent):
        return super(SortFilterProxyModel, self).filterAcceptsRow(row_num, parent)

    def filter_accepts_any_parent(self, parent):
        """
        Проходит к корневому элементу и проверяет, что какой-то из предков
        соотстветвует фильтру
        """
        while parent.isValid():
            if self.filter_accepts_row_itself(parent.row(), parent.parent()):
                return True
            parent = parent.parent()
        return False

    def lessThan(self, left: QModelIndex, right: QModelIndex):
        """
        Заставляем числа сезоны и серии сортировать как числа, а не как строки
        для того, чтобы серии шли в правильном порядке
        """
        l_value = left.data()
        if 'Сезон' in l_value or 'Серия' in l_value:
            l_value = l_value.split()[-1]
            r_value = right.data().split()[-1]
            return int(l_value) < int(r_value)
        else:
            return super(SortFilterProxyModel, self).lessThan(left, right)