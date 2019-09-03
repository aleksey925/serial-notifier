import re
import codecs
import logging
import configparser
from os.path import join, exists
from urllib.parse import urlsplit

from enums import SupportedSites


class BaseConfigReader:
    """
    Базовый класс для всех парсеров конфигурационных файлов
    """
    def __init__(self, base_dir, conf_name):
        self._logger = logging.getLogger('serial-notifier')
        self._cfg_parser = configparser.ConfigParser()

        self._data = {}

        self._base_dir = base_dir
        self._conf_name = conf_name
        self._path = join(base_dir, conf_name)
        self._default_settings = {}

    def init(self):
        """
        Проверяет наличие конфига и если его нет, создает конфиг с
        настройками по умолчанию
        """
        if not exists(self._path):
            self.write(self._default_settings)

    def read(self):
        self._data.clear()

        try:
            self._cfg_parser.read(self._path, encoding='utf8')
        except Exception:
            self._logger.critical(
                f'Ошибка при парсинге конфигурационного файла '
                f'"{self._conf_name}"', exc_info=True
            )
            return 'error'
        else:
            for section_name in self._cfg_parser.sections():
                self._data[section_name] = {}
                for option in self._cfg_parser[section_name].items():
                    self._data[section_name][option[0]] = option[1]

    def write(self, setting: dict=None):
        if setting:
            self._cfg_parser.update(setting)
            self._data.update(setting)

        with open(self._path, 'w') as out:
            self._cfg_parser.write(out)

    def get_config_data(self):
        return self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __str__(self):
        return str(self._data)

    def __repr__(self):
        return repr(self._data)


class SerialsUrls(BaseConfigReader):
    def __init__(self, base_dir, conf_name='sites.conf'):
        super().__init__(base_dir, conf_name)

        self.url_sep = ';'
        self._default_settings = {
            SupportedSites.FILIN.value: {'urls': '', 'encoding': 'cp1251'},
            SupportedSites.FILMIX.value: {'urls': '', 'encoding': ''},
            SupportedSites.SEASONVAR.value: {'urls': '', 'encoding': ''},
        }
        self.init()
        self.read()

    def read(self):
        error = super().read()
        if error:
            return

        data = {}
        for section, options in self._data.items():
            data[section] = {}
            data[section]['urls'] = {}
            for value in options['urls'].split('\n'):
                if value != '':
                    tv_serial_name, tv_serial_url = value.split(self.url_sep)
                    data[section]['urls'][tv_serial_name] = tv_serial_url
            data[section]['encoding'] = options.get('encoding', '')

        self._data = data

    def tv_serial_with_same_name_exists(self, tv_serial_name) -> bool:
        for section_options in self._data.values():
            if tv_serial_name in section_options.get('urls', {}):
                return True
        return False

    def add(self, tv_serial_name, tv_serial_url):
        """
        Добавляет новый сериал в список отслеживаемых
        :param tv_serial_name: название сериала
        :param tv_serial_url: url сериала
        """
        parsed_url = urlsplit(tv_serial_url)
        try:
            base_url = parsed_url.netloc.split('.')[0]
            site = SupportedSites(base_url)
        except ValueError:
            msg = 'Введеный сайт не поддерживается приложением'
            self._logger.error(msg + f' ({tv_serial_url})')
            raise ValueError(msg)

        urls = self._cfg_parser[site.value]['urls']

        if self.tv_serial_with_same_name_exists(tv_serial_name):
            raise ValueError('Сериал с таким именем уже существует')

        if parsed_url.path in urls:
            raise ValueError(
                'Данный сериал уже отслеживается, но под другим именем'
            )

        sep = '' if len(urls) == 0 else '\n'
        self._cfg_parser[site.value]['urls'] += (
            f'{sep}{tv_serial_name}{self.url_sep}{tv_serial_url}'
        )

        self.write()
        self.read()

    def rename(self, old_name, new_name):
        if self.tv_serial_with_same_name_exists(new_name):
            raise ValueError('Сериал с таким именем уже существует')

        for section_name, section in self._cfg_parser.items():
            urls = section.get('urls', None)
            if urls is not None:
                section['urls'] = re.sub(
                    f'(^|\s*)({old_name})({self.url_sep})',
                    rf'\g<1>{new_name}\g<3>',
                    urls,
                    flags=re.UNICODE | re.MULTILINE
                )

        self.write()
        self.read()

    def remove(self, serial_name):
        """
        Удаляет сериал из списка отслеживаемых
        :param serial_name: название сериала
        """
        for section_name, section in self._cfg_parser.items():
            for option, value in section.items():
                self._cfg_parser[section_name][option] = re.sub(
                    f'{serial_name}{self.url_sep}.*\n?', '', value
                )
        self.write()
        self.read()


class ConfigsProgram(BaseConfigReader):
    def __init__(self, base_dir, conf_name='setting.conf'):
        super().__init__(base_dir, conf_name)

        self._strtobool = {'true': True, 'false': False, '1': True, '0': False}

        self._default_settings = {
            'general': {
                'refresh_interval': '10',
            },
            'downloader': {
                'use_proxy': True,
                'pac_file': 'https://antizapret.prostovpn.org/proxy.pac',
                'target_downloader': 'async_downloader',
                'check_internet_access_url': 'http://ya.ru'
            },
            'async_downloader': {
                'timeout': '2',
                'concurrent_requests_count': '100'
            },
            'thread_downloader': {
                'timeout': '2',
                'thread_count': '10'
            },
            'gopac': {
                'console_encoding': ''
            }
        }
        self.converter = {
            'general': {
                # конвертируем минуты в миллисекунды
                'refresh_interval': lambda i: float(i) * 60000,
            },
            'downloader': {
                'use_proxy': self._str_to_bool
            },
            'async_downloader': {
                # конвертируем минуты в секунды
                'timeout': lambda i: float(i) * 60,
                'concurrent_requests_count': lambda i: int(i)
            },
            'thread_downloader': {
                # конвертируем минуты в миллисекунды
                'timeout': lambda i: float(i) * 60000,
                'thread_count': lambda i: int(i)
            },
            'gopac': {
                'console_encoding': self._lookup_encoding
            }
        }
        self.init()
        self.read()

    @staticmethod
    def _lookup_encoding(i):
        if i == '':
            return i

        try:
            codecs.lookup(i)
        except LookupError:
            raise

        return i

    def _str_to_bool(self, i):
        value = self._strtobool.get(i.lower(), None)
        if value is None:
            raise ValueError('Ошибка при преобразовании str в bool')
        return value

    def read(self):
        error = super().read()
        if error:
            return

        for section, options in self.converter.items():
            for option, func in options.items():
                option_value = self._data[section][option]
                try:
                    self._data[section][option] = func(option_value)
                except Exception:
                    self._logger.error(
                        f'Возникла ошибка при попытке конвертировать параметр '
                        f'"{option} = {option_value}" из секции "{section}".'
                        f'Будет применено значение по умолчанию.',
                        exc_info=True
                    )
                    self._data[section][option] = (
                        self._default_settings[section][option]
                    )


if __name__ == '__main__':
    from configs import base_dir

    cp = ConfigsProgram(base_dir)
    print(cp)

    su = SerialsUrls(base_dir)
    print(su)
