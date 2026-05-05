#include "motor.h"

MotorEntry g_motors[kMaxMotors] = {};

Motor::Motor(int step, int dir, int en, uint32_t stepsPerRev)
    : stepPin(step), dirPin(dir), enPin(en), enabled(false), moving(false),
      stopRequested(false), position(0), stepsPerRevolution(stepsPerRev),
      stepDelayUs(1250), stepTaskHandle(nullptr) {
}

void Motor::initialize() {
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);
  pinMode(enPin, OUTPUT);
  digitalWrite(stepPin, LOW);
  digitalWrite(dirPin, LOW);
  digitalWrite(enPin, HIGH);  // Disabled by default
}

void Motor::cleanup() {
  if (stepTaskHandle != nullptr) {
    stopRequested = true;
    vTaskDelete(stepTaskHandle);
    stepTaskHandle = nullptr;
  }
  digitalWrite(enPin, HIGH);  // Disable driver
  digitalWrite(stepPin, LOW);
  digitalWrite(dirPin, LOW);
  moving = false;
}

void Motor::setSpeed(uint32_t delayUs) {
  stepDelayUs = delayUs;
}

void Motor::engage() {
  digitalWrite(enPin, LOW);  // Active low
  enabled = true;
}

void Motor::disengage() {
  digitalWrite(enPin, HIGH);  // Disable
  enabled = false;
}

bool Motor::isEnabled() const {
  return enabled;
}

bool Motor::isMoving() const {
  return moving;
}

uint32_t Motor::getStepDelayUs() const {
  return stepDelayUs;
}

uint32_t Motor::getStepsPerRevolution() const {
  return stepsPerRevolution;
}

int32_t Motor::getPosition() const {
  return position;
}

void Motor::resetPosition() {
  position = 0;
}

void Motor::stop() {
  if (!moving) {
    return;
  }
  stopRequested = true;
}

void Motor::turnDegrees(float degrees, bool forward) {
  if (!enabled) {
    return;
  }
  if (moving) {
    return;  // Already moving, ignore
  }

  stopRequested = false;
  moving = true;

  uint32_t stepsNeeded = (uint32_t)((degrees / 360.0) * stepsPerRevolution);
  digitalWrite(dirPin, forward ? HIGH : LOW);

  struct StepParams {
    Motor* motor;
    uint32_t stepsNeeded;
    bool forward;
  };

  StepParams* params = new StepParams{this, stepsNeeded, forward};

  xTaskCreatePinnedToCore(
    stepTask,
    "MotorStep",
    2048,
    params,
    1,
    &stepTaskHandle,
    1
  );
}

void Motor::startContinuous(bool forward) {
  if (!enabled) {
    return;
  }
  if (moving) {
    return;  // Already moving, ignore
  }

  stopRequested = false;
  moving = true;

  digitalWrite(dirPin, forward ? HIGH : LOW);

  struct StepParams {
    Motor* motor;
    bool forward;
  };

  StepParams* params = new StepParams{this, forward};

  xTaskCreatePinnedToCore(
    continuousStepTask,
    "MotorContinuous",
    2048,
    params,
    1,
    &stepTaskHandle,
    1
  );
}

void Motor::stepTask(void* pvParameters) {
  struct StepParams {
    Motor* motor;
    uint32_t stepsNeeded;
    bool forward;
  };

  StepParams* params = (StepParams*)pvParameters;
  Motor* motor = params->motor;
  uint32_t stepsNeeded = params->stepsNeeded;
  bool forward = params->forward;
  delete params;

  int32_t positionDelta = forward ? 1 : -1;

  for (uint32_t i = 0; i < stepsNeeded; i++) {
    if (motor->stopRequested) {
      break;
    }

    digitalWrite(motor->stepPin, HIGH);
    delayMicroseconds(PULSE_WIDTH_US);
    digitalWrite(motor->stepPin, LOW);
    delayMicroseconds(motor->stepDelayUs - PULSE_WIDTH_US);

    motor->position += positionDelta;
  }

  motor->moving = false;
  vTaskDelete(nullptr);
}

void Motor::continuousStepTask(void* pvParameters) {
  struct StepParams {
    Motor* motor;
    bool forward;
  };

  StepParams* params = (StepParams*)pvParameters;
  Motor* motor = params->motor;
  delete params;

  int32_t positionDelta = 1;

  while (!motor->stopRequested) {
    digitalWrite(motor->stepPin, HIGH);
    delayMicroseconds(PULSE_WIDTH_US);
    digitalWrite(motor->stepPin, LOW);
    delayMicroseconds(motor->stepDelayUs - PULSE_WIDTH_US);

    motor->position += positionDelta;
  }

  motor->moving = false;
  vTaskDelete(nullptr);
}

Motor* findMotor(const String& id) {
  for (size_t i = 0; i < kMaxMotors; i++) {
    if (g_motors[i].motor != nullptr && g_motors[i].id == id) {
      return g_motors[i].motor;
    }
  }
  return nullptr;
}

bool registerMotor(const String& id, Motor* motor, bool owned) {
  if (id.length() == 0 || motor == nullptr) {
    return false;
  }
  if (findMotor(id) != nullptr) {
    return false;
  }
  for (size_t i = 0; i < kMaxMotors; i++) {
    if (g_motors[i].motor == nullptr) {
      g_motors[i].id = id;
      g_motors[i].motor = motor;
      g_motors[i].owned = owned;
      return true;
    }
  }
  return false;
}
