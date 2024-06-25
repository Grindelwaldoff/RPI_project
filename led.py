import time

from logger import log


try:
    import RPi.GPIO as GPIO
    IN_RPI = True
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
except ModuleNotFoundError:
    log.info("No module")
    pass


# порты светодиодов на плате
START_LED, ACCEPT_LED, CANCEL_LED, READY_LED = 19, 13, 25, 16

LEDS = {
    19: 'START_LED',
    13: 'ACCEPT_LED',
    25: 'CANCEL_LED',
    16: 'READY_LED',
}


class LED:
    """Абстрактный интерфейс для управления состоянием светодиодов."""

    def __init__(self, port: int, on: bool = False):
        self.on = on
        self.port = port
        self.init_led_gpio(port)

    @staticmethod
    def init_led_gpio(port: int):
        """Инициализируем светодиоды."""
        # GPIO.setup(port, GPIO.OUT)

        """Выключаем светодиоды при инициализации."""
        # GPIO.output(port, GPIO.LOW)

    def turn_on(self):
        """Метод включающий светодиод."""
        # GPIO.output(self.port, GPIO.HIGH)
        self.on = True
        log.info(f'LED on {LEDS[self.port]} is ON!')

    def turn_off(self):
        """Метод выключающий светодиод."""
        # GPIO.output(self.port, GPIO.LOW)
        self.on = False
        log.info(f'LED on {LEDS[self.port]} is OFF!')

    def blinking_algorithm(self):
        self.turn_on()
        time.sleep(0.75)
        self.turn_off()
        time.sleep(0.75)

    def _blinking(self, event):
        while not event.is_set():
            self.blinking_algorithm()

    def blinking(self, *args, **kwargs):
        """Метод заставляющий светодиод мигать."""
        while True:
            self.blinking_algorithm()


ready_led = LED(port=READY_LED, on=False)
accept_led = LED(port=ACCEPT_LED, on=False)
start_led = LED(port=START_LED, on=False)
cancel_led = LED(port=CANCEL_LED, on=False)
