import os
import asyncio
import logging
import time
from copy import deepcopy
from typing import Callable, Optional
from datetime import datetime
from functools import wraps
import multiprocessing as mp

import websockets
import signal
from peewee import SqliteDatabase, Model, CharField, DateTimeField


db = SqliteDatabase('rpi.db')

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


"""Задействованные пины на плате (GPIO)."""
IN_RPI = False
RELAY_CHANNELS = [4, 17, 27, 22, 23, 24]
WAVE, SIM, READY, ACCEPT, START, CANCEL = 4, 17, 27, 22, 23, 24
START_LED, ACCEPT_LED, CANCEL_LED = 19, 13, 6
LEDS = {
    19: 'START_LED',
    13: 'ACCEPT_LED',
    6: 'CANCEL_LED'
}

CONNECTIONS = set()

STATE = [0, 0, 0, 0, 0, 0]
BLINK_STATE = deepcopy(STATE)

LED_STATUS = {
    True: 'turn_on',
    False: 'turn_off'
}

CANCEL_DELAY = 15
__PROCESSES__ = []


class InvalidButton(Exception):
    """Ошибка при нажатии кнопки не по порядку."""
    pass


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
        """Проверяет, что предыдущая команда действительно была нажата последней."""
        return Logs.get_last_elem().command == command

    @staticmethod
    def check_button_was_pressed_less_than_15_sec(command: str):
        """Проверяет, что кнопка старт была нажата менее чем 15 сек назад."""
        return (
            datetime.now() - Logs.get_last_elem(command).dt
        ).total_seconds() <= 15

    class Meta:
        database = db


class LED:
    """Интерфейс для управления состоянием светодиодов."""

    def __init__(self, port: int, on: bool = False):
        self.on = on
        self.port = port
        self.init_led_gpio(port)

    @staticmethod
    def init_led_gpio(port: int):
        """Инициализируем светодиоды."""
        GPIO.setup(port, GPIO.OUT)

        """Выключаем светодиоды при инициализации."""
        GPIO.output(port, GPIO.LOW)

    def turn_on(self):
        """Метод включающий светодиод."""
        GPIO.output(self.port, GPIO.HIGH)
        self.on = True
        log.info(f'LED on {LEDS[self.port]} is ON!')

    def turn_off(self):
        """Метод выключающий светодиод."""
        GPIO.output(self.port, GPIO.LOW)
        self.on = False
        log.info(f'LED on {LEDS[self.port]} is OFF!')

    def blinking(self, *args, **kwargs):
        """Метод заставляющий светодиод мигать."""
        while True:
            self.turn_on()
            time.sleep(0.75)
            self.turn_off()
            time.sleep(0.75)


def start_auto_off_timer(process, *args, **kwargs):
    """Выключает все светодиоды по истечение 15 сек."""
    log.info('started timer for cancel')
    time.sleep(CANCEL_DELAY)
    stop_processes(process)
    GPIO.output(ACCEPT_LED, GPIO.LOW)
    GPIO.output(START_LED, GPIO.LOW)
    GPIO.output(CANCEL_LED, GPIO.LOW)
    log.info('All LEDs is off now!')


def stop_processes(process=None):
    """Останавливает все запущенные процессы."""
    processes = process if process else __PROCESSES__
    for index in range(len(processes)):
        pid = processes.pop()
        os.kill(pid, signal.SIGKILL)
        log.info(f'{pid} killed!')


def create_process(command, *args, **kwargs):
    """Создает процесс и сохраняет его id."""
    p = mp.Process(target=command, args=args)
    p.start()
    __PROCESSES__.append(p.pid)


def command_wrapper(function):
    """Декоратор, который отправляет логи и сообщения по ws."""
    @wraps(function)
    def wrapper(self, channel=None, *args, **kwargs):
        try:
            global __PROCESSES__
            function(self, channel)
            log.info(self.command)
            websockets.broadcast(CONNECTIONS, self.command)
            if len(__PROCESSES__) > 0:
                stop_processes()
            if self.led:
                if self.led['past']:
                    for led in self.led['past']:
                        led()
                if self.led['future']:
                    for led in self.led['future']:
                        create_process(led, __PROCESSES__)
        except InvalidButton:
            websockets.broadcast(
                CONNECTIONS,
                f'{self.command} command is unavailable now!'
            )
        except Exception as e:
            websockets.broadcast(
                CONNECTIONS,
                str(e)
            )
            log.error(str(e))
        return __PROCESSES__
    return wrapper


class Commands:
    """Интерфейс обработчика событий после нажатия кнопки."""

    def __init__(
        self,
        command: str,
        checker: Callable = None,
        model: Optional[Model] = None,
        led: Optional[dict[LED]] = None,
    ):
        self.command = command
        self.checker = checker
        self.model = model
        self.led = led

    @command_wrapper
    def basic_command(self, channel):
        """Стандартный обработчик нажатия кнопки."""
        ...

    @command_wrapper
    def trigger_command(self, channel=None):
        """Обработчик создающий запись о нажатии в бд."""
        return self.model.create(command=self.command)

    def check_command(self, channel=None):
        """Обработчик проверяющий опред условия перед нажатием кнопки."""
        if not self.checker(check_command_list[self.command]):
            log.info('failed checking')
            log.info('Button pressed in wrong order')
        return self.trigger_command(channel)


async def invalidate_state():
    global STATE
    global BLINK_STATE
    log.info("invalidate_state")
    log.info(STATE)
    for s_idx, s in enumerate(STATE):
        await asyncio.sleep(0.1)
        if (s == 1):
            GPIO.output(RELAY_CHANNELS[s_idx], GPIO.LOW)
        elif (s == 0):
            GPIO.output(RELAY_CHANNELS[s_idx], GPIO.HIGH)
        elif (s == 2):
            if (BLINK_STATE[s_idx] == 0):
                GPIO.output(RELAY_CHANNELS[s_idx], GPIO.HIGH)
            else:
                GPIO.output(RELAY_CHANNELS[s_idx], GPIO.LOW)
    websockets.broadcast(CONNECTIONS, " ".join(map(str, STATE)))


async def invalidate_blink():
    invalidated = False
    for s_idx, s in enumerate(STATE):
        if (s == 2):
            BLINK_STATE[s_idx] = abs(BLINK_STATE[s_idx] - 1)
            invalidated = True

    if (invalidated):
        log.info("invalidate_blink")
        log.info(BLINK_STATE)
        await invalidate_state()


async def register(websocket):
    CONNECTIONS.add(websocket)
    log.info('Connect registration...')
    try:
        async for message in websocket:
            log.info(message)
            cmd = message.split(':')
            idx = int(cmd[1]) - 1
            STATE[idx] = int(cmd[0])
            await invalidate_state()
            await websocket.wait_closed()
    finally:
        log.info('Connection abroted.')
        CONNECTIONS.remove(websocket)


async def main():
    """Инициализация веб сервера."""
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)
    async with websockets.serve(
        register, port=8765,
    ):
        # main loop
        log.info('Connection served')
        global STATE
        global BLINK_STATE
        while True:
            await asyncio.sleep(0.5)
            await invalidate_blink()
            await asyncio.Future()


def setup_rpi_handlers():
    """Метод инициализации кнопок и севтодиодов на плате."""

    log.info("Setup")
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    """Светодиоды."""
    accept_led = LED(port=ACCEPT_LED, on=False)
    start_led = LED(port=START_LED, on=False)
    cancel_led = LED(port=CANCEL_LED, on=False)

    """Кнопки."""
    GPIO.setup(WAVE, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # волна
    GPIO.setup(SIM, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # sim
    GPIO.setup(READY, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # готов
    GPIO.setup(ACCEPT, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # подтвердить
    GPIO.setup(CANCEL, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # пуск
    GPIO.setup(START, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # отмена

    """Триггеры на кнопки,"""
    GPIO.add_event_detect(SIM, GPIO.BOTH, callback=Commands(
            command='sim pressed'
        ).basic_command,
        bouncetime=80)
    GPIO.add_event_detect(
        WAVE,
        GPIO.BOTH,
        callback=Commands(
            command='wave pressed'
        ).basic_command,
        bouncetime=80
    )
    GPIO.add_event_detect(
        READY, GPIO.BOTH,
        callback=Commands(
            command='ready pressed', model=Logs,
            led={
                'past': None,
                'future': [accept_led.blinking],
            }
        ).trigger_command, bouncetime=80
    )
    GPIO.add_event_detect(
        ACCEPT, GPIO.BOTH,
        callback=Commands(
            command='accept pressed',
            model=Logs,
            led={
                'past': [accept_led.turn_on],
                'future': [start_led.blinking],
            },
            checker=Logs.check_last_elem_command
        ).check_command,
        bouncetime=300
    )
    GPIO.add_event_detect(
        START, GPIO.BOTH,
        callback=Commands(
            command='start pressed', model=Logs,
            led={
                'past': [start_led.turn_on],
                'future': [cancel_led.blinking, start_auto_off_timer],
            },
            checker=Logs.check_last_elem_command,
        ).check_command,
        bouncetime=80
    )
    GPIO.add_event_detect(
        CANCEL, GPIO.BOTH,
        callback=Commands(
            command='cancel pressed',
            led={
                'past': [
                    accept_led.turn_off,
                    start_led.turn_off,
                    cancel_led.turn_off
                ],
                'future': None,
            },
            model=Logs,
            checker=Logs.check_button_was_pressed_less_than_15_sec
        ).check_command,
        bouncetime=80
    )


def init_db(db: SqliteDatabase, tables: list):
    """Метод инициализирующий бд."""
    db.connect()
    db.drop_tables(tables)
    db.create_tables(tables)


if __name__ == "__main__":
    check_command_list = {
        'start pressed': 'accept pressed',
        'accept pressed': 'ready pressed',
        'cancel pressed': 'start pressed'
    }
    accept_led = LED(port=ACCEPT_LED, on=False)
    start_led = LED(port=START_LED, on=False)
    cancel_led = LED(port=CANCEL_LED, on=False)
    try:
        init_db(db, [Logs])
        try:
            import RPi.GPIO as GPIO
            IN_RPI = True
        except ModuleNotFoundError:
            log.info("No module")
            pass
        if IN_RPI:
            setup_rpi_handlers()
        asyncio.run(main())
    except KeyboardInterrupt:
        GPIO.cleanup()
