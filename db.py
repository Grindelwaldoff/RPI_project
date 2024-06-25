from datetime import datetime

from peewee import SqliteDatabase, DateTimeField, CharField, Model


database = SqliteDatabase('rpi.db')


class Logs(Model):
    """Модель журнала нажатий кнопок."""
    dt = DateTimeField(default=datetime.now)
    command = CharField()

    @staticmethod
    def get_last_elem(command: str = None):
        """Метод возвращающий последний элемент."""
        elem = Logs.select().order_by(Logs.id.desc())
        if command:
            elem = elem.where(Logs.command == command)
        return elem.get()

    @staticmethod
    def check_last_elem_command(command: str):
        """Метод проверяющий последнюю команду."""
        return Logs.get_last_elem().command == command

    @staticmethod
    def check_button_was_pressed_less_than_15_sec(command: str):
        """Метод проверяющий время нажатия последней команды"""
        return (
            datetime.now() - Logs.get_last_elem(command).dt
        ).total_seconds() <= 15

    class Meta:
        database = database


def init_db(db: SqliteDatabase, tables: list):
    """Метод инициализирующий бд."""
    db.connect()
    db.drop_tables(tables)
    db.create_tables(tables)
