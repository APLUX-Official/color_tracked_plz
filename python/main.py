# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

import io
import base64
import time
import cv2
import numpy as np
from arduino.app_utils import App, Bridge
from arduino.app_bricks.web_ui import WebUI

ui = WebUI()

# === ⚙️ 全局配置 ===
current_pan = 90.0   # 保持 float，避免 int 截断引起跳变
current_tilt = 90.0
prev_sent_pan = -1   # 上次实际发送的角度 (int)，用于去重
prev_sent_tilt = -1
is_auto_mode = False

# 🔹 EMA 低通滤波器 (平滑检测坐标的帧间噪声)
ema_alpha = 0.4   # 平滑系数: 越小越平滑但延迟越大，0.4 是较好的平衡点
ema_x = None      # 首次检测时初始化
ema_y = None

# 🎯 PID 控制器类
class PIDController:
    """PID 闭环控制器 (Pan/Tilt 云台追踪)"""
    def __init__(self, kp=0.035, ki=0.001, kd=0.02, dead_zone=15):
        self.Kp = kp           # 比例增益
        self.Ki = ki           # 积分增益
        self.Kd = kd           # 微分增益
        self.dead_zone = dead_zone  # 死区 (px)
        self.integral = 0.0    # 误差累积
        self.prev_error = 0.0  # 上一次误差
        self.integral_limit = 500.0  # 积分限幅 (防止 windup)
    
    def compute(self, error):
        """PID 计算: 输入像素误差, 输出舵机角度变化量"""
        # 死区: 带迟滞设计，避免边缘反复进出
        # 进入死区后需要误差超过 dead_zone*1.2 才重新激活
        if abs(error) < self.dead_zone:
            self.integral *= 0.8  # 死区内积分衰减
            self.prev_error = error
            self._in_dead_zone = True
            return 0.0
        
        if getattr(self, '_in_dead_zone', False) and abs(error) < self.dead_zone * 1.3:
            # 迟滞区间：还没超过激活阈值，继续保持静止
            self.integral *= 0.9
            self.prev_error = error
            return 0.0
        self._in_dead_zone = False
        
        # P — 比例项: 误差越大, 输出越大
        p_out = self.Kp * error
        
        # I — 积分项: 误差累积, 消除稳态误差
        self.integral += error
        self.integral = max(-self.integral_limit, min(self.integral_limit, self.integral))  # Anti-windup
        i_out = self.Ki * self.integral
        
        # D — 微分项: 误差变化率, 抑制超调
        d_out = self.Kd * (error - self.prev_error)
        self.prev_error = error
        
        output = p_out + i_out + d_out
        
        # 输出死区：PID 输出太小时不动作，防止亚度级微抖
        if abs(output) < 0.3:
            return 0.0
        
        return output
    
    def reset(self):
        """重置积分和微分状态"""
        self.integral = 0.0
        self.prev_error = 0.0

# 初始化双轴 PID (调优后参数: 降低 Ki 减少积分振荡, 增大 Kd 抑制超调, 稍大死区)
pid_pan  = PIDController(kp=0.035, ki=0.0005, kd=0.025, dead_zone=20)
pid_tilt = PIDController(kp=0.035, ki=0.0005, kd=0.025, dead_zone=20)

# 🎨 HSV 颜色范围 (默认黄色)
hsv_lower = [20, 80, 80]
hsv_upper = [40, 255, 255]

# 📷 掉线检测参数 (新加)
MAX_FAIL_COUNT = 60  # 连续失败多少次才算掉线 (30帧约1秒)
fail_counter = 0     # 失败计数器

# === 📡 Web 消息回调 ===
def on_control_pan(sid, data):
    global current_pan, prev_sent_pan
    if not is_auto_mode:
        try:
            current_pan = float(int(data))
            pan_int = int(current_pan)
            Bridge.call("set_pan", pan_int)
            prev_sent_pan = pan_int
        except: pass

def on_control_tilt(sid, data):
    global current_tilt, prev_sent_tilt
    if not is_auto_mode:
        try:
            current_tilt = float(int(data))
            tilt_int = int(current_tilt)
            Bridge.call("set_tilt", tilt_int)
            prev_sent_tilt = tilt_int
        except: pass

def on_toggle_mode(sid, data):
    global is_auto_mode
    if str(data).lower() == 'true':
        is_auto_mode = True
        print("🟢 自动追踪模式: 开启", flush=True)
    else:
        is_auto_mode = False
        print("⚪ 手动模式: 开启", flush=True)

def on_set_color(sid, data):
    global hsv_lower, hsv_upper
    try:
        keys = ['h_low', 's_low', 'v_low', 'h_high', 's_high', 'v_high']
        # 校验：所有字段必须存在且非 None
        for k in keys:
            if data.get(k) is None:
                print(f"⚠️ set_color 数据不完整，缺少 {k}，原始数据: {data}", flush=True)
                return
        hsv_lower = [int(data['h_low']), int(data['s_low']), int(data['v_low'])]
        hsv_upper = [int(data['h_high']), int(data['s_high']), int(data['v_high'])]
        print(f"🎨 颜色已更新: HSV {hsv_lower} ~ {hsv_upper}", flush=True)
    except Exception as e:
        print(f"颜色设置错误: {e}, 原始数据: {data}", flush=True)

def on_set_pid(sid, data):
    """Web 端动态调节 PID 参数"""
    global pid_pan, pid_tilt
    try:
        kp = float(data.get('kp', pid_pan.Kp))
        ki = float(data.get('ki', pid_pan.Ki))
        kd = float(data.get('kd', pid_pan.Kd))
        dz = float(data.get('dead_zone', pid_pan.dead_zone))
        # 双轴使用相同参数
        pid_pan.Kp = kp;  pid_pan.Ki = ki;  pid_pan.Kd = kd;  pid_pan.dead_zone = dz
        pid_tilt.Kp = kp; pid_tilt.Ki = ki; pid_tilt.Kd = kd; pid_tilt.dead_zone = dz
        # 重置积分/微分状态, 避免参数切换时旧积分造成跳变
        pid_pan.reset()
        pid_tilt.reset()
        print(f"🎯 PID 已更新: Kp={kp} Ki={ki} Kd={kd} DeadZone={dz}", flush=True)
    except Exception as e:
        print(f"PID 设置错误: {e}", flush=True)

ui.on_message('control_pan', on_control_pan)
ui.on_message('control_tilt', on_control_tilt)
ui.on_message('toggle_mode', on_toggle_mode)
ui.on_message('set_color', on_set_color)
ui.on_message('set_pid', on_set_pid)

def clamp(n, minn, maxn): return max(min(maxn, n), minn)

# === 🔍 找摄像头 ===
def find_camera():
    print("🔍 正在扫描摄像头 (V4L2)...", flush=True)
    for i in range(10): 
        try:
            # 强制 MJPG 以提高稳定性
            temp_cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            if temp_cap.isOpened():
                temp_cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
                temp_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                temp_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                
                # 预读 3 帧，确保画面稳定
                for _ in range(3): 
                    ret, _ = temp_cap.read()
                
                if ret:
                    print(f"✅ 在索引 {i} 找到摄像头！", flush=True)
                    return temp_cap
                else:
                    temp_cap.release()
        except: pass
    return None

# === 🚀 主循环 ===
def loop():
    global current_pan, current_tilt, fail_counter, prev_sent_pan, prev_sent_tilt, ema_x, ema_y
    
    cap = None 
    print("🚀 系统就绪: 请访问 http://<IP>:7000", flush=True)

    while True:
        # --- 阶段 1: 连接设备 ---
        if cap is None:
            cap = find_camera()
            if cap is None:
                time.sleep(1) 
                continue
            fail_counter = 0 # 连接成功，重置计数器

        # --- 阶段 2: 读取画面 ---
        ret = False
        frame = None
        try:
            ret, frame = cap.read()
        except:
            ret = False
        
        # --- 🔥🔥🔥 核心修复：掉线容忍逻辑 🔥🔥🔥 ---
        if not ret:
            fail_counter += 1
            # 只有连续失败超过阈值，才真的认为掉线
            if fail_counter > MAX_FAIL_COUNT:
                print(f"⚠️ 严重错误：连续 {MAX_FAIL_COUNT} 次读取失败，正在重置摄像头...", flush=True)
                try: cap.release()
                except: pass
                cap = None
                fail_counter = 0
            else:
                # 只是偶尔丢帧，不要断开，睡一会重试
                # print(f"⚠️ 丢帧 ({fail_counter}/{MAX_FAIL_COUNT})", flush=True) 
                time.sleep(0.01)
            
            continue # 跳过本次循环
        else:
            # 读取成功，立即重置计数器 (只要成功一次，危机解除)
            fail_counter = 0

        # === 🖼️ 图像处理 ===
        height, width, _ = frame.shape
        center_x, center_y = width // 2, height // 2

        if is_auto_mode:
            try:
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                lower_bound = np.array(hsv_lower)
                upper_bound = np.array(hsv_upper)
                
                # 处理红色跨越 H=0 的情况
                if hsv_lower[0] > hsv_upper[0]:
                    mask1 = cv2.inRange(hsv, np.array([hsv_lower[0], hsv_lower[1], hsv_lower[2]]), np.array([180, hsv_upper[1], hsv_upper[2]]))
                    mask2 = cv2.inRange(hsv, np.array([0, hsv_lower[1], hsv_lower[2]]), np.array([hsv_upper[0], hsv_upper[1], hsv_upper[2]]))
                    mask = cv2.bitwise_or(mask1, mask2)
                else:
                    mask = cv2.inRange(hsv, lower_bound, upper_bound)
                mask = cv2.erode(mask, None, iterations=2)
                mask = cv2.dilate(mask, None, iterations=2)
                
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                target_found = False
                if len(contours) > 0:
                    c = max(contours, key=cv2.contourArea)
                    ((x, y), radius) = cv2.minEnclosingCircle(c)
                    
                    if radius > 10:
                        target_found = True
                        obj_x, obj_y = int(x), int(y)
                        cv2.circle(frame, (obj_x, obj_y), int(radius), (0, 255, 0), 2)
                        cv2.circle(frame, (obj_x, obj_y), 5, (0, 0, 255), -1)

                        # === 🔹 EMA 低通滤波: 平滑检测坐标 ===
                        if ema_x is None:
                            ema_x, ema_y = float(obj_x), float(obj_y)
                        else:
                            ema_x = ema_alpha * obj_x + (1 - ema_alpha) * ema_x
                            ema_y = ema_alpha * obj_y + (1 - ema_alpha) * ema_y

                        # === 🎯 PID 追踪控制 ===
                        # 使用滤波后的坐标计算误差
                        error_x = ema_x - center_x  # 正 = 目标在右
                        error_y = ema_y - center_y  # 正 = 目标在下
                        
                        # PID 计算: 误差→角度修正量
                        delta_pan  = pid_pan.compute(error_x)
                        delta_tilt = pid_tilt.compute(error_y)
                        
                        # 方向映射: X偏右→Pan减小, Y偏下→Tilt减小
                        current_pan  -= delta_pan
                        current_tilt -= delta_tilt

                        # 保持 float 精度，只在发送时转 int
                        current_pan  = clamp(current_pan, 0, 180)
                        current_tilt = clamp(current_tilt, 30, 150)

                        # 只有角度实际变化时才发送指令，避免重复脉冲引起微抖
                        pan_int  = int(current_pan)
                        tilt_int = int(current_tilt)
                        if pan_int != prev_sent_pan:
                            Bridge.call("set_pan", pan_int)
                            prev_sent_pan = pan_int
                        if tilt_int != prev_sent_tilt:
                            Bridge.call("set_tilt", tilt_int)
                            prev_sent_tilt = tilt_int
                        ui.send_message('update_sliders', {'pan': pan_int, 'tilt': tilt_int})
                
                # 目标丢失时重置滤波器和 PID 状态
                if not target_found:
                    ema_x = None
                    ema_y = None
                    pid_pan.reset()
                    pid_tilt.reset()
            except Exception as e:
                print(f"Tracking Error: {e}")

        # === 🎥 推流 ===
        cv2.line(frame, (center_x - 10, center_y), (center_x + 10, center_y), (200, 200, 200), 1)
        cv2.line(frame, (center_x, center_y - 10), (center_x, center_y + 10), (200, 200, 200), 1)

        try:
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            if ret:
                b64_frame = base64.b64encode(buffer).decode("utf-8")
                ui.send_message('frame', {'image': b64_frame})
        except: pass
        
        time.sleep(0.04)

App.run(user_loop=loop)