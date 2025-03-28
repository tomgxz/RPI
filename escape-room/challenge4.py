import RPi.GPIO as GPIO # type: ignore
from pythonosc import udp_client, dispatcher, osc_server
import logging

from LED import LEDIndicator

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG:dict[str, str | int | list[dict] | dict[str, int]] = {
    "circuit_breakers": [
        {"pin":  4, "needs_cutting": False},  # GPIO  4,  pin  7
        {"pin": 14, "needs_cutting": False},  # GPIO 14,  pin  8
        {"pin": 17, "needs_cutting": False},  # GPIO 17,  pin 11
        {"pin": 18, "needs_cutting": False},  # GPIO 18,  pin 12
        {"pin": 22, "needs_cutting": True},   # GPIO 22,  pin 15
        {"pin": 23, "needs_cutting": False},  # GPIO 23,  pin 16
    ],
    "leds": {
        "red1": 19,
        "red2": 26,
        "green": 16
    },
    "osc_rx_server_ip": "0.0.0.0",
    "osc_rx_server_port": 8001,
    "osc_tx_client_ip": "10.100.20.255",
    "osc_tx_client_port": 8000
}


class DiffusalWire():
    def __init__(self, pin: int, needs_cutting: bool, handler: "Handler"):
        logging.debug(f"Initializing DiffusalWire: pin={pin}, needs_cutting={needs_cutting}")
        self.handler:"Handler" = handler
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


class Handler():
    def __init__(self):
        logging.debug("Initializing Handler...")
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
        self.leds["red2"].flash(interval = 0.15, initial_delay = 0.1)
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
        self.leds["red2"].flash(interval = 0.15, initial_delay = 0.1)
        self.leds["green"].state = False
        
        self.on_state_change()


if __name__ == "__main__":
    handler = Handler()