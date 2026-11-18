# Head-follow boat control (laptop webcam to Arduino or ESP32)

`head_follow.py` watches your head through the laptop webcam and sends drive commands over USB serial. A receiver sketch on the board turns those commands into ESC pulses for the lifebuoy's two thrusters.

| File | What it is |
|---|---|
| `head_follow.py` | Laptop script: face tracking plus manual WASD control |
| `wasd_receiver_uno/wasd_receiver_uno.ino` | Receiver for **Arduino Uno / Nano** (ESCs on pins 9 and 10) |
| `wasd_receiver_esp32/wasd_receiver_esp32.ino` | Receiver for **ESP32** (ESCs on GPIO 25 and 26) |

Both sketches use the same commands, so `head_follow.py` works with either board. The steps below are for the Uno. For the ESP32, see [ESP32 differences](#esp32-differences).

## What you need

- An Arduino Uno or Nano and a USB cable
- 2 bidirectional ESCs (neutral = 1500 µs) and 2 thrusters (for example ApisQueen U1)
- A motor battery with an inline fuse and a main power switch
- A laptop with Python 3 and a webcam, to run `head_follow.py`

## Wiring

```
Arduino pin 9  ──── LEFT  ESC signal wire
Arduino pin 10 ──── RIGHT ESC signal wire
Arduino GND    ──── both ESC ground wires (black/brown)   <- required
ESC red 5V wire ─── leave unconnected while the Uno is on USB

Motor battery ──[fuse]──[main switch]──┬── LEFT  ESC ── left thruster  (3 wires, any order)
                                       └── RIGHT ESC ── right thruster (3 wires, any order)
```

- Don't use pins 0 and 1, because they're the USB serial lines.
- The motor battery only connects to the ESCs. Never connect it to an Arduino pin.
- The Servo library turns off `analogWrite()` on pins 9 and 10, so don't use them for anything else.

## Upload the sketch

1. Open `wasd_receiver_uno/wasd_receiver_uno.ino` in the Arduino IDE. `Servo` is built in, so there's nothing to install.
2. Under **Tools → Board**, choose **Arduino Uno** (or Nano), then pick the port.
3. Click **Upload**.
4. Open the Serial Monitor at **9600** baud. After about 3 seconds, while the ESCs arm, you should see `Ready for operation`.

## Commands

Each command is one character sent at 9600 baud.

| Key | Action |
|---|---|
| `w` | Forward |
| `s` | Back |
| `a` | Turn left (left motor back, right motor forward) |
| `d` | Turn right |
| `x` or space | Stop |
| `1` / `2` / `3` | Power low / mid / high (±300 / ±400 / ±500 µs from neutral) |

A power change applies right away to the current direction. You can test by typing the keys into the Serial Monitor.

## First test (propellers off)

1. Take the propellers off the thrusters.
2. Power the Uno over USB, then switch on the motor battery. Wait for the ESCs to arm.
3. Send `1`, then `w`. Both motors should spin the "forward" way.
4. **If one motor spins backward,** switch off the battery and swap **any two** of that thruster's three motor wires. This reverses a brushless motor.
5. Send `a`. The boat should turn left: the left motor goes back and the right goes forward. **If left and right are mixed up,** swap the signal wires on pins 9 and 10.
6. Send `x` and check that both motors stop.

## Run head tracking

```
pip install pyserial opencv-python
python head_follow.py               # auto-detects the Arduino
python head_follow.py --port COM5   # or name the port
```

Close the Arduino Serial Monitor first, because only one program can use the port at a time. In the video window, **T** switches between tracking and manual mode, **W/A/S/D** drive in manual mode, **Space** stops, **1/2/3** set power, and **Q** quits (it sends stop first).

## ESP32 differences

- Install ESP32 board support and the **ESP32Servo** library in the Arduino IDE, then choose your ESP32 board.
- Wire the left ESC signal to **GPIO 25** and the right one to **GPIO 26**. Still share ground.
- Don't connect an ESC's red 5 V wire to the ESP32's 3.3 V pin.
- Everything else (baud rate, commands, first test) is the same.

## Troubleshooting

- **Motors don't move:** check the shared ground and that the ESCs armed (most beep). Check that the battery switch is on.
- **The Uno resets when the motors start:** the voltage is dropping. Keep the Uno on USB or a separate 5 V supply, and share only ground with the ESCs.
- **"Couldn't open port":** close the Serial Monitor.
- **Motors twitch at stop:** the ESC's neutral may not be exactly 1500 µs. Recalibrate the ESC, or change `NEUTRAL` in the sketch.
