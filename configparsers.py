import configparser

from os.path import join


class SerialsUrls:
    def __init__(self, base_path):
        self.path = base_path

        self.config = configparser.ConfigParser()
        self.urls = {}

        self.read()

    def read(self):
        self.urls.clear()

        self.config.read(join(self.path, 'sites.conf'))

        for section in self.config.sections():
            self.urls[section] = []
            for i in self.config[section]['urls'].split('\n'):
                self.urls[section].append(i.split(';'))


class ConfigsProgram:
    def __init__(self, base_path):
        self.path = base_path

        self.config = configparser.ConfigParser()
        self.conf = {}

        self.read()

    def read(self):
        self.conf.clear()

        self.config.read(join(self.path, 'setting.conf'))

        for option in self.config['general']:
            if option == 'timeout_refresh':
                # Таймер в программе принимает в миллисекундах значение, по
                # этому переводим минуты в милисекунды
                self.conf[option] = self.config.getint('general', option) * 60000
            else:
                self.conf[option] = self.config.get('general', option)
