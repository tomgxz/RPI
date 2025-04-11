from RPLCD.i2c import CharLCD # type: ignore
from time import sleep

lcd = CharLCD('PCF8574', 0x20, cols=20, rows=4)

lcd.clear()

lcd.write_string("Help!")
lcd.cursor_pos = (2, 0)
lcd.write_string("I am stuck inside\n\rthis LCD display :(")
