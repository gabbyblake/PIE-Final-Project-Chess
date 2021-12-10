#include <Adafruit_MotorShield.h>

#define BUFFER_LEN 128
#define NUM_ANALOG 6
#define NUM_MOTORS 4
#define NUM_STEPPERS 2
#define STEPS_PER_REV 200

int ANALOG_PINS[NUM_ANALOG] = {A0, A1, A2, A3, A4, A5};
Adafruit_DCMotor* MOTORS[NUM_MOTORS];
Adafruit_StepperMotor* STEPPERS[NUM_STEPPERS];
int stepperModes[NUM_STEPPERS] = {SINGLE, SINGLE};
const Adafruit_MotorShield motorShield = Adafruit_MotorShield();

char commandBuffer[BUFFER_LEN];
int bufferPos = 0;

enum PinType {
  DIGITAL,
  ANALOG,
  MOTOR,
  STEPPER
};

void writeToPin(PinType type, int pin, int value) {
  if (type == DIGITAL) {
    digitalWrite(pin, value);
  } else if (type == ANALOG) {
    analogWrite(ANALOG_PINS[pin], value);
  } else if (type == MOTOR) {
    MOTORS[pin]->setSpeed(value);
  } else if (type == STEPPER) {
    STEPPERS[pin]->step(abs(value), value > 0 ? FORWARD : BACKWARD, stepperModes[pin]);
  }
  Serial.print("Writing to pin ");
  Serial.print(type);
  Serial.print(pin);
  Serial.print(" value ");
  Serial.println(value);
}

void setMode(PinType type, int pin, int mode) {
  if (type == DIGITAL) {
    pinMode(pin, mode);
  } else if (type == ANALOG) {
    pinMode(ANALOG_PINS[pin], mode);
  } else if (type == MOTOR) {
    MOTORS[pin]->run(mode);
  } else if (type == STEPPER) {
    stepperModes[pin] = mode;
  }
}

int readValue(PinType type, int pin) {
  int value = -1;
  if (type == DIGITAL) {
    value = analogRead(pin);
  } else if (type == ANALOG) {
    value = analogRead(ANALOG_PINS[pin]);
  }
  return value;
}

int parseNum(int startPos, int base) {
  int value = 0;
  for (int pos = startPos; pos < BUFFER_LEN && commandBuffer[pos] != '\r'; pos++) {
    value *= base;
    value += commandBuffer[pos] <= '9' ? (commandBuffer[pos] - '0') : (commandBuffer[pos] - 'a' + 10);
  }
  return value;
}

void processCommand() {
  // Find pin
  PinType type = DIGITAL;
  if (commandBuffer[0] == 'A') {
    type = ANALOG;
  }
  else if (commandBuffer[0] == 'M') {
    type = MOTOR;
  }
  else if (commandBuffer[0] == 'S') {
    type = STEPPER;
  }
  int pin = (int)(commandBuffer[1] - '0');
  if (commandBuffer[0] == '1') {
    pin += 10;
  }

  // Set value
  if (commandBuffer[2] == ':') {
    int value = 0;
    if (commandBuffer[3] == 'H') {
      value = HIGH;
    }
    else if (commandBuffer[3] == 'L') {
      value == LOW;
    }
    else {
      int sign = commandBuffer[3] == '-' ? -1 : 1;
      value = parseNum(sign == 1 ? 3 : 4, 16) * sign;
    }
    writeToPin(type, pin, value);
  }

  // Set mode
  if (commandBuffer[2] == '-') {
    if (commandBuffer[3] == 'I') {
      setMode(type, pin, INPUT);
    } else if (commandBuffer[3] == 'O') {
      setMode(type, pin, OUTPUT);
    } else if (commandBuffer[3] == 'S') {
      setMode(type, pin, BRAKE);
    } else if (commandBuffer[3] == 'R') {
      setMode(type, pin, RELEASE);
    } else if (commandBuffer[3] == 'F') {
      setMode(type, pin, FORWARD);
    } else if (commandBuffer[3] == 'B') {
      setMode(type, pin, BACKWARD);
    } else if (commandBuffer[3] >= '0' && commandBuffer[3] <= '9') {
      setMode(type, pin, parseNum(3, 10));
    }
  }

  // Read value
  if (commandBuffer[2] == '?') {
    int value = readValue(type, pin);
    Serial.println(value);
  }
}

void setup() {
  Serial.begin(115200);
  
  if (!motorShield.begin()) {
    Serial.println("Motor Shield not found. Check wiring.");
    while (true) {}
  }
  
  // Initialize motors
  for (int i = 0; i < NUM_MOTORS; i++) {
    MOTORS[i] = motorShield.getMotor(i + 1);
    MOTORS[i]->run(BRAKE);
  }

  // Initialize motors
  for (int i = 0; i < NUM_STEPPERS; i++) {
    STEPPERS[i] = motorShield.getStepper(STEPS_PER_REV, i + 1);
    STEPPERS[i]->setSpeed(255);
  }
  
  Serial.println("Setup done.");
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();

    if (c == '\r') {
      // End of command
      commandBuffer[bufferPos] = c;
      processCommand();
      bufferPos = 0;
    }
    else if (bufferPos == BUFFER_LEN - 1) {
      // Should not reach here, but in case command is too long, reset
      bufferPos = 0;
    }
    else {
      // Add current character to command buffer
      commandBuffer[bufferPos] = c;
      bufferPos++;
    }
  }
}