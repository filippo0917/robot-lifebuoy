// WASD receiver for Arduino Uno / Nano (ATmega328P).
// Same serial protocol as the ESP32 version, so head_follow.py works unchanged:
//   w/a/s/d = drive, x or space = stop, 1/2/3 = power low/mid/high, 9600 baud.
#include <Servo.h>

// ---- ESC pins ----
// Pins 9 and 10 work well on the Uno/Nano. Don't use pins 0 and 1: they're the
// USB serial lines, so the ESC signal and the laptop's commands would collide.
// Note: the Servo library disables analogWrite() (PWM) on pins 9 and 10.
const int ESC1_PIN = 9;
const int ESC2_PIN = 10;

const int NEUTRAL = 1500;   // ESC "stop" pulse (µs)

Servo esc1;
Servo esc2;

int power = 300;            // offset from neutral: 300 / 400 / 500
char currentDir = 'x';      // last movement command, so power changes apply live

void setup() {
  Serial.begin(9600);       // must match BAUD in head_follow.py

  esc1.attach(ESC1_PIN, 1000, 2000);   // (pin, minPulse, maxPulse)
  esc2.attach(ESC2_PIN, 1000, 2000);
  stopMotors();
  delay(3000);              // let the ESCs arm at neutral

  Serial.println("Ready for operation");
}

void loop() {
  while (Serial.available() > 0) {
    char c = tolower(Serial.read());

    switch (c) {
      case 'w': currentDir = 'w'; Serial.println("FORWARD"); break;
      case 's': currentDir = 's'; Serial.println("BACK");    break;
      case 'a': currentDir = 'a'; Serial.println("LEFT");    break;
      case 'd': currentDir = 'd'; Serial.println("RIGHT");   break;
      case 'x':
      case ' ': currentDir = 'x'; Serial.println("STOP");    break;

      // Power levels: a char holds ONE character, so "300" can't be sent
      // as one byte. Use keys 1/2/3 instead.
      case '1': power = 300; Serial.println("LOW POWER (300)");  break;
      case '2': power = 400; Serial.println("MID POWER (400)");  break;
      case '3': power = 500; Serial.println("HIGH POWER (500)"); break;

      default: continue;    // ignore newlines and anything else
    }

    drive(currentDir);      // apply direction at the current power
  }
}

void drive(char dir) {
  switch (dir) {
    case 'w': setMotors(NEUTRAL + power, NEUTRAL + power); break;
    case 's': setMotors(NEUTRAL - power, NEUTRAL - power); break;
    case 'a': setMotors(NEUTRAL - power, NEUTRAL + power); break;
    case 'd': setMotors(NEUTRAL + power, NEUTRAL - power); break;
    default:  stopMotors(); break;
  }
}

void setMotors(int m1, int m2) {
  esc1.writeMicroseconds(m1);
  esc2.writeMicroseconds(m2);
}

void stopMotors() {
  setMotors(NEUTRAL, NEUTRAL);
}
