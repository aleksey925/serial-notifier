import sys
import time

from PyQt5 import QtWidgets, QtGui, QtCore

from gui.mainwindow import SystemTrayIcon, MainWindow
from . import NoticePluginsContainer, DIServises, BaseNoticePlugin, \
    UpdateCounterAction


class DesktopNotice(NoticePluginsContainer, BaseNoticePlugin):
    name = 'system_notice'
    description = ('Показывает стандартные системные уведомления и изменяет '
                   'состояния счетчика новых уведомлений на иконке приложения')

    def __init__(self):
        super().__init__()

        font_size = {
            'tray': {
                'darwin': 26,
                'other': 19
            },
            'task_bar': {
                'darwin': 120,
                'other': 100
            }
        }
        self.font_tray: QtGui.QFont = None
        self.font_task_bar: QtGui.QFont = None

        self.app: QtWidgets.QApplication = DIServises.app()
        self.main_window: MainWindow = DIServises.main_window()
        self.tray_icon: SystemTrayIcon = DIServises.tray_icon()

        self.clean_icon = self.tray_icon.icons['normal']

        for target, fonts in font_size.items():
            size = fonts.get(sys.platform, None)
            if not size:
                size = fonts['other']

            font = QtGui.QFont('Arial')
            font.setBold(True)
            font.setPointSizeF(size)
            setattr(self, f'font_{target}', font)

    def send_notice(self, data, warning,
                    counter_action: UpdateCounterAction = None):
        self.tray_icon.showMessage(
            'В курсе новых серий',  self.build_notice(data) + warning
        )

        if counter_action and not self.main_window.isActiveWindow():
            self.update_counter(counter_action)

    def update_counter(self, counter_action: UpdateCounterAction=UpdateCounterAction.ADD):
        if counter_action is UpdateCounterAction.CLEAR:
            self.count = 0
            self.app.setWindowIcon(self.app.icon)
            self.tray_icon.icons['normal'] = self.clean_icon
            self.tray_icon.setIcon(self.tray_icon.icons['normal'])
            return

        self.count += 1
        count = str(self.count)

        self.app.setWindowIcon(
            self._draw_counter(self.app.icon, self.font_task_bar, count, 170)
        )

        # Сохраняем картинку со счетчиком, чтобы после обновления
        # восстановить её
        self.tray_icon.icons['normal'] = self._draw_counter(
                self.tray_icon.icons['normal'], self.font_tray, count, 35
            )
        self.tray_icon.setIcon(self.tray_icon.icons['normal'])

    def _draw_counter(self, icon: QtGui.QIcon, font: QtGui.QFont, count: str,
                      radius: int):
        """
        Рисует на иконке приложения количество новых уведомлений
        :param icon: иконка на которой будет рисоваться счетчик
        :param font: шрифт используемый для рисования счетчика
        :param count: количество новых уведомлений
        :param radius: радиус кружка в котором будет размещатьс счечик
        :return новая иконка
        """
        icon_size = icon.availableSizes()[0]
        pixmap = icon.pixmap(icon_size)

        painter_app_icon = QtGui.QPainter(pixmap)
        painter_app_icon.setRenderHint(QtGui.QPainter.Antialiasing)
        painter_app_icon.drawPixmap(
            pixmap.width() - (radius + 3), 1,
            self._draw_circle(font, count, radius)
        )

        painter_app_icon.end()

        return QtGui.QIcon(pixmap)

    def _draw_circle(self, font, text, radius):
        circle = QtGui.QPixmap(radius, radius)
        # Избавляет от шумов на изображении
        circle.fill(QtGui.QColor(0, 0, 0, 0))

        painter_circle = QtGui.QPainter(circle)
        painter_circle.setRenderHint(QtGui.QPainter.Antialiasing)
        painter_circle.setFont(font)
        painter_circle.setPen(QtCore.Qt.red)
        painter_circle.setBrush(QtCore.Qt.red)
        painter_circle.drawEllipse(0, 0, radius, radius)

        painter_circle.setPen(QtCore.Qt.white)
        text_option = QtGui.QTextOption()
        text_option.setAlignment(QtCore.Qt.AlignCenter)

        painter_circle.drawText(
            QtCore.QRectF(circle.rect()),
            text,
            text_option)
        painter_circle.end()

        return circle


class NoticeFile(NoticePluginsContainer, BaseNoticePlugin):
    name = 'notice_file'
    description = 'Записывает уведомления в указанный файл'
    default_setting = {
        'enable': 'no',
        'path': './serial_notifier.txt'
    }

    def __init__(self):
        super().__init__()

    def send_notice(self, data, warning,
                    counter_action: UpdateCounterAction = None):
        with open(self.conf_program.data['general']['path'], 'a') as out:
            out.write(
                f'{time.strftime("(%Y-%m-%d) (%H:%M:%S)")} '
                f'{self.build_notice(data)}\n\n\n'
            )


class BoardNotices(NoticePluginsContainer, BaseNoticePlugin):
    name = 'board_notices'
    description = ('Отображает уведомления о новых сериалах в специальном '
                   'виджете главного окна приложения')

    def __init__(self):
        super().__init__()

        self.board_notices = DIServises.board_notices()

    def send_notice(self, data, warning,
                    counter_action: UpdateCounterAction = None):
        self.board_notices.add_notification(data)
