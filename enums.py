import enum


class UpgradeState(enum.Enum):
    """
    Состоение отображающие процесс получения и обработки информации о новых
    сериях
    """
    OK = 0
    CANCELLED = 1
    WARNING = 2
    ERROR = 3

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value

        return NotImplemented


class SupportedSites(enum.Enum):
    """
    Название сайтов, которые поддерживаются приложением
    """
    FILIN = 'filin'
    FILMIX = 'filmix'
    SEASONVAR = 'seasonvar'
