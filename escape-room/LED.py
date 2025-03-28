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
        self.stop_flashing()
        self.state = False
        
        logging.debug(f"LEDIndicator(pin={self.pin}) start flashing with interval: {interval}")
        self.__stop_flashing_event.clear()
        
        def thread():
            if initial_delay:
                time.sleep(interval)
            
            while not self.__stop_flashing_event.is_set():
                self.state = not self.state
                time.sleep(interval)
                
        self.__flash_thread = threading.Thread(target=thread)
        self.__flash_thread.start()
        
        self.__is_flashing = True
        
    def stop_flashing(self):
        if self.__is_flashing:
            logging.debug(f"LEDIndicator(pin={self.pin}) stop flashing")
            self.__stop_flashing_event.set()
            self.__flash_thread.join()
            
            self.__is_flashing = False
            self.state = False
    
    def __repr__(self):
        return f"LEDIndicator(pin={self.pin}, state={self.state}, flashing={not self.__stop_flashing})"
