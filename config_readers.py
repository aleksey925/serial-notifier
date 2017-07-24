import re
import logging
import traceback
import configparser

from abc import ABC, abstractmethod
from os.path import join, exists


class ConfigReader(ABC):
    """
    Базовый класс для всех парсеров
    """
    def __init__(self, base_dir, conf_name):
        self._logger = logging.getLogger('main')
        self._config = configparser.ConfigParser()

        self.data = {}

        self.base_dir = base_dir
        self.conf_name = conf_name
        self.path = join(base_dir, conf_name)
        self.default_settings = ''

    def init(self):
        """
        Проверяет наличие конфига и если его нет, создает конфиг с
        настройками по умолчанию
        """
        if not exists(self.path):
            with open(self.path, 'w') as out:
                out.write(self.default_settings)

    @abstractmethod
    def read(self):
        self.data.clear()

        try:
            self._config.read(self.path, encoding='utf8')
        except Exception:
            self._logger.critical((
                f'Ошибка при парсинге {self.conf_name}\n'
                f'{traceback.format_exc()}'
            ))

    def write(self):
        with open(self.path, 'w') as out:
            self._config.write(out)


class SerialsUrls(ConfigReader):
    def __init__(self, base_dir, conf_name='sites.conf'):
        super().__init__(base_dir, conf_name)

        self.default_settings = (
            '# Файл заглушка, замените все реальными данными\n'
            '[filin.tv]\nurls = <Название сериала>;<url>\n\n'
            '[filmix.me]\nurls = <Название сериала>;<url>\n'
        )
        self.init()
        self.read()

    def read(self):
        super().read()
        for section in self._config.sections():
            self.data[section] = []
            for i in self._config[section]['urls'].split('\n'):
                self.data[section].append(i.split(';'))

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


class ConfigsProgram(ConfigReader):
    def __init__(self, base_dir, conf_name='setting.conf'):
        super().__init__(base_dir, conf_name)

        self.default_settings = (
            '[general]\n'
            'file_notif ='
            'timeout_refresh = 10'
            'timeout_update = 100'
        )
        self.init()
        self.read()

    def read(self):
        super().read()

        for option in self._config['general']:
            if option == 'timeout_refresh':
                # Таймер в программе принимает в миллисекундах значение, по
                # этому переводим минуты в милисекунды
                self.data[option] = self._config.getint('general', option) * 60000
            elif option == 'timeout_update':
                self.data[option] = self._config.getint('general', option)
            else:
                self.data[option] = self._config.get('general', option)

if __name__ == '__main__':
    from configs import base_dir

    s = SerialsUrls(base_dir, 'sites.conf')
    print(s.data)
