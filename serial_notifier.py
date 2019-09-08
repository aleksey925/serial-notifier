#!/usr/bin/env python3
import asyncio
import sys
from os.path import join

import dependency_injector.containers as cnt
import dependency_injector.providers as prv
from PyQt5 import QtWidgets, QtGui
from quamash import QEventLoop

import configs
import loggers
import notice_plugins
import schedulers
from config_readers import ConfigsProgram, SerialsUrls
from configs import base_dir, resources_dir, log_path
from db.managers import DbManager
from db.utils import apply_migrations
from downloaders import base_downloader
from gui import mainwindow, widgets, windows
from gui.mainwindow import MainWindow, SerialTree, SystemTrayIcon
from gui.widgets import SearchLineEdit, BoardNotices


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
    unhandled_exception_message_box = prv.Object(
        windows.UnhandledExceptionMessageBox()
    )

    upgrades_scheduler = prv.Singleton(schedulers.UpgradesScheduler)
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
loggers.DIServices.override(DIServices)

app: QtWidgets.QApplication = DIServices.app()
app.icon = QtGui.QIcon(join(base_dir, 'icons/app-icon-512x512.png'))
app.setWindowIcon(app.icon)
loop = QEventLoop(app)
loop.set_exception_handler(loggers.asyncio_unhandled_exception_hook)
asyncio.set_event_loop(loop)

loggers.init_logger(log_path)
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
