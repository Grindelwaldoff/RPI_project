try:
        import RPi.GPIO as GPIO
        IN_RPI = True
    except ModuleNotFoundError:
        log.info("No module")
        pass
    init_db(db, [Logs])
    Commands(
        command='ready pressed', model=Logs,
        led={
            'past': None,
            'future': [accept_led.blinking],
        }
    ).trigger_command([1])
    Commands(
        command='accept pressed',
        model=Logs,
        led={
            'past': [accept_led.turn_on],
            'future': [start_led.blinking],
        },
        checker=Logs.check_last_elem_command
    ).check_command([1])
    Commands(
        command='start pressed', model=Logs,
        led={
            'past': [start_led.turn_on],
            'future': [cancel_led.blinking, LED.start_auto_off_timer],
        },
        checker=Logs.check_last_elem_command,
    ).check_command([1])
    Commands(
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
    ).check_command([1])
    time.sleep(5)

