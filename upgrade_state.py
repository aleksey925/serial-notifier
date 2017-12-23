import enum


class UpgradeState(enum.Enum):
    """
    Состоение отображающие процесс получения и обработки информации о новых
    серий
    """
    OK = 'ok'
    ERROR = 'error'
    CANCELLED = 'cancelled'
