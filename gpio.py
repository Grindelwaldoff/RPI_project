import os
import time
import signal
import asyncio
import threading
import websockets
import multiprocessing as mp
from typing import Callable, Optional
from functools import wraps

from peewee import Model

import db
import exceptions
from led import (
    LED,
    ACCEPT_LED,
    READY_LED,
    START_LED,
    CANCEL_LED,
    accept_led,
    ready_led,
    cancel_led,
    start_led,
)
from logger import log

IN_RPI = False

try:
    import RPi.GPIO as GPIO
    IN_RPI = True
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
except ModuleNotFoundError:
    log.info("No module")
    pass

# порты кнопок на плате
WAVE, SIM, READY, ACCEPT, START, CANCEL = 4, 17, 27, 22, 23, 24

__PROCESSES__ = []

# время через которое сценарий оканчивается после нажатия start
CANCEL_DELAY = 15

# последовательность команд для проверки верной очередности
check_command_list = {
    "start pressed": "accept pressed",
    "accept pressed": "ready pressed",
    "cancel pressed": "start pressed",
}

THREAD = None
SIGNAL = False

# активные ws подключения
CONNECTIONS = set()


def start_ready_blinking():
    """
    Метод запускающий мигание ready_led
    и активирующий сценарий, после команды 'ready' с вебсокетами.
    """
    global SIGNAL, THREAD
    THREAD = threading.Event()
    threading.Thread(target=ready_led._blinking, args=(THREAD,)).start()
    SIGNAL = True
    return THREAD, SIGNAL


def set_thread():
    """Метод прекращеия мигания ready_led."""
    global THREAD
    THREAD.set()
    return THREAD


def abort_scenario():
    """Метод прерывающий сценарий."""
    global SIGNAL
    set_thread()
    stop_processes()
    ready_led.turn_off()
    start_led.turn_off()
    accept_led.turn_off()
    cancel_led.turn_off()
    log.info(THREAD)
    SIGNAL = False
    return THREAD, SIGNAL


async def register(websocket: websockets):
    """Обработчик сообщений с вебсокета."""
    CONNECTIONS.add(websocket)
    log.info("Connect registration...")
    try:
        while True:
            message = await websocket.recv()
            log.info(message)
            if message == "ready":
                start_ready_blinking()
            if message == "cancel":
                abort_scenario()
    finally:
        log.info("Connection abroted.")
        CONNECTIONS.remove(websocket)


async def main():
    """Инициализация веб сервера."""
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)
    async with websockets.serve(
        register,
        port=8766,
    ):
        # main loop
        log.info("Connection served")
        while True:
            await asyncio.Future()


def command_wrapper(function):
    """
    Декоратор, который отправляет логи и
    сообщения по ws и выполняет основной алгоритм.
    """

    @wraps(function)
    def wrapper(self, channel=None, *args, **kwargs):
        try:
            global SIGNAL
            global __PROCESSES__
            log.info(THREAD)
            function(self, channel)
            log.info(self.command)
            websockets.broadcast(CONNECTIONS, self.command)
            if len(__PROCESSES__) > 0:
                stop_processes()
            if self.led:
                for key in ["past", "future"]:
                    if self.led.get(key):
                        for led in self.led[key]:
                            (
                                led()
                                if key == "past"
                                else create_process(led, __PROCESSES__)
                            )
            if "start" in self.command:
                SIGNAL = False
        except exceptions.InvalidButton:
            websockets.broadcast(
                CONNECTIONS, f"{self.command} command is unavailable now!"
            )
        except Exception as e:
            websockets.broadcast(CONNECTIONS, str(e))
            log.error(str(e))
        return __PROCESSES__, SIGNAL

    return wrapper


class Commands:
    """Абстрактный интерфейс обработчика событий после нажатия кнопки."""

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
        global SIGNAL
        log.info(SIGNAL)
        if SIGNAL:
            return self.model.create(command=self.command)

    def check_command(self, channel=None):
        """Обработчик проверяющий опред условия перед нажатием кнопки."""
        global SIGNAL
        log.info(SIGNAL)
        if self.checker(check_command_list[self.command]) and (
            SIGNAL or "cancel" in self.command
        ):
            return self.trigger_command(channel)
        log.info("failed checking")
        raise exceptions.InvalidButton("Button pressed in wrong order")


def start_auto_off_timer(process, *args, **kwargs):
    """Выключает все светодиоды по истечение 15 сек."""
    log.info("started timer for cancel")
    time.sleep(CANCEL_DELAY)
    stop_processes(process)
    GPIO.output(READY_LED, GPIO.LOW)
    GPIO.output(ACCEPT_LED, GPIO.LOW)
    GPIO.output(START_LED, GPIO.LOW)
    GPIO.output(CANCEL_LED, GPIO.LOW)
    log.info("All LEDs is off now!")


def stop_processes(process=None):
    """
    Метод останавливающий все созданные
    нажатием предыдущей кнопки процессы.
    """
    processes = process if process else __PROCESSES__
    if process is not None and process != []:
        for elem_index in range(len(processes)):
            pid = processes.pop()
            os.kill(pid, signal.SIGKILL)
            log.info(f"{pid} killed!")


def create_process(command, *args, **kwargs):
    """
    Метод создающий будущие процессы при нажатии кнопки.
    """
    p = mp.Process(target=command, args=args)
    p.start()
    __PROCESSES__.append(p.pid)
    return __PROCESSES__


def setup_rpi_handlers():
    """Метод инициализации кнопок и севтодиодов на плате."""

    log.info("Setup")

    """Кнопки."""
    GPIO.setup(WAVE, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # волна
    GPIO.setup(SIM, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # sim
    GPIO.setup(READY, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # готов
    GPIO.setup(ACCEPT, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # подтвердить
    GPIO.setup(CANCEL, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # пуск
    GPIO.setup(START, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # отмена

    """Триггеры на кнопки,"""
    GPIO.add_event_detect(
        SIM,
        GPIO.BOTH,
        callback=Commands(command="sim pressed").basic_command,
        bouncetime=40,
    )
    GPIO.add_event_detect(
        WAVE,
        GPIO.BOTH,
        callback=Commands(command="wave pressed").basic_command,
        bouncetime=40,
    )
    GPIO.add_event_detect(
        READY,
        GPIO.BOTH,
        callback=Commands(
            command="ready pressed",
            model=db.Logs,
            led={
                "past": [set_thread, ready_led.turn_on],
                "future": [accept_led.blinking],
            },
        ).trigger_command,
        bouncetime=40,
    )
    GPIO.add_event_detect(
        ACCEPT,
        GPIO.BOTH,
        callback=Commands(
            command="accept pressed",
            model=db.Logs,
            led={
                "past": [accept_led.turn_on],
                "future": [start_led.blinking],
            },
            checker=db.Logs.check_last_elem_command,
        ).check_command,
        bouncetime=40,
    )
    GPIO.add_event_detect(
        START,
        GPIO.BOTH,
        callback=Commands(
            command="start pressed",
            model=db.Logs,
            led={
                "past": [start_led.turn_on],
                "future": [cancel_led.blinking, start_auto_off_timer],
            },
            checker=db.Logs.check_last_elem_command,
        ).check_command,
        bouncetime=40,
    )
    GPIO.add_event_detect(
        CANCEL,
        GPIO.BOTH,
        callback=Commands(
            command="cancel pressed",
            led={
                "past": [abort_scenario],
                "future": None,
            },
            model=db.Logs,
            checker=db.Logs.check_button_was_pressed_less_than_15_sec,
        ).check_command,
        bouncetime=40,
    )


if __name__ == "__main__":
    try:
        db.init_db(db.database, [db.Logs])
        if IN_RPI:
            setup_rpi_handlers()
        asyncio.run(main())
    except KeyboardInterrupt:
        GPIO.cleanup()
