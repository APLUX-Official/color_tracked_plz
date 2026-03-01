/*
 * @Author: WALT
 * @Date: 2026-02-09 19:36:03
 */
// SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
// SPDX-License-Identifier: MPL-2.0

#include "Arduino_RouterBridge.h"

const int PIN_PAN = D3;   // Pan
const int PIN_TILT = D11; // Tilt

// 全局变量存脉宽 (默认中位 1500us)
volatile int pulse_pan = 1500;
volatile int pulse_tilt = 1500;

void setup() {
    pinMode(PIN_PAN, OUTPUT);
    pinMode(PIN_TILT, OUTPUT);

    Bridge.begin();
    // 注册两个函数供 Python 调用
    Bridge.provide("set_pan", update_pan);
    Bridge.provide("set_tilt", update_tilt);
}

void loop() {
    // === 手动生成双路 PWM (50Hz) ===
    
    // 1. Pan 脉冲
    digitalWrite(PIN_PAN, HIGH);
    delayMicroseconds(pulse_pan);
    digitalWrite(PIN_PAN, LOW);
    
    // 2. Tilt 脉冲
    digitalWrite(PIN_TILT, HIGH);
    delayMicroseconds(pulse_tilt);
    digitalWrite(PIN_TILT, LOW);
    
    // 3. 补足剩余时间
    int used_time = pulse_pan + pulse_tilt;
    if(20000 - used_time > 0) {
        delayMicroseconds(20000 - used_time);
    }
}

// 角度转脉宽辅助函数
int angle_to_pulse(int angle) {
    if (angle < 0) angle = 0;
    if (angle > 180) angle = 180;
    return 500 + (angle * 2000 / 180);
}

// Python 调用的函数
void update_pan(int angle) {
    pulse_pan = angle_to_pulse(angle);
}

void update_tilt(int angle) {
    pulse_tilt = angle_to_pulse(angle);
}