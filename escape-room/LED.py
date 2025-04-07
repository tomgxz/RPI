import RPi.GPIO as GPIO # type: ignore
import logging, time, threading


class LEDIndicator():
    def __init__(self, pin: int):
        logging.debug(f"Initializing LEDIndicator: pin={pin}")
        self.pin:int = pin
        self.__stop_flashing = True
        self.__flash_thread = None
        
        self.__stop_flashing_event = threading.Event()
        self.__stop_flashing_event.clear()
        self.__is_flashing = False
        
        GPIO.setup(self.pin, GPIO.OUT)
        
    @property
    def state(self) -> bool:
        state = GPIO.input(self.pin) == GPIO.HIGH
        return state

    @state.setter
    def state(self, value: bool):
        if not self.__is_flashing:
            logging.debug(f"Setting LEDIndicator(pin={self.pin}) state to: {value}")
        GPIO.output(self.pin, GPIO.HIGH if value else GPIO.LOW)
        
    def flash(self, interval: float = 0.2, initial_delay: float = 0):
        try:
            self.stop_flashing()
            self.state = False

            logging.debug(f"LEDIndicator(pin={self.pin}) start flashing with interval: {interval}")
            self.__stop_flashing_event.clear()

            def thread():
                try:
                    if initial_delay:
                        time.sleep(initial_delay)

                    while not self.__stop_flashing_event.is_set():
                        self.state = not self.state
                        time.sleep(interval)
                except Exception as e:
                    logging.error(f"LEDIndicator(pin={self.pin}) encountered an error in flash thread: {e}")

            self.__flash_thread = threading.Thread(target=thread, daemon=True)
            self.__flash_thread.start()

            self.__is_flashing = True
        except Exception as e:
            logging.error(f"LEDIndicator(pin={self.pin}) failed to start flashing: {e}")

    def stop_flashing(self):
        try:
            if self.__is_flashing:
                logging.debug(f"LEDIndicator(pin={self.pin}) stop flashing")
                self.__stop_flashing_event.set()

                if self.__flash_thread:
                    self.__flash_thread.join(timeout=1)  # Add a timeout to prevent indefinite blocking
                    if self.__flash_thread.is_alive():
                        logging.warning(f"LEDIndicator(pin={self.pin}) flashing thread did not terminate properly")

                self.__is_flashing = False
                self.state = False
        except Exception as e:
            logging.error(f"LEDIndicator(pin={self.pin}) failed to stop flashing: {e}")
    
    def __repr__(self):
        return f"LEDIndicator(pin={self.pin}, state={self.state}, flashing={not self.__stop_flashing})"
