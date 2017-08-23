#!/usr/bin/env python3
import sys
import asyncio
from os.path import join

import dependency_injector.containers as cnt
import dependency_injector.providers as prv
from quamash import QEventLoop
from PyQt5 import QtWidgets, QtGui

import notice_plugins
import schedulers
from db.managers import DbManager
from gui import mainwindow
from gui.widgets import SearchLineEdit, BoardNotices
from gui.mainwindow import MainWindow, SerialTree, SystemTrayIcon
from configs import base_dir, log_path
from config_readers import ConfigsProgram, SerialsUrls
from loggers import create_logger


class DIServises(cnt.DeclarativeContainer):
    app = prv.Object(QtWidgets.QApplication(sys.argv))
    main_window = prv.Singleton(MainWindow)
    tray_icon = prv.Singleton(SystemTrayIcon, parent=main_window())
    serial_tree = prv.Singleton(SerialTree, parent=main_window())
    search_field = prv.Singleton(SearchLineEdit, parent=main_window())
    board_notices = prv.Singleton(BoardNotices, search_field)

    db_manager = prv.Singleton(DbManager, main_window().s_send_db_task)

    conf_program = prv.Singleton(ConfigsProgram, base_dir=base_dir)
    serials_urls = prv.Singleton(SerialsUrls, base_dir=base_dir)


# Внедрение зависимостей
mainwindow.DIServises.override(DIServises)
schedulers.DIServises.override(DIServises)
notice_plugins.DIServises.override(DIServises)

app: QtWidgets.QApplication = DIServises.app()
app.icon = QtGui.QIcon(join(base_dir, 'icons/app-512x512.png'))
app.setWindowIcon(app.icon)
loop = QEventLoop(app)
asyncio.set_event_loop(loop)

create_logger(log_path)
notice_plugins.NoticePluginsContainer.load_notice_plugins()

window = DIServises.main_window()
window.init()
window.show()

# Делаем окно активным
window.raise_()
window.activateWindow()

with loop:
    loop.run_forever()
