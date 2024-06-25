import logging


"""Инициализация логера."""
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
handler = logging.StreamHandler()

"""Настройка вывода логов."""
formatter = logging.Formatter(
    '%(name)s - %(asctime)s - %(module)s - %(lineno)d'
    ' - %(process)d - %(thread)d - %(message)s'
)
handler.setFormatter(formatter)
log.addHandler(handler)
