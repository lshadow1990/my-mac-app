#!/usr/bin/env python3
"""
会话数测试工具 - 极简版
"""

import sys
import socket
import threading
import time

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QLabel, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QPainter, QColor, QPen


class WorkerSignals(QObject):
    update_peak = pyqtSignal(int)
    update_speed = pyqtSignal(float)
    test_finished = pyqtSignal(int)
    test_started = pyqtSignal()
    test_stopped = pyqtSignal()


class SessionTester:
    def __init__(self):
        self.stop_flag = False
        self.connections = []
        self.lock = threading.Lock()
        self.current_count = 0
        self.max_count = 0
        self.connection_history = []
        self.last_success = 0
        self.stable_count = 0
        self.target_ip = "baidu.com"
        self.target_port = 80
        
    def run_test(self, signals):
        signals.test_started.emit()
        
        batch_size = 200
        consecutive_failures = 0
        round_num = 0
        
        while not self.stop_flag and round_num < 30:
            round_num += 1
            start_time = time.time()
            success = self.batch_connect(batch_size)
            elapsed = time.time() - start_time
            
            if success > 0:
                speed = success / elapsed if elapsed > 0 else 0
                signals.update_speed.emit(speed)
                consecutive_failures = 0
            else:
                consecutive_failures += 1
            
            signals.update_peak.emit(self.max_count)
            
            success_rate = success / batch_size if batch_size > 0 else 0
            if self.check_peak(success_rate, success) or consecutive_failures >= 2:
                break
            
            if success_rate < 0.2 and batch_size > 50:
                batch_size = max(50, batch_size // 2)
            
            time.sleep(0.05)
        
        signals.test_finished.emit(self.max_count)
        self.stop_flag = False
    
    def batch_connect(self, count):
        if self.stop_flag:
            return 0
        
        sockets = []
        for i in range(min(count, 300)):
            if self.stop_flag:
                break
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.3)
                sockets.append(sock)
            except:
                pass
        
        if not sockets:
            return 0
        
        results = []
        lock = threading.Lock()
        
        def worker(sock):
            try:
                sock.connect((self.target_ip, self.target_port))
                with lock:
                    results.append(sock)
            except:
                try:
                    sock.close()
                except:
                    pass
        
        threads = [threading.Thread(target=worker, args=(s,)) for s in sockets]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=0.5)
        
        with self.lock:
            for sock in results:
                self.connections.append(sock)
                self.current_count = len(self.connections)
            if self.current_count > self.max_count:
                self.max_count = self.current_count
        
        return len(results)
    
    def check_peak(self, success_rate, success_count):
        if success_rate < 0.05 and success_count < 10 and self.current_count > 50:
            return True
        
        self.connection_history.append(success_rate)
        if len(self.connection_history) > 3:
            self.connection_history.pop(0)
        
        if len(self.connection_history) == 3:
            if sum(self.connection_history) / 3 < 0.1 and self.current_count > 100:
                return True
        
        if success_count <= self.last_success and success_count < 3 and self.current_count > 100:
            self.stable_count += 1
            if self.stable_count >= 2:
                return True
        else:
            self.stable_count = 0
        
        self.last_success = success_count
        return False
    
    def clear(self):
        with self.lock:
            for sock in self.connections:
                try:
                    sock.close()
                except:
                    pass
            self.connections.clear()
            self.current_count = 0
    
    def stop(self):
        self.stop_flag = True
        self.clear()


class CircleButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self.setCursor(Qt.PointingHandCursor)
        self.running = False
        
    def set_running(self, running):
        self.running = running
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        r = 56
        
        cx = w // 2
        cy = h // 2
        
        if self.running:
            color = QColor(239, 68, 68)
        else:
            color = QColor(0, 0, 0)
        
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(QColor(255, 255, 255, 0))
        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        
        if self.running:
            painter.setPen(QPen(color, 1.5))
            s = 16
            painter.drawRect(cx - s, cy - s, s * 2, s * 2)
        else:
            painter.setPen(QPen(color, 1.5))
            s = 14
            pts = [
                (cx - s//2, cy - s),
                (cx - s//2, cy + s),
                (cx + s, cy)
            ]
            for i in range(3):
                x1, y1 = pts[i]
                x2, y2 = pts[(i+1)%3]
                painter.drawLine(x1, y1, x2, y2)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("会话数测试")
        self.setFixedSize(300, 480)
        self.setStyleSheet("background-color: #ffffff;")
        
        self.tester = SessionTester()
        self.signals = WorkerSignals()
        self.is_testing = False
        self.test_thread = None
        
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 50, 40, 30)
        layout.setSpacing(16)
        
        # 峰值数字
        self.peak_label = QLabel("0")
        self.peak_label.setAlignment(Qt.AlignCenter)
        self.peak_label.setStyleSheet("""
            font-size: 96px;
            font-weight: 200;
            color: #000000;
            font-family: "Helvetica Neue";
        """)
        layout.addWidget(self.peak_label)
        
        # 标签
        label = QLabel("峰值连接数")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("""
            font-size: 12px;
            font-weight: 400;
            color: #999999;
            margin-top: -8px;
        """)
        layout.addWidget(label)
        
        # 速率
        self.speed_label = QLabel("")
        self.speed_label.setAlignment(Qt.AlignCenter)
        self.speed_label.setStyleSheet("""
            font-size: 13px;
            color: #999999;
            font-weight: 400;
            min-height: 20px;
        """)
        layout.addWidget(self.speed_label)
        
        layout.addSpacing(10)
        
        # 圆形按钮
        self.btn = CircleButton()
        self.btn.clicked.connect(self.toggle)
        layout.addWidget(self.btn, alignment=Qt.AlignCenter)
        
        layout.addStretch()
        
        # 底部状态
        self.status_label = QLabel("ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            font-size: 10px;
            color: #cccccc;
        """)
        layout.addWidget(self.status_label)
    
    def connect_signals(self):
        self.signals.update_peak.connect(self.update_peak)
        self.signals.update_speed.connect(self.update_speed)
        self.signals.test_finished.connect(self.on_finished)
        self.signals.test_started.connect(self.on_started)
        self.signals.test_stopped.connect(self.on_stopped)
    
    def toggle(self):
        if self.is_testing:
            self.stop()
        else:
            self.start()
    
    def start(self):
        self.is_testing = True
        self.btn.set_running(True)
        self.peak_label.setText("0")
        self.speed_label.setText("")
        self.status_label.setText("testing...")
        
        self.tester.max_count = 0
        self.tester.current_count = 0
        self.tester.clear()
        self.tester.stop_flag = False
        
        self.test_thread = threading.Thread(target=self.tester.run_test, args=(self.signals,))
        self.test_thread.daemon = True
        self.test_thread.start()
    
    def stop(self):
        self.tester.stop()
        self.status_label.setText("stopping...")
    
    def update_peak(self, value):
        self.peak_label.setText(str(value))
    
    def update_speed(self, speed):
        self.speed_label.setText(f"{speed:.0f} 连接/秒")
    
    def on_started(self):
        pass
    
    def on_finished(self, max_count):
        self.is_testing = False
        self.btn.set_running(False)
        self.status_label.setText(f"完成 · 峰值 {max_count}")
        self.speed_label.setText("")
    
    def on_stopped(self):
        self.is_testing = False
        self.btn.set_running(False)
        self.status_label.setText("已停止")
        self.speed_label.setText("")


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Helvetica Neue", 12))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()