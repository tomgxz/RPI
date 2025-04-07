import RPi.GPIO as GPIO # type: ignore
from pythonosc import udp_client, dispatcher, osc_server
import time, threading
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG = {
    "circuit_breakers": [
        {"pin":  4, "valid_state": True},   # GPIO  4,  pin  7
        {"pin": 14, "valid_state": False},  # GPIO 14,  pin  8
        {"pin": 17, "valid_state": False},  # GPIO 17,  pin 11
        {"pin": 18, "valid_state": False},  # GPIO 18,  pin 12
        {"pin": 22, "valid_state": True},   # GPIO 22,  pin 15
        {"pin": 23, "valid_state": True},   # GPIO 23,  pin 16
        {"pin":  9, "valid_state": False},  # GPIO  9,  pin 21
        {"pin": 25, "valid_state": True},   # GPIO 25,  pin 22
        {"pin": 11, "valid_state": False},  # GPIO 11,  pin 23
        {"pin":  8, "valid_state": False},  # GPIO  8,  pin 24
        {"pin":  6, "valid_state": True},   # GPIO  6,  pin 31
        {"pin": 12, "valid_state": True}    # GPIO 12,  pin 32
    ],
    "leds": [19, 16, 26], # Pins 35, 36, 37
    "osc_rx_server_ip": "0.0.0.0",
    "osc_rx_server_port": 10001,
    "osc_tx_client_ip": "10.100.20.255",
    "osc_tx_client_port": 10000
}


class CircuitBreaker():
    def __init__(self, pin: int, valid_state: bool, handler: "Handler"):
        logging.debug(f"Initializing CircuitBreaker: pin={pin}, valid_state={valid_state}")
        self.handler:"Handler" = handler
        self.pin:int = pin
        self.valid_state:bool = valid_state
        
        GPIO.setup(self.pin, GPIO.IN)
        GPIO.add_event_detect(self.pin, GPIO.BOTH, callback=self.handler.on_breaker_change, bouncetime=200)

    @property
    def state(self) -> bool:
        state = GPIO.input(self.pin) == GPIO.HIGH
        return state
    
    @property
    def valid(self) -> bool:
        valid = self.state == self.valid_state
        return valid
    
    def __repr__(self):
        return f"CircuitBreaker(pin={self.pin}, valid_state={self.valid_state}, state={self.state}, valid={self.valid})"


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
        
    def flash(self, interval: float = 0.2):
        logging.debug(f"LEDIndicator(pin={self.pin}) start flashing with interval: {interval}")
        self.__stop_flashing_event.clear()
        
        def thread():
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


class Handler():
    def __init__(self):
        logging.debug("Initializing Handler...")
        GPIO.setmode(GPIO.BCM)

        self.breakers:list[CircuitBreaker] = [
            CircuitBreaker(breaker["pin"], breaker["valid_state"], self)
            for breaker in CONFIG["circuit_breakers"]
        ]
        
        self.leds:list[LEDIndicator] = [LEDIndicator(pin) for pin in CONFIG["leds"]]
        
        for led in self.leds:
            led.state = False
        
        self.__unlocked = False
        
        self.counter:int = 0
        self.on_breaker_change()
        
        osc_rx_dispatcher = dispatcher.Dispatcher()
        osc_rx_dispatcher.map("/escaperoom/challenge/1/reset", self.reset)
        
        osc_rx_server = osc_server.BlockingOSCUDPServer((CONFIG['osc_rx_server_ip'], CONFIG['osc_rx_server_port']), osc_rx_dispatcher)
        logging.debug(f"Starting OSC server listening on {CONFIG['osc_rx_server_ip']}:{CONFIG['osc_rx_server_port']}")
        osc_rx_server.serve_forever()
    
    def on_breaker_change(self, *a):
        logging.debug("Breaker state changed")
        
        if self.__unlocked:
            logging.debug("Already unlocked, ignoring breaker change")
            return
        
        self.counter = 0
        
        for breaker in self.breakers:
            if breaker.state: # if the breaker is on
                self.counter += 1 if breaker.valid else -1 # increment or decrement based on whether breaker should be on or off
        
        logging.debug(f"Counter: {self.counter}")
        
        for index, led in enumerate(self.leds):
            if (index + 0.5) * 2 < self.counter:
                led.stop_flashing()
                led.state = True
                
            elif (index + 0.5) * 2 == self.counter:
                led.flash()
                
            else:
                led.stop_flashing()
        
        if self.counter == 6:
            logging.debug(f"Sending success osc command to {CONFIG['osc_tx_client_ip']}:{CONFIG['osc_tx_client_port']}")
            
            self.__unlocked = True
            
            osc_tx_client = udp_client.SimpleUDPClient(CONFIG["osc_tx_client_ip"], CONFIG["osc_tx_client_port"], allow_broadcast=True)
            osc_tx_client.send_message("/escaperoom/challenge/1/success", 1)

    def reset(self, *a):
        logging.debug("Resetting Handler...")
        self.__unlocked = False
        
        for led in self.leds:
            led.stop_flashing()
            led.state = False
            
        self.counter = 0
        self.on_breaker_change()


if __name__ == "__main__":
    handler = Handler()