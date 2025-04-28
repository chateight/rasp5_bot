# servo_control.py
import gpiod
import time
import sys

CHIP = 'gpiochip4'
PIN = 18

angle = float(sys.argv[1])
duration = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0  # デフォルト1秒

chip = gpiod.Chip(CHIP)
line = chip.get_line(PIN)
line.request(consumer="Servo", type=gpiod.LINE_REQ_DIR_OUT)

def set_servo_angle(angle):
    duty_cycle = (angle / 18) + 2.5
    pulse_width = duty_cycle / 100 * 20000
    line.set_value(1)
    time.sleep(pulse_width / 1000000)
    line.set_value(0)
    time.sleep((20000 - pulse_width) / 1000000)

# duration秒間サーボを動かす
end_time = time.time() + duration
while time.time() < end_time:
    set_servo_angle(angle)
    time.sleep(0.02)

line.release()
chip.close()
