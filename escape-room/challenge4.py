import RPi.GPIO as GPIO # type: ignore
from pythonosc import udp_client, dispatcher, osc_server
from pad4pi import rpi_gpio # type: ignore
from threading import Thread
import logging

from LED import LEDIndicator

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG:dict[str, str | int | list[dict] | dict[str, int]] = {    
    "circuit_breakers": [
        {"pin": 17, "needs_cutting": False},  # GPIO 17,  pin 11
        {"pin": 27, "needs_cutting": False},  # GPIO 27,  pin 13
        {"pin": 22, "needs_cutting": False},  # GPIO 22,  pin 15
        {"pin": 10, "needs_cutting": False},  # GPIO 10,  pin 19
        {"pin":  9, "needs_cutting": True},   # GPIO  9,  pin 21
        {"pin": 11, "needs_cutting": False},  # GPIO 11,  pin 23
    ],
    "leds": {
        "red1": 23,
        "red2": 24,
        "green": 25
    },
    "osc_rx_server_ip": "0.0.0.0",
    "osc_rx_server_port": 10001,
    "osc_tx_client_ip": "10.100.20.255",
    "osc_tx_client_port": 10000
}


class DiffusalWire():
    def __init__(self, pin: int, needs_cutting: bool, handler: "DiffusalWire"):
        logging.debug(f"Initializing DiffusalWire: pin={pin}, needs_cutting={needs_cutting}")
        self.handler:"DiffusalWire" = handler
        self.pin:int = pin
        self.needs_cutting:bool = needs_cutting
        
        GPIO.setup(self.pin, GPIO.IN)
        GPIO.add_event_detect(self.pin, GPIO.BOTH, callback=self.handler.on_state_change, bouncetime=200)

    @property
    def state(self) -> bool:
        state = GPIO.input(self.pin) == GPIO.HIGH
        return state
    
    @property
    def valid(self) -> bool:
        valid = self.state != self.needs_cutting
        return valid
    
    def __repr__(self):
        return f"DiffusalWire(pin={self.pin}, needs_cutting={self.needs_cutting}, state={self.state})"


class WireCutHandler():
    def __init__(self):
        logging.debug("Initializing Wire Cut Handler...")
        GPIO.setmode(GPIO.BCM)

        self.wires:list[DiffusalWire] = [
            DiffusalWire(wire["pin"], wire["needs_cutting"], self)
            for wire in CONFIG["circuit_breakers"]
        ]
        
        self.leds:dict[str, LEDIndicator] = {
            f"{name}": LEDIndicator(pin) 
            for name, pin in CONFIG["leds"].items()
        }
        
        self.leds["red1"].flash(interval = 0.15)
        self.leds["red2"].flash(interval = 0.15, initial_delay = 0.08)
        self.leds["green"].state = False
        
        self.__unlocked = False
        self.__exploded = False
        
        self.on_state_change()
        
        osc_rx_dispatcher = dispatcher.Dispatcher()
        osc_rx_dispatcher.map("/escaperoom/challenge/4/reset", self.reset)
        
        osc_rx_server = osc_server.BlockingOSCUDPServer((CONFIG['osc_rx_server_ip'], CONFIG['osc_rx_server_port']), osc_rx_dispatcher)
        logging.debug(f"Starting OSC server listening on {CONFIG['osc_rx_server_ip']}:{CONFIG['osc_rx_server_port']}")
        osc_rx_server.serve_forever()
    
    def on_state_change(self, *a):
        logging.debug("Wire cut state changed")
        
        if self.__unlocked:
            logging.debug("Already unlocked, ignoring state change")
            return
        
        self.__unlocked = False
        self.__exploded = False
        
        for wire in self.wires:
            if not wire.state and wire.needs_cutting:
                self.__unlocked = True
            elif not wire.state and not wire.needs_cutting:
                self.__exploded = True
                
        if self.__exploded:
            logging.debug(f"Incorrect wire cut")
            
            self.leds["red1"].flash(interval = 0.05)
            self.leds["red2"].flash(interval = 0.06)
            self.leds["green"].state = False
            
            logging.debug(f"Sending failure osc command to {CONFIG['osc_tx_client_ip']}:{CONFIG['osc_tx_client_port']}")
                    
            osc_tx_client = udp_client.SimpleUDPClient(CONFIG["osc_tx_client_ip"], CONFIG["osc_tx_client_port"], allow_broadcast=True)
            osc_tx_client.send_message("/escaperoom/challenge/4/failure", 1)
        
        elif self.__unlocked:
            logging.debug(f"Correct wire cut")
            
            for _, led in self.leds.items():
                led.stop_flashing()
                
            self.leds["red1"].state = False
            self.leds["red2"].state = False
            self.leds["green"].state = True

            logging.debug(f"Sending success osc command to {CONFIG['osc_tx_client_ip']}:{CONFIG['osc_tx_client_port']}")
                    
            osc_tx_client = udp_client.SimpleUDPClient(CONFIG["osc_tx_client_ip"], CONFIG["osc_tx_client_port"], allow_broadcast=True)
            osc_tx_client.send_message("/escaperoom/challenge/4/success", 1)

    def reset(self, *a):
        logging.debug("Resetting Handler...")
        
        self.__unlocked = False
        self.__exploded = False
        
        for _, led in self.leds.items():
            led.stop_flashing()
        
        self.leds["red1"].flash(interval = 0.15)
        self.leds["red2"].flash(interval = 0.15, initial_delay = 0.08)
        self.leds["green"].state = False
        
        self.on_state_change()


class KeypadHandler():
    def __init__(self):
        logging.debug("Initializing Keypad Handler...")
        GPIO.setmode(GPIO.BCM)
        
        self.keys = [
            ["1", "2", "3"],
            ["4", "5", "6"],
            ["7", "8", "9"],
            ["*", "0", "#"]
        ]
        
        # from right to left looking at the keypad, the GPIOs wired in to the pins are:
        # 21, 20, 16, 26, 19, 13, 6, 5
        
        self.row_pins = [5, 6, 13]
        self.col_pins = [19, 26, 16, 20]
        
        self.factory = rpi_gpio.KeypadFactory()
        self.keypad = self.factory.create_keypad(keypad=self.keys, row_pins=self.row_pins, col_pins=self.col_pins)
        
        def print_key(key):
            logging.debug(f"Key Pressed: {key}")
        
        self.keypad.registerKeyPressHandler(print_key)
        

class ElectroMagnentHandler():
    def __init__(self):
        logging.debug("Initializing Electromagnet Handler...")
        GPIO.setmode(GPIO.BCM)
        
        self.relay_pin = 4 # GPIO 4, pin 7
        GPIO.setup(self.relay_pin, GPIO.HIGH)
        
        osc_rx_dispatcher = dispatcher.Dispatcher()
        osc_rx_dispatcher.map("/escaperoom/vaultdoor/unlock", self.unlock)
        osc_rx_dispatcher.map("/escaperoom/vaultdoor/lock", self.lock)
        
        osc_rx_server = osc_server.BlockingOSCUDPServer((CONFIG['osc_rx_server_ip'], CONFIG['osc_rx_server_port']), osc_rx_dispatcher)
        logging.debug(f"Starting OSC server listening on {CONFIG['osc_rx_server_ip']}:{CONFIG['osc_rx_server_port']}")
        osc_rx_server.serve_forever()
        
    def unlock(self):
        GPIO.output(self.relay_pin, GPIO.HIGH)
        
    def lock(self):
        GPIO.output(self.relay_pin, GPIO.HIGH)

if __name__ == "__main__":
    Thread(target=WireCutHandler).start()
    Thread(target=KeypadHandler).start()
    Thread(target=ElectroMagnentHandler).start()