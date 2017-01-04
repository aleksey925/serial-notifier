#!/usr/bin/env python3
import sys
import asyncio

from os.path import join

from configs import base_dir, log_path
from gui.mainwindow import MainWindow
from loggers import create_logger

from quamash import QEventLoop
from PyQt5 import QtWidgets, QtGui


# todo добавить кнопку прерывания обновления
# todo изменить виджет для отображения списка сериалов
# todo при изменении статуса фильма не перезагружать весь виджет
app = QtWidgets.QApplication(sys.argv)
app.setWindowIcon(QtGui.QIcon(join(base_dir, 'icons/app-icon-512x512.png')))

loop = QEventLoop(app)
asyncio.set_event_loop(loop)

create_logger(log_path)

window = MainWindow()
window.setWindowTitle('В курсе новых серий')
window.show()
# Делаем окно активным
window.raise_()
window.activateWindow()

with loop:
    loop.run_forever()
