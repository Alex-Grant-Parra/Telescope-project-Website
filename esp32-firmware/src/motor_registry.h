#ifndef MOTOR_REGISTRY_H
#define MOTOR_REGISTRY_H

#include <Arduino.h>
#include "motor.h"

struct MotorEntry {
  String id;
  Motor* motor;
  bool owned;
};

constexpr size_t kMaxMotors = 8;
extern MotorEntry g_motors[kMaxMotors];

Motor* findMotor(const String& id);
bool registerMotor(const String& id, Motor* motor, bool owned);

#endif // MOTOR_REGISTRY_H
