#!/usr/bin/env python3
import sys
import asyncio
from os.path import join

import dependency_injector.containers as cnt
import dependency_injector.providers as prv
from quamash import QEventLoop
from PyQt5 import QtWidgets, QtGui

import configs
import notice_plugins
import schedulers
from db.utils import apply_migrations
from downloaders import base_downloader
from db.managers import DbManager
from gui import mainwindow, widgets, windows
from gui.widgets import SearchLineEdit, BoardNotices
from gui.mainwindow import MainWindow, SerialTree, SystemTrayIcon
from configs import base_dir, resources_dir, log_path
from config_readers import ConfigsProgram, SerialsUrls
from loggers import init_logger


class DIServices(cnt.DeclarativeContainer):
    app = prv.Object(QtWidgets.QApplication(sys.argv))
    main_window = prv.Singleton(MainWindow)
    tray_icon = prv.Singleton(SystemTrayIcon, parent=main_window())
    serial_tree = prv.Singleton(SerialTree, parent=main_window())
    search_field = prv.Singleton(SearchLineEdit, parent=main_window())
    board_notices = prv.Singleton(BoardNotices, search_field)
    add_new_tv_series_windows = prv.Singleton(
        windows.AddNewTvSeriesWindows, parent=main_window()
    )
    rename_tv_series_windows = prv.Singleton(
        windows.RenameTvSeriesWindows, parent=main_window(),
        serial_tree=serial_tree()
    )

    db_manager = prv.Singleton(DbManager, main_window().s_send_db_task)

    conf_program = prv.Singleton(ConfigsProgram, base_dir=resources_dir)
    serials_urls = prv.Singleton(SerialsUrls, base_dir=resources_dir)


# Внедрение зависимостей
mainwindow.DIServices.override(DIServices)
widgets.DIServices.override(DIServices)
windows.DIServices.override(DIServices)
schedulers.DIServices.override(DIServices)
notice_plugins.DIServices.override(DIServices)
base_downloader.DIServices.override(DIServices)

app: QtWidgets.QApplication = DIServices.app()
app.icon = QtGui.QIcon(join(base_dir, 'icons/app-icon-512x512.png'))
app.setWindowIcon(app.icon)
loop = QEventLoop(app)
asyncio.set_event_loop(loop)

init_logger(log_path)
notice_plugins.NoticePluginsContainer.load_notice_plugins()

apply_migrations(configs.base_dir)

window = DIServices.main_window()
window.init()
window.show()

# Делаем окно активным
window.raise_()
window.activateWindow()

with loop:
    loop.run_forever()
