import re
import logging
import traceback
import configparser
from abc import ABC, abstractmethod
from os.path import join, exists


class BaseConfigReader(ABC):
    """
    Базовый класс для всех парсеров конфигурационных файлов
    """
    def __init__(self, base_dir, conf_name):
        self._logger = logging.getLogger('main')
        self._config = configparser.ConfigParser()

        self.data = {}

        self.base_dir = base_dir
        self.conf_name = conf_name
        self.path = join(base_dir, conf_name)
        self.default_settings = {}

    def init(self):
        """
        Проверяет наличие конфига и если его нет, создает конфиг с
        настройками по умолчанию
        """
        if not exists(self.path):
            self.write(self.default_settings)

    def read(self):
        self.data.clear()

        try:
            self._config.read(self.path, encoding='utf8')
        except Exception:
            self._logger.critical((
                f'Ошибка при парсинге {self.conf_name}\n'
                f'{traceback.format_exc()}'
            ))
            return 'error'
        else:
            for section_name in self._config.sections():
                self.data[section_name] = {}
                for option in self._config[section_name].items():
                    self.data[section_name][option[0]] = option[1]

    def write(self, setting: dict=None):
        if setting:
            self._config.update(setting)
            self.data.update(setting)

        with open(self.path, 'w') as out:
            self._config.write(out)


class SerialsUrls(BaseConfigReader):
    def __init__(self, base_dir, conf_name='sites.conf'):
        super().__init__(base_dir, conf_name)

        self.default_settings = {
            'filin.tv': {'urls': '<Название сериала>;<url>'},
            'filmix.me': {'urls': '<Название сериала>;<url>'}
        }
        self.init()
        self.read()

    def read(self):
        error = super().read()
        if error:
            return

        data = {}
        for section, options in self.data.items():
            data[section] = []
            for value in options['urls'].split('\n'):
                if value != '':
                    data[section].append(value.split(';'))

        self.data = data

    def remove(self, serial_name):
        """
        Удаляет сериал из списка отслеживаемых
        :param serial_name: название сериала
        """
        for section_name, section in self._config.items():
            for option, value in section.items():
                self._config[section_name][option] = re.sub(
                    '{};.*\n?'.format(serial_name), '', value
                )
        self.write()
        self.read()


class ConfigsProgram(BaseConfigReader):
    def __init__(self, base_dir, conf_name='setting.conf'):
        super().__init__(base_dir, conf_name)

        self.default_settings = {
            'general': {
                'refresh_interval': '10',
                'timeout_update': '100',
                'thread_count': '10',
                'pac_file': 'https://antizapret.prostovpn.org/proxy.pac'
            }
        }
        self.converter = {
            'general': {
                'refresh_interval': lambda i: int(i) * 60000,
                'timeout_update': lambda i: int(i),
                'thread_count': lambda i: int(i)
            }
        }
        self.init()
        self.read()

    def read(self):
        error = super().read()
        if error:
            return

        for section, options in self.converter.items():
            for option, func in options.items():
                self.data[section][option] = func(self.data[section][option])


if __name__ == '__main__':
    from configs import base_dir

    #c = ConfigsProgram(base_dir)
    #print(c.data)

    c1 = SerialsUrls(base_dir)
    print(c1.data)