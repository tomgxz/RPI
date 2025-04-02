import RPi.GPIO as GPIO
import time

# Set up the GPIO mode
GPIO.setmode(GPIO.BCM)

# GPIO pins for your keypad (replace with your actual pin numbers)
keypad_pins = [21, 20, 16, 26, 19, 13, 6, 5]

# Set all pins as input
for pin in keypad_pins:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

try:
    while True:
        for pin in keypad_pins:
            input_state = GPIO.input(pin)
            if input_state == GPIO.LOW:
                print(f"Button connected to GPIO pin {pin} is pressed.")
            time.sleep(0.1)

except KeyboardInterrupt:
    GPIO.cleanup()