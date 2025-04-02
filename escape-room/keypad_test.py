import RPi.GPIO as GPIO
import time

# Set up the GPIO mode
GPIO.setmode(GPIO.BCM)

# from right to left looking at the keypad, the GPIOs wired in to the pins are:
# 21, 20, 16, 26, 19, 13, 6, 5
    
# Define GPIO pins for rows and columns
cols = [13, 6, 5]
rows = [20, 16, 26, 19]

# Set up the GPIO pins for rows (input with pull-up)
for row in rows:
    GPIO.setup(row, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Set up the GPIO pins for columns (output)
for col in cols:
    GPIO.setup(col, GPIO.OUT)
    GPIO.output(col, GPIO.HIGH)  # Initially set columns to HIGH (inactive)

# Define the keypad matrix layout (rows x cols)
keypad = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ['*', '0', '#']
]

try:
    while True:
        for col_num, col in enumerate(cols):
            # Set the current column to LOW
            GPIO.output(col, GPIO.LOW)
            
            # Check each row to see if it's pressed
            for row_num, row in enumerate(rows):
                if GPIO.input(row) == GPIO.LOW:  # If button is pressed
                    print(f"Button {keypad[row_num][col_num]} pressed (Row {row_num+1}, Col {col_num+1})")
                    time.sleep(0.2)  # Debounce time
                
            # Set the column back to HIGH
            GPIO.output(col, GPIO.HIGH)

        time.sleep(0.1)  # Short delay between column scans

except KeyboardInterrupt:
    GPIO.cleanup()
