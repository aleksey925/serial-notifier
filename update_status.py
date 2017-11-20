import enum


class UpgradeStatus(enum.Enum):
    """
    Стататусы отображающие процесс получения и обработки информации о новых
    серий
    """
    OK = 'ok'
    ERROR = 'error'
    CANCELLED = 'cancelled'
