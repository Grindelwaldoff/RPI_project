# asyncio.run(main())
    # init_db(db, [Logs])
    # while True:
    #     ...
    #     if SIGNAL:
    #         print(THREAD)
    # Commands(
    #     command='ready pressed', model=Logs,
    #     led={
    #         'past': [set_thread, ready_led.turn_on],
    #         'future': [accept_led.blinking],
    #     }
    # ).trigger_command([1])
    # time.sleep(2)
    # Commands(
    #     command='accept pressed',
    #     model=Logs,
    #     led={
    #         'past': [accept_led.turn_on],
    #         'future': [start_led.blinking],
    #     },
    #     checker=Logs.check_last_elem_command
    # ).check_command([1])
    # log.info(SIGNAL)
    # time.sleep(2)
    # Commands(
    #     command='start pressed', model=Logs,
    #     led={
    #         'past': [start_led.turn_on],
    #         'future': [cancel_led.blinking, start_auto_off_timer],
    #     },
    #     checker=Logs.check_last_elem_command,
    # ).check_command([1])
    # time.sleep(2)
    # log.info(SIGNAL)
    # Commands(
    #     command='cancel pressed',
    #     led={
    #         'past': [
    #             accept_led.turn_off,
    #             start_led.turn_off,
    #             cancel_led.turn_off
    #         ],
    #         'future': None,
    #     },
    #     model=Logs,
    #     checker=Logs.check_button_was_pressed_less_than_15_sec
    # ).check_command([1])
    # log.info(SIGNAL)
    # time.sleep(5)
    # Commands(
    #     command='ready pressed', model=Logs,
    #     led={
    #         'past': [set_thread, ready_led.turn_on],
    #         'future': [accept_led.blinking],
    #     }
    # ).trigger_command([1])
