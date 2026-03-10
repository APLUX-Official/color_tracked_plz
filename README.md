# 🎯 Color Tracked PTZ (Pan-Tilt-Zoom)

HSV color tracking PTZ based on **Arduino UNO Q**. OpenCV identifies the target color → PID closed-loop control algorithm calculates the error → MG996R servos follow in real time, with a cyberpunk-style Web console provided.

## ✨ Functional Features

| Feature                       | Description                                                  |
| ----------------------------- | ------------------------------------------------------------ |
| 🎨 Dynamic Color Selection     | Hue slider + 6 color presets (Yellow/Red/Green/Blue/Orange/Purple) for real-time switching of the tracked color |
| 🤖 PID Automatic Tracking      | Dual-axis independent PID closed-loop control, including deadband hysteresis, integral Anti-Windup, and EMA coordinate filtering |
| 📊 PID Online Parameter Tuning | Four-parameter sliders (Kp/Ki/Kd/deadband) + 4 preset schemes (Default/Pure P/Conservative/Aggressive), taking effect in real time |
| 🕹️ Manual Control              | Direct control via sliders for Pan (0-180°) / Tilt (30-150°) |
| 🔧 Servo Neutral Calibration   | Fine adjustment (±1°/±5°) + one-click return to 90° neutral position, facilitating rocker arm installation |
| 📹 Real-Time Video             | Base64 JPEG streaming (~25fps) with tracking markers displayed directly in the browser |

## 🔌 Hardware Connection

| Component           | Pin  | Description                   |
| ------------------- | ---- | ----------------------------- |
| Pan Servo (MG996R)  | D3   | Horizontal rotation (0°-180°) |
| Tilt Servo (MG996R) | D11  | Vertical tilt (30°-150°)      |
| USB Camera          | USB  | 320×240 MJPG                  |

## 📁 Project Structure

```
color_tracked_plz/
├── app.yaml           # Arduino App Configuration
├── assets/
│   └── index.html     # Single-file Web Console (CSS + HTML + JS, ~930 lines)
├── python/
│   └── main.py        # OpenCV Vision + PID Control + WebUI Service (~270 lines)
└── sketch/
    ├── sketch.ino     # Manual 50Hz PWM Servo Driver (~65 lines)
    └── sketch.yaml    # Sketch Configuration (Arduino Zephyr UNO Q)
```

## 🧠 Core Algorithms

### PID Closed-Loop Control

Dual-axis independent PID controllers convert pixel errors into servo angle correction values:

$$u(k) = K_p \cdot e(k) + K_i \cdot \sum_{j=0}^{k} e(j) + K_d \cdot [e(k) - e(k-1)]$$

- **Proportional Term (P)**: Larger error leads to greater correction, providing fast response
- **Integral Term (I)**: Accumulates historical errors to eliminate steady-state deviation, with Anti-Windup limiting (±500)
- **Derivative Term (D)**: Detects the rate of error change to suppress overshoot and oscillation
- **Deadband Hysteresis**: No action when error < 20px; reactivation requires error exceeding 26px to avoid edge jitter
- **EMA Low-Pass Filter**: Exponential Moving Average (α=0.4) on detected coordinates to smooth inter-frame noise

### Color Threshold Segmentation

Color segmentation and centroid calculation based on the HSV color space:

```
BGR → HSV Conversion → inRange Threshold Segmentation → Erosion/Dilation Denoising
→ findContours Contour Extraction → Largest Contour → minEnclosingCircle Centroid Localization
```

Red color automatically handles hue wrapping (merged dual masks for H≈170°~10°).

### Manual PWM Servo Driving

Instead of using the Servo library, 50Hz pulses are generated manually in `loop()`:

```
Angle → Pulse Width: pulse = 500 + (angle × 2000 / 180) μs
0° → 500μs | 90° → 1500μs | 180° → 2500μs
```

## 🚀 Usage Instructions

1. **Upload Sketch** — Compile and upload the `sketch/` directory to UNO Q
2. **Start App** — Run the project in Arduino App Lab
3. **Open Console** — Access `http://<UNO_Q_IP>:7000` in a browser
4. **Select Color** — Choose the color to track using the Hue slider or preset color blocks
5. **Enable Tracking** — Toggle the "Auto Tracking" switch to make the PTZ follow the target automatically

### 🔧 Servo Calibration

Use this when assembling for the first time or replacing the rocker arm:

1. Click **"Start Calibration"** → Both axes automatically return to the 90° neutral position
2. Use the **±1 / ±5** buttons to fine-tune to the servo's physical neutral position
3. Install the servo rocker arm at the current angle
4. Click **"Finish Calibration"** to exit

> During calibration, auto tracking is forcibly disabled to ensure manual fine-tuning is not interfered with.

### 🎯 PID Tuning Guide

| Phenomenon                         | Adjustment Suggestion      |
| ---------------------------------- | -------------------------- |
| Too slow response                  | Increase Kp                |
| Jitter/Oscillation                 | Increase Kd or decrease Kp |
| Target centered but with deviation | Increase Ki                |
| Jitter near the center             | Increase deadband          |

Quick reference for four preset schemes:

| Preset       | Kp    | Ki     | Kd    | Deadband | Application Scenario                    |
| ------------ | ----- | ------ | ----- | -------- | --------------------------------------- |
| Default      | 0.035 | 0.0005 | 0.025 | 20       | General balance                         |
| Pure P       | 0.08  | 0      | 0     | 10       | Fast response with steady-state error   |
| Conservative | 0.02  | 0.002  | 0.03  | 25       | Stable tracking                         |
| Aggressive   | 0.06  | 0.003  | 0.04  | 10       | Sensitive tracking (possible overshoot) |

## 🛠️ Technology Stack

- **Arduino Firmware**: Manual 50Hz PWM + RouterBridge remote call
- **Python Middleware**: OpenCV HSV color recognition + PID closed-loop control + EMA coordinate filtering + Base64 streaming
- **Web Frontend**: Single-file HTML (cyberpunk style), Socket.IO bidirectional communication
- **Communication Protocol**: RouterBridge (Python ↔ Arduino), Socket.IO (Browser ↔ Python)

<!--
 * @Author: WALT
 * @Date: 2026-02-09 19:36:03
-->

# 🎯 颜色追踪云台 (Color Tracked PTZ)

基于 **Arduino UNO Q** 的 HSV 颜色追踪云台。OpenCV 识别目标颜色 → PID 闭环控制算法计算误差 → MG996R 舵机实时跟随，同时提供赛博朋克风格 Web 控制台。

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 🎨 动态选色 | Hue 滑条 + 6 色预设（黄/红/绿/蓝/橙/紫），实时切换追踪颜色 |
| 🤖 PID 自动追踪 | 双轴独立 PID 闭环控制，含死区迟滞、积分 Anti-Windup、EMA 坐标滤波 |
| 📊 PID 在线调参 | Kp/Ki/Kd/死区四参数滑块 + 4 种预设方案（默认/纯P/保守/激进），实时生效 |
| 🕹️ 手动控制 | Pan 0-180° / Tilt 30-150° 滑块直控 |
| 🔧 舵机中位校准 | ±1°/±5° 微调 + 一键回中 90°，方便安装摇臂 |
| 📹 实时视频 | Base64 JPEG 推流（~25fps），浏览器直接显示追踪标记 |

## 🔌 硬件连接

| 组件 | 引脚 | 说明 |
|------|------|------|
| Pan 舵机 (MG996R) | D3 | 水平旋转 0°-180° |
| Tilt 舵机 (MG996R) | D11 | 垂直俯仰 30°-150° |
| USB 摄像头 | USB | 320×240 MJPG |

## 📁 项目结构

```
color_tracked_plz/
├── app.yaml           # Arduino App 配置
├── assets/
│   └── index.html     # 单文件 Web 控制台 (CSS + HTML + JS, ~930行)
├── python/
│   └── main.py        # OpenCV 视觉 + PID 控制 + WebUI 服务 (~270行)
└── sketch/
    ├── sketch.ino     # 手动 50Hz PWM 舵机驱动 (~65行)
    └── sketch.yaml    # Sketch 配置 (Arduino Zephyr UNO Q)
```

## 🧠 核心算法

### PID 闭环控制

双轴独立 PID 控制器，将像素误差转换为舵机角度修正量：

$$u(k) = K_p \cdot e(k) + K_i \cdot \sum_{j=0}^{k} e(j) + K_d \cdot [e(k) - e(k-1)]$$

- **比例项 (P)**：误差越大修正越大，提供快速响应
- **积分项 (I)**：累积历史误差，消除稳态偏差，含 Anti-Windup 限幅 (±500)
- **微分项 (D)**：感知误差变化速率，抑制超调震荡
- **死区迟滞**：误差 < 20px 时不动作，需超过 26px 才重新激活，避免边缘抖动
- **EMA 低通滤波**：对检测坐标做指数移动平均（α=0.4），平滑帧间噪声

### 颜色阈值分割

基于 HSV 色彩空间的颜色分割与质心计算：

```
BGR → HSV 转换 → inRange 阈值分割 → 腐蚀/膨胀去噪
→ findContours 轮廓提取 → 最大轮廓 → minEnclosingCircle 质心定位
```

红色自动处理色相环绕（H≈170°~10°双 mask 合并）。

### 手动 PWM 舵机驱动

不使用 Servo 库，`loop()` 中手动生成 50Hz 脉冲：

```
角度 → 脉宽: pulse = 500 + (angle × 2000 / 180) μs
0° → 500μs | 90° → 1500μs | 180° → 2500μs
```

## 🚀 使用方法

1. **上传 Sketch** — 将 `sketch/` 编译上传到 UNO Q
2. **启动 App** — 在 Arduino App Lab 中运行本项目
3. **打开控制台** — 浏览器访问 `http://<UNO_Q_IP>:7000`
4. **选择颜色** — 用 Hue 滑条或预设色块选择要追踪的颜色
5. **开启追踪** — 打开 "自动追踪" 开关，云台自动跟随目标

### 🔧 舵机校准

首次组装或更换摇臂时使用：

1. 点击 **"开始校准"** → 两轴自动回中 90°
2. 用 **±1 / ±5** 按钮微调至舵机物理中位
3. 在当前角度安装舵机摇臂
4. 点击 **"完成校准"** 退出

> 校准时自动追踪会被强制关闭，确保手动微调不受干扰。

### 🎯 PID 调参指南

| 现象 | 调整建议 |
|------|----------|
| 响应太慢 | 增大 Kp |
| 抖动/震荡 | 增大 Kd 或减小 Kp |
| 目标居中但有偏差 | 增大 Ki |
| 中心附近抖动 | 增大死区 |

四种预设方案速查：

| 预设 | Kp | Ki | Kd | 死区 | 适用场景 |
|------|-----|------|------|------|----------|
| 默认 | 0.035 | 0.0005 | 0.025 | 20 | 通用平衡 |
| 纯P | 0.08 | 0 | 0 | 10 | 快速响应，有稳态误差 |
| 保守 | 0.02 | 0.002 | 0.03 | 25 | 平稳追踪 |
| 激进 | 0.06 | 0.003 | 0.04 | 10 | 灵敏追踪，可能超调 |

## 🛠️ 技术栈

- **Arduino 固件**：手动 50Hz PWM + RouterBridge 远程调用
- **Python 中台**：OpenCV HSV 颜色识别 + PID 闭环控制 + EMA 坐标滤波 + Base64 推流
- **Web 前端**：单文件 HTML（赛博朋克风），Socket.IO 双向通信
- **通信协议**：RouterBridge（Python ↔ Arduino），Socket.IO（浏览器 ↔ Python）
