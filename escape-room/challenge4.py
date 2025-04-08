import RPi.GPIO as GPIO # type: ignore
from pythonosc import udp_client, dispatcher, osc_server
from pad4pi import rpi_gpio # type: ignore
import logging, time

from LED import LEDIndicator

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG:dict[str, str | int | list[dict] | dict[str, int]] = {    
    "circuit_breakers": [
        {"pin": 18, "needs_cutting": False},  # GPIO 18,  pin 12
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


class OSCController():
    def __init__(self, rx_ip: str, rx_port: int, tx_ip: str, tx_port: int):
        logging.debug("OSC - Initializing OSC Controller...")
        self.rx_ip = rx_ip
        self.rx_port = rx_port
        self.tx_ip = tx_ip
        self.tx_port = tx_port

        self.dispatcher = dispatcher.Dispatcher()
        self.server = osc_server.BlockingOSCUDPServer((self.rx_ip, self.rx_port), self.dispatcher)
        self.server_active = False

    def add_handler(self, address: str, handler):
        self.dispatcher.map(address, handler)

    def start_server(self):
        logging.debug(f"OSC - Starting OSC server listening on {self.rx_ip}:{self.rx_port}")
        
        if self.server_active:
            logging.debug("OSC - Server is already running, stopping it...")
            self.server.shutdown()
        
        self.server.serve_forever()

    def send_message(self, address: str, value):
        logging.debug(f"OSC - Sending OSC message to {self.tx_ip}:{self.tx_port} - {address}: {value}")
        client = udp_client.SimpleUDPClient(self.tx_ip, self.tx_port, allow_broadcast=True)
        client.send_message(address, value)
        

class DiffusalWire():
    def __init__(self, pin: int, needs_cutting: bool, handler: "Handler"):
        logging.debug(f"WIRECUT - Initializing DiffusalWire: pin={pin}, needs_cutting={needs_cutting}")
        self.handler:"Handler" = handler
        self.pin:int = pin
        self.needs_cutting:bool = needs_cutting
        
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.add_event_detect(self.pin, GPIO.BOTH, callback=self.handler.wirecut_on_state_change, bouncetime=200)

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


class Handler():
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        
        self.osc_controller = OSCController(
            CONFIG['osc_rx_server_ip'], CONFIG['osc_rx_server_port'],
            CONFIG['osc_tx_client_ip'], CONFIG['osc_tx_client_port']
        )
        
        self.keypad_started = False
        self.keypad_finished = False
        
        self.init_wire_cutting()
        self.init_keypad()
        self.init_vault_door()
        
        self.osc_controller.start_server()
        
    
    def init_wire_cutting(self):
        logging.debug("WIRECUT - Initializing Wire Cut Handler...")

        self.wirecut_wires:list[DiffusalWire] = [
            DiffusalWire(wire["pin"], wire["needs_cutting"], self)
            for wire in CONFIG["circuit_breakers"]
        ]
        
        self.wirecut_leds:dict[str, LEDIndicator] = {
            f"{name}": LEDIndicator(pin) 
            for name, pin in CONFIG["leds"].items()
        }
        
        self.wirecut_leds["red1"].flash(interval = 0.15)
        self.wirecut_leds["red2"].flash(interval = 0.15, initial_delay = 0.08)
        self.wirecut_leds["green"].state = False
        
        self.wirecut__unlocked = False
        self.wirecut__exploded = False

        def reset( *a):
            logging.debug("WIRECUT - Resetting Handler...")
            
            self.wirecut__unlocked = False
            self.wirecut__exploded = False
            
            for _, led in self.wirecut_leds.items():
                led.stop_flashing()
            
            self.wirecut_leds["red1"].flash(interval = 0.15)
            self.wirecut_leds["red2"].flash(interval = 0.15, initial_delay = 0.08)
            self.wirecut_leds["green"].state = False
            
            self.wirecut_on_state_change()
    
        self.wirecut_on_state_change()
        
        self.osc_controller.add_handler("/escaperoom/challenge/4/reset", reset)
    
    
    def wirecut_on_state_change(self, *a):
        logging.debug("WIRECUT - Wire cut state changed")
        
        if self.wirecut__unlocked or self.wirecut__exploded:
            logging.debug("WIRECUT - Already unlocked, ignoring state change")
            return
        
        self.wirecut__unlocked = False
        self.wirecut__exploded = False
        
        cut_state = ""
        
        time.sleep(0.1)
        
        for wire in self.wirecut_wires:
            cut_state += str(int(wire.state))
            
            if not wire.state and wire.needs_cutting:
                self.wirecut__unlocked = True
            elif not wire.state and not wire.needs_cutting:
                self.wirecut__exploded = True
                
        logging.debug(f"WIRECUT - Current Wire Connections: {cut_state}")
        
        if self.wirecut__exploded:
            logging.debug(f"WIRECUT - Incorrect wire cut")
            
            self.wirecut_leds["red1"].flash(interval = 0.05)
            self.wirecut_leds["red2"].flash(interval = 0.06)
            self.wirecut_leds["green"].state = False
            
            print("Got here")
            
            logging.debug(f"WIRECUT - Sending failure osc command to {CONFIG['osc_tx_client_ip']}:{CONFIG['osc_tx_client_port']}")
            self.osc_controller.send_message("/escaperoom/challenge/4/failure", 1)
            
            print("Got here 2")
        
        elif self.wirecut__unlocked:
            logging.debug(f"WIRECUT - Correct wire cut")
            
            for _, led in self.wirecut_leds.items():
                led.stop_flashing()
                
            self.wirecut_leds["red1"].state = False
            self.wirecut_leds["red2"].state = False
            self.wirecut_leds["green"].state = True
            
            self.keypad_started = True # enable keypad

    
    def init_keypad(self):
        logging.debug("KEYPAD - Initializing Keypad Handler...")
        
        self.keypad_keys = [
            ["1", "2", "3"],
            ["4", "5", "6"],
            ["7", "8", "9"],
            ["*", "0", "#"]
        ]
        
        # from right to left looking at the keypad, the GPIOs wired in to the pins are:
        # 21, 20, 16, 26, 19, 13, 6, 5
        
        self.keypad_row_pins = [19, 26, 16, 20]
        self.keypad_col_pins = [6, 5, 13] 
        
        self.keypad_factory = rpi_gpio.KeypadFactory()
        self.keypad_keypad = self.keypad_factory.create_keypad(keypad=self.keypad_keys, row_pins=self.keypad_row_pins, col_pins=self.keypad_col_pins)
        
        self.keypad_input = ""
        self.keypad_strikes = 0
        self.correct_code = "8140"       
        
        def handle_key(key):
            logging.debug(f"KEYPAD - Key Pressed: {key}")
            
            if not self.keypad_started:
                logging.debug(f"KEYPAD - Puzzle not started, ignoring")
                return
            
            if self.keypad_finished:
                logging.debug(f"KEYPAD - Completed puzzle, ignoring")
                return
            
            if key in ["*", "#"]:  # Clear button
                logging.debug("KEYPAD - Input cleared")
                self.keypad_input = ""
                return
            
            self.keypad_input += key
            logging.debug(f"KEYPAD - Current Input: {self.keypad_input}")
            
            if len(self.keypad_input) == 4:  # Check if 4 digits are entered
                if self.keypad_input == self.correct_code:
                    logging.debug("KEYPAD - Correct code entered")
                    self.osc_controller.send_message("/escaperoom/challenge/4/success", 1)
                    self.keypad_finished = True
                else:
                    logging.debug("KEYPAD - Incorrect code entered")
                    self.keypad_strikes += 1
                    
                    if self.keypad_strikes >= 3:
                        logging.debug("KEYPAD - 3 strikes reached")
                        self.osc_controller.send_message("/escaperoom/challenge/4/failure", 1)
                        self.keypad_finished = True
                        
                    else:
                        self.osc_controller.send_message("/escaperoom/challenge/4/keypad/incorrect", 1)
                        self.keypad_input = ""
        
        self.keypad_keypad.registerKeyPressHandler(handle_key)
    
    
    def init_vault_door(self):
        logging.debug("ELECTROMAGNET - Initializing Electromagnet Handler...")
        
        relay_pin = 4
        
        GPIO.setup(relay_pin, GPIO.OUT)
        GPIO.output(relay_pin, GPIO.LOW)
        
        def unlock(self, *args):
            logging.debug("ELECTROMAGNET - Unlocking door...")
            GPIO.output(relay_pin, GPIO.LOW)
            
        def lock(self, *args):
            logging.debug("ELECTROMAGNET - Locking door...")
            GPIO.output(relay_pin, GPIO.HIGH)
            
        self.osc_controller.add_handler("/escaperoom/vaultdoor/unlock", unlock)
        self.osc_controller.add_handler("/escaperoom/vaultdoor/lock", lock)
        

if __name__ == "__main__":
    Handler()