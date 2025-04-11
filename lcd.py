from RPLCD.i2c import CharLCD # type: ignore
from time import sleep

# Create LCD instance (check number of columns and rows!)
lcd = CharLCD('PCF8574', 0x20, cols=20, rows=4, backlight_enabled=False)

# Clear and write message
lcd.clear()
lcd.write_string("Hello, world!")

# Keep it on screen for 5 seconds
sleep(5)
lcd.clear()
