import glob
import enum
import logging
from os.path import join, dirname, basename, isfile

import dependency_injector.containers as cnt
import dependency_injector.providers as prv

from config_readers import ConfigsProgram

logger = logging.getLogger('serial-notifier')


class DIServices(cnt.DeclarativeContainer):
    app = prv.Provider()
    main_window = prv.Provider()
    tray_icon = prv.Provider()
    board_notices = prv.Provider()

    conf_program = prv.Provider()


class UpdateCounterAction(enum.Enum):
    ADD = 'add'
    CLEAR = 'clear'


class NoticePluginMount(type):
    required_attr = ['name', 'description']

    def __init__(cls, name, bases, attrs):
        if not hasattr(cls, 'plugins'):
            cls.plugins = {}
        else:
            check = NoticePluginMount.check_requirements(cls)
            if check:
                NoticePluginMount.registration_plugin(cls)

    def check_requirements(cls):
        missing = []
        for attr in NoticePluginMount.required_attr:
            if not hasattr(cls, attr):
                missing.append(attr)

        if missing:
            logger.error(
                f'Невозможно зарегистировать плагин {cls.__name__}, '
                f'отсутствует атрибут(ы): {", ".join(missing)}'
            )

        return not bool(missing)

    def registration_plugin(cls):
        config_program = DIServices.conf_program()
        if not config_program.get(cls.name, None):
            default_setting = {}
            default_setting.update(BaseNoticePlugin.default_setting)
            default_setting.update(cls.default_setting)
            config_program.write({cls.name: default_setting})

        if config_program[cls.name]['enable'] == 'yes':
            cls.plugins[cls.name] = cls()


class NoticePluginsContainer(metaclass=NoticePluginMount):
    count = 0

    @classmethod
    def send_notice_everyone(cls, data, warning,
                             counter_action: UpdateCounterAction = None):
        """
        Отправляет уведомления во все зарегистрированные плагины
        :param data: данные, которые будут выведены в уведомлении
        :param warning: содержит предупреждение, если при доступе к каким-то
        источникам обновлений возникли проблемы
        :param counter_action: действие совершаемое со счетчиком
        :return:
        """
        for name, plugin in cls.plugins.items():
            plugin.send_notice(data, warning, counter_action)

    @classmethod
    def update_all_counters(cls, counter_action=UpdateCounterAction.ADD):
        for name, plugin in cls.plugins.items():
            try:
                plugin.update_counter(counter_action)
            except NotImplementedError:
                pass

    @classmethod
    def load_notice_plugins(cls):
        plugin_modules = [
            f'{__name__}.{basename(f)[:-3]}' for f in
            glob.glob(join(dirname(__file__), "*.py"))
            if isfile(f) and not f.endswith('__init__.py')
        ]

        for i in plugin_modules:
            __import__(i, locals(), globals())


class BaseNoticePlugin:
    default_setting = {
        'enable': 'yes'
    }

    def __init__(self):
        self.conf_program: ConfigsProgram = DIServices.conf_program()

    def send_notice(self, data, warning, counter_action: UpdateCounterAction=None):
        """
        :param data: данные, которые нужно отобразить в уведомлении
        :param warning: содержит предупреждение, если при доступе к каким-то
        источникам обновлений возникли проблемы
        :param counter_action: указывает, что нужно сделать: обновить счетчик
        или убрать счетчик. Может иметь значения add или clear.
        """
        raise NotImplementedError

    def update_counter(self, counter_action=UpdateCounterAction.ADD):
        """
        Обновляет счетчик обновлений, который показывает сколько новых
        уведомлений есть
        :param counter_action: указывает, что нужно сделать: обновить счетчик
        или убрать счетчик.
        """
        raise NotImplementedError

    def build_notice(self, data) -> str:
        """
        Собирает из присланных данных строку с уведомлением, которое будет
        показываться пользователю
        :param data: данные из которых собирается строка
        :return: итоговая строка показываемая пользователю
        """
        result_message = ''
        for site_name, serials in data.items():
            result_message += '{}\n'.format(site_name)
            for serial_name, i in serials.items():
                url, i = i
                result_message += '{}: Сезон {}, Серия {}\n'.format(
                    serial_name, i['Сезон'], ', '.join(map(str, i['Серия']))
                )
            result_message += '\n'
        return result_message.strip()
