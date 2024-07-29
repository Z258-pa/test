import sys
import cv2
from PySide2.QtWidgets import QApplication, QMainWindow, QLabel,QMessageBox,QPushButton,QSpinBox,QRadioButton, QButtonGroup,QSlider,QTextEdit

from PySide2.QtGui import QImage, QPixmap,QPainter, QFont, QColor, Qt,QPen
from PySide2.QtCore import Qt, QTimer,QSize,QThread,QRect
from PySide2.QtUiTools import QUiLoader
from SimpleServer import SimpleServer
from ClickableLabel import ClickableLabel
import socket
import threading
import numpy as np
import math


#让服务器运行在一个单独线程中
class ServerThread(QThread):
    def __init__(self, server):
        super(ServerThread, self).__init__()
        self.server = server
        self.running = True

    def run(self):
        self.server.open()  # 打开服务器套接字并监听连接
        while self.running:
            # 在这里可以添加额外的线程处理逻辑，例如定时任务等
            self.sleep(1)  # 让线程休息一会儿，防止过于忙碌
        self.server.close()  # 关闭服务器套接字
    def sendmessage(self,message):
        self.server.handle_keyboard_input(message)
    def stop(self):
        self.running = False  # 通知线程停止
        self.wait()  # 等待线程结束

# ESP32-CAM的Web服务器URL，提供MJPEG视频流
stream_url = 'http://192.168.43.25:81/stream'  # 替换为实际的IP地址和端口号
class VideoStreamWindow(QMainWindow):
    def __init__(self):
        super(VideoStreamWindow, self).__init__()
        self.background_frame = None
        self.rect_center=None
        self.contours=None
        self.centers=[]
        self.a= [None] * 10000
        self.j=0
        self.i=0
        self.k=0
        self.flag=False
        self.c=True
        self.server = SimpleServer() #创建服务器类
        self.server_thread = None
        self.clickpoint=[]
        self.trace=[]
        self.buttonvalue=-1
        self.point2F=[]
        self.complete=False
        self.circle=[]
        loader = QUiLoader()
        ui_file = 'window.ui'  # 确保这里的路径正确
        self.ui = loader.load(ui_file)
        self.setGeometry(100, 100, 1000, 800)
        self.setWindowTitle('Video Stream')
        self.setCentralWidget(self.ui)  # 设置UI为窗口的中央部件
        # 找到UI中的QLabel控件
        self.video_label = self.ui.findChild(QLabel, 'viedo1')
        self.video2_label = self.ui.findChild(QLabel, 'viedo2')
        self.video3_label = self.ui.findChild(QLabel, 'viedo3')
        clickable_label = ClickableLabel(self.video3_label.parentWidget())  # 确保父部件正确
        clickable_label.setGeometry(self.video3_label.geometry())
        clickable_label.setPixmap(self.video3_label.pixmap())
        self.video3_label.setParent(None)  # 从原布局中移除
        self.ui.layout().addWidget(clickable_label)  # 假设self.ui.layout()是包含QLabel的布局的引用
        self.video3_label = clickable_label  # 更新引用到新的ClickableLabel
        self.ui.select.clicked.connect(self.sel)
        self.ui.connect1.clicked.connect(self.con)
        self.ui.discon.clicked.connect(self.discon)
        self.connect_button = self.ui.findChild(QPushButton, 'connect1')
        self.disconnect_button = self.ui.findChild(QPushButton, 'discon')
        self.start_button = self.ui.findChild(QPushButton, 'start')
        self.stop_button = self.ui.findChild(QPushButton, 'stop')
        self.stop_button.clicked.connect(self.stop)
        self.start_button.clicked.connect(self.start)
        self.ui.save.clicked.connect(self.save)
        self.ui.log.clicked.connect(self.log)
        self.gussian_key=self.ui.findChild(QSpinBox,'guss')
        self.erode_key=self.ui.findChild(QSpinBox,'erode')
        self.thread_key=self.ui.findChild(QSlider,'thread')
        self.text1=self.ui.findChild(QTextEdit,"dis_thread")
        self.thread_key.setRange(0, 255)
        self.thread_key.setValue(0)  # 设置初始值

        # 当滑动条的值改变时
        self.thread_key.valueChanged.connect(self.on_slider_value_changed)
        self.radio_button1 = self.ui.findChild(QRadioButton,'evade')
        self.radio_button1.setProperty("value", 1)  # 设置值
        self.radio_button2 = self.ui.findChild(QRadioButton,'free')
        self.radio_button2.setProperty("value", 2)  # 设置值
        self.radio_button3 = self.ui.findChild(QRadioButton,'follow')
        self.radio_button3.setProperty("value", 3)  # 设置值
        self.radio_button4 = self.ui.findChild(QRadioButton, 'park')
        self.radio_button4.setProperty("value", 4)  # 设置值
        self.button_group = QButtonGroup()

        # 将单选按钮添加到按钮组中，并设置互斥
        self.button_group.addButton(self.radio_button1)
        self.button_group.addButton(self.radio_button2)
        self.button_group.addButton(self.radio_button3)
        self.button_group.addButton(self.radio_button4)
        self.button_group.setExclusive(True)

        # 连接按钮组的按钮点击信号到槽函数
        self.button_group.buttonClicked.connect(self.on_button_clicked)

        if self.video_label:
          print("QLabel found!")
        else:
           print("QLabel not found in the UI.")
           sys.exit(1)
        if self.video2_label:
            print("QLabel2 found!")
        else:
            print("QLabel2 not found in the UI.")
            sys.exit(1)

            # 设置定时器来定期从视频流中捕获帧
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # 每50毫秒更新一次帧

        # 尝试打开视频捕获对象以读取MJPEG流
        self.cap = cv2.VideoCapture(stream_url)
        if not self.cap.isOpened():
            print("无法打开视频流")
            sys.exit(1)
    def stop(self):
        message = '0'
        self.c=False
        print(message)
        self.server_thread.sendmessage(message)
    def on_slider_value_changed(self,value):
        self.text1.setText(str(value))
    def on_button_clicked(self,button):
        value = button.property("value")
        self.buttonvalue=value
        if value==1:

            self.a[self.i]='g'
            self.i+=1
    def start(self):
        self.start_timer()
        # self.flag= not self.flag
        # if self.flag:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               self.start_timer()
        # else:
            # self.stop_timer()


    def start_timer(self):

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.send_message_to_clients)
        self.timer.start(1000)  # 每秒发送一次

    def stop_timer(self):
        if self.timer is not None:
            self.timer.stop()
            self.timer.deleteLater()  # 清理定时器
            self.timer = None

    def send_message_to_clients(self):
        # a=['b','b','b','0']
        # if self.j < len(a) and a[self.j] is not None:
        #     message = a[self.j]
        #     print(message)
        #     if self.server_thread is not None:
        #         self.server_thread.sendmessage(message)  # 假设sendmessage是一个正确的方法
        #     if a[self.j + 1] is not None:
        #         self.j += 1
       if self.j < len(self.a)and self.a[self.j] is not None and self.c:
           # 确保j没有超出数组a的索引范
           message =self.a[self.j]
           print(message)
           if self.server_thread is not  None:
             self.server_thread.sendmessage(message) # 假设sendmessage是一个正确的方法
             if self.a[self.j+1] is not None:
               self.j += 1

    def commander(self,targetpoint,contours):
        if self.rect_center is not None:
            # 使用蓝色绘制从矩形中心到圆心的线
            circelAngle = 9999.9999
            if targetpoint:
                circle_params = self.circle[0]  # 现在 circle_params 是 [256, 158, 18]

                center_x = circle_params[0]  # 256
                center_y = circle_params[1]
                q = (self.point2F[2][1] - self.point2F[1][1]) ** 2 + (self.point2F[2][0] - self.point2F[1][0]) ** 2
                w = (self.point2F[3][1] - self.point2F[2][1]) ** 2 + (self.point2F[3][0] - self.point2F[2][0]) ** 2
                c = (center_y - self.point2F[0][1]) ** 2 + (
                        center_x - self.point2F[0][0]) ** 2
                v = (center_y- self.point2F[2][1]) ** 2 + (
                        center_x - self.point2F[2][0]) ** 2

                # 条件判断
                if q > w:  # 1.1
                    # 计算两点之间的角度
                    dy = self.point2F[2][1] - self.point2F[1][1]
                    dx = self.point2F[2][0] - self.point2F[1][0]
                    j1 = math.atan2(dy, dx)

                    # 如果需要角度（以度为单位），则转换弧度到角度
                    j1 = math.degrees(j1)
                    j2 = cv2.fastAtan2(targetpoint.y() - self.rect_center[1],
                                       targetpoint.x() - self.rect_center[0])

                    # 根据条件计算偏移角度
                    if c > v:  # 1.2
                        circelAngle = j2 - j1
                        if circelAngle > math.pi:  # 大于180度
                            circelAngle -= 2 * math.pi
                        elif circelAngle < -math.pi:  # 小于-180度
                            circelAngle += 2 * math.pi
                    else:
                        circelAngle = j1 - j2
                        circelAngle = math.pi - circelAngle
                        if circelAngle > math.pi:  # 大于180度
                            circelAngle -= 2 * math.pi
                        elif circelAngle < -math.pi:  # 小于-180度
                            circelAngle += 2 * math.pi
                elif q > w:  # 2.1
                    # 计算两点之间的角度
                    j1 = cv2.fastAtan2(self.point2F[3][1] - self.point2F[2][1], self.point2F[3][0] - self.point2F[2][0])
                    j2 = cv2.fastAtan2(targetpoint.y() - self.rect_center[1],
                                       targetpoint.x() - self.rect_center[0])

                    # 根据条件计算偏移角度
                    if c > v:  # 2.2
                        circelAngle = j1 - j2
                        circelAngle = math.pi - circelAngle
                        if circelAngle > math.pi:  # 大于180度
                            circelAngle -= 2 * math.pi
                        elif circelAngle < -math.pi:  # 小于-180度
                            circelAngle += 2 * math.pi
                    else:
                        circelAngle = j2 - j1
                        if circelAngle > math.pi:  # 大于180度
                            circelAngle -= 2 * math.pi
                        elif circelAngle < -math.pi:  # 小于-180度
                            circelAngle += 2 * math.pi
                distance = cv2.pointPolygonTest(contours[0], (
                targetpoint.x(), targetpoint.y()), False)
                if distance < 0:

                    if circelAngle != 9999.9999:
                        if -90 < circelAngle < -20:
                          if self.i==0:
                            self.a[self.i] = 'r'
                            self.i += 1
                          elif self.a[self.i-1]!='r':
                              self.a[self.i] = 'r'
                              self.i += 1

                        elif -160 < circelAngle < -90:
                            if self.i == 0:
                                self.a[self.i] = 'l'
                                self.i += 1
                            elif self.a[self.i - 1] != 'l':
                                self.a[self.i] = 'l'
                                self.i += 1

                        elif 20 < circelAngle < 90:
                            if self.i == 0:
                                self.a[self.i] = 'l'
                                self.i += 1
                            elif self.a[self.i - 1] != 'l':
                                self.a[self.i] = 'l'
                                self.i += 1

                        elif 90 < circelAngle < 160:
                            if self.i == 0:
                                self.a[self.i] = 'r'
                                self.i += 1
                            elif self.a[self.i - 1] != 'r':
                                self.a[self.i] = 'r'
                                self.i += 1
                        elif -20 < circelAngle < 20:
                            if self.i == 0:
                                self.a[self.i] = 'g'
                                self.i += 1
                            elif self.a[self.i - 1] != 'g':
                                self.a[self.i] = 'g'
                                self.i += 1
                        elif (-180 < circelAngle < -160) or (160 < circelAngle < 180):
                            if self.i == 0:
                                self.a[self.i] = 'b'
                                self.i += 1
                            elif self.a[self.i - 1] != 'b':
                                 self.a[self.i] = 'b'
                                 self.i += 1
                else:
                    self.a[self.i] = '0'
                    self.i += 1


    def update_frame(self):
        ret, frame = self.cap.read()

        if ret:
            # 将 BGR 图像转换为 RGB 图像
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            h, w, ch = rgb_image.shape
            bytes_per_line = 3 * w

            # 创建 QImage 对象
            q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)

            # 如果需要缩放，在这里进行缩放操作
            scaled_img = q_img.scaled(self.video_label.size(), Qt.KeepAspectRatio)

            # 使用 QPainter 在缩放后的 QImage 上绘制文本
            painter = QPainter(scaled_img)
            painter.setPen(QPen(QColor(0, 255, 0), 2))  # 设置画笔为绿色，线宽为2
            font = QFont("Microsoft YaHei", 10)  # 使用支持中文的字体，这里以微软雅黑为例
            painter.setFont(font)
            text = "原视频"
            text_rect = QRect(scaled_img.width() - painter.fontMetrics().width(text) - 10, 10,
                              painter.fontMetrics().width(text), painter.fontMetrics().height())
            painter.drawText(text_rect, Qt.AlignRight | Qt.AlignTop, text)
            painter.end()

            # 设置 QLabel 的 QPixmap，使用绘制了文本的 scaled_img
            self.video_label.setPixmap(QPixmap.fromImage(scaled_img))

            # 强制 QLabel 更新显示
            self.video_label.update()
            if self.background_frame is not None and self.background_frame.size > 0:
                p = q_img.scaled(self.video3_label.size(), Qt.KeepAspectRatio)
                self.video3_label.setPixmap(QPixmap.fromImage(p))
                erodeLevel = int(self.erode_key.value())
                gaussianBlurLevel = (int(self.gussian_key.value()), int(self.gussian_key.value()))
                threshold_value = int(self.thread_key.value())

                # 计算绝对差值
                subtracted_mat = cv2.absdiff(self.background_frame, frame)

                # 检查subtracted_mat是否有效
                if subtracted_mat is not None and subtracted_mat.size > 0:
                    # 创建腐蚀操作的核
                    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (erodeLevel, erodeLevel), (-1, -1))

                    # 腐蚀操作 - 使用新的矩阵来存储结果
                    eroded_mat = cv2.erode(subtracted_mat, kernel, iterations=1)

                    # 高斯模糊 - 同样使用新的矩阵
                    blurred_mat = cv2.GaussianBlur(eroded_mat, gaussianBlurLevel, 0)

                    # 转换为灰度图像
                    gray_mat = cv2.cvtColor(blurred_mat, cv2.COLOR_BGR2GRAY)

                    # 阈值化
                    _, binary_mat = cv2.threshold(gray_mat, threshold_value, 255, cv2.THRESH_BINARY_INV)

                    # 霍夫圆变换找圆形区域


                    # 应用Canny边缘检测
                    minVal=30
                    maxVal=150
                    edges = cv2.Canny(binary_mat, minVal, maxVal)
                    self.contours, _ = cv2.findContours(edges.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    # 查找轮廓
                    for contour in self.contours:
                        # 计算最小面积矩形
                        area = cv2.contourArea(contour)
                        min_area=1000
                        # 如果面积大于最小面积阈值，则计算最小面积矩形并绘制
                        if area > min_area:
                          rect = cv2.minAreaRect(contour)
                          box = cv2.boxPoints(rect)
                          box = np.intp(box)
                          box=box.astype(np.int32)
                          self.point2F=box
                        # 在原始图像上绘制矩形（用绿色线）
                          cv2.drawContours(frame, [box], 0, (0, 255, 0), 2)

                        # 计算矩形中心（如果需要）
                          center = (int(rect[0][0]), int(rect[0][1]))
                          self.rect_center = center
                          break

                    circles = cv2.HoughCircles(binary_mat, cv2.HOUGH_GRADIENT, 1, binary_mat.shape[0] // 8,
                                               param1=100, param2=10, minRadius=0, maxRadius=40)

                    # 如果找到了圆，绘制它们
                    if circles is not None and len(circles) > 0:
                        circles = np.uint16(np.around(circles))
                        first_circle = circles[0, :]
                        self.circle = first_circle
                        first_circle=first_circle[0]
                        # 如果first_circle是从NumPy数组中获取的，并且NumPy数组的形状是(1, 3)，则应该这样做：
                        center_x = int(first_circle[0])
                        center_y = int(first_circle[1])
                        radius = int(first_circle[2])
                            # 绘制外圆，使用橙色 (BGR: (0, 128, 255))
                        cv2.circle(frame, (center_x,center_y), radius, (0, 128, 255), 2)
                        # 绘制圆心，使用红色 (BGR: (0, 0, 255))
                        cv2.circle(frame, (center_x,center_y), 2, (0, 0, 255), 3)
                        if hasattr(self, 'rect_center'):
                            # 绘制从圆心到self.rect_center的线，使用蓝色 (BGR: (255, 0, 0))
                            cv2.line(frame, (center_x,center_y), self.rect_center, (255, 0, 0), 2)
                        else:
                            print("Warning: self.rect_center is not set or does not exist.")
                        if self.video3_label.click_points is not None and self.buttonvalue==2:
                            self.commander(self.video3_label.click_points[0],self.contours)
                        if self.video3_label.trajectory is not  None and self.buttonvalue==3:
                            if self.complete is False and self.k<len(self.video3_label.trajectory):
                                self.commander(self.video3_label.trajectory[self.k],self.contours)
                            else:
                                self.k+=1
                                self.complete=True
                        if self.buttonvalue==4:
                            for contour in self.contours:
                                # 计算最小面积矩形
                                area = cv2.contourArea(contour)
                                min_area = 1000
                                # 如果面积大于最小面积阈值，则计算最小面积矩形并绘制
                                if area > min_area:
                                    rect = cv2.minAreaRect(contour)
                                    box = cv2.boxPoints(rect)
                                    box = np.intp(box)
                                    box = box.astype(np.int32)
                                    self.point2F = box
                                    # 在原始图像上绘制矩形（用绿色线）
                                    center = (int(rect[0][0]), int(rect[0][1]))
                                    self.centers.append(center)
                                    cv2.drawContours(frame, [box], 0, (0, 255, 0), 2)
                            if len(self.centers) > 0:
                                first_center =self.centers[0]  # 获取第一个center点
                                x_coord = first_center[0]  # 获取横坐标
                                y_coord = first_center[1]
                                second_center = self.centers[1]  # 获取第一个center点
                                x_coord1 = second_center[0]  # 获取横坐标
                                y_coord1 = second_center[1]
                                if x_coord > x_coord1:
                                    end = first_center
                                    start = second_center
                                else:
                                    end = second_center
                                    start = first_center
                                if end[0] - start[0] > start[1] - end[1]:
                                    r = start[1] - end[1]
                                    center_coordinates = (end[0] - r, end[1])
                                else:
                                    r = end[0] - start[0]
                                    center_coordinates = (end[0] - r, end[1])
                                start_angle_deg = -90 # 起点角度
                                end_angle_deg = -180
                                # 将角度从度转换为弧度
                                start_angle_rad = math.radians(start_angle_deg)
                                end_angle_rad = math.radians(end_angle_deg)

                                # 计算等间距的点的数量
                                num_points = 5

                                # 计算每个点之间的角度差
                                angle_step = (end_angle_rad - start_angle_rad) / (num_points - 1)

                                # 存储点的坐标
                                points = []

                                # 计算并存储每个点的坐标
                                for i in range(num_points):
                                    angle = start_angle_rad + i * angle_step
                                    x = int(center_coordinates[0] + r * math.cos(angle))
                                    y = int(center_coordinates[1] + r * math.sin(angle))
                                    points.append((x, y))

                                    # 绘制点（可选）
                                    cv2.circle(frame, (x, y), 3, (255, 0, 0), -1)

                                # 绘制圆弧（可选）
                                cv2.ellipse(frame, center_coordinates, (r, r), 0, start_angle_deg, end_angle_deg,(0, 255, 0), 2)

                                # 显示图像
                    h, w, ch = frame.shape
                    bytes_per_line = ch * w  # 取决于图像的颜色通道数
                    q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888).rgbSwapped()

                # 缩放QImage以适应self.video3_label的大小
                    p = q_img.scaled(self.video3_label.size(), Qt.KeepAspectRatio)

                # 设置self.video3_label的Pixmap
                    self.video3_label.setPixmap(QPixmap.fromImage(p))
    def sel(self):
        ret, frame = self.cap.read()
        if ret:
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # 膨胀操作，解决了地板砖侵蚀小车的问题
            kernel0 = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11), (-1, -1))#膨胀核
            self.background_frame= cv2.dilate(rgb_image, kernel0, iterations=1)#膨胀操作
            h, w, ch = self.background_frame.shape
            bytes_per_line = 3 * w
            q_img = QImage(self.background_frame, w, h, bytes_per_line, QImage.Format_RGB888)

            # 根据你的需求缩放图像，这里保持宽高比
            scaled_img = q_img.scaled(self.video2_label.size(), Qt.KeepAspectRatio)#不保持原有比列缩放如果参数设为KeeAspectRatio则保持原有纵横比
            # 设置QLabel的Pixmap
            painter = QPainter(scaled_img)
            painter.setPen(QPen(QColor(0, 255, 0), 2))  # 设置画笔为绿色，线宽为2
            font = QFont("Microsoft YaHei", 10)  # 使用支持中文的字体，这里以微软雅黑为例
            painter.setFont(font)
            text = "背景帧"
            text_rect = QRect(scaled_img.width() - painter.fontMetrics().width(text) - 10, 10,
                              painter.fontMetrics().width(text), painter.fontMetrics().height())
            painter.drawText(text_rect, Qt.AlignRight | Qt.AlignTop, text)
            painter.end()
        self.video2_label.setPixmap(QPixmap.fromImage(scaled_img))
    def con(self):
        if self.server_thread is None or not self.server_thread.isRunning():
            self.server_thread = ServerThread(self.server)
            self.server_thread.start()
            self.connect_button.setStyleSheet("background-color: green;")
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True                                                                                                            )
            QMessageBox.information(self, '提示', '服务器已启动')
    def discon(self):
        if self.server_thread and self.server_thread.isRunning():
            self.server_thread.stop()
            self.server_thread = None
            self.connect_button.setStyleSheet("background-color: white;")
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            QMessageBox.information(self, '提示', '服务器已停止')
    def save(self):
        with open('seetings.txt', 'w') as f:
            # 获取值并写入文件，每个值占一行
            erode_level = int(self.erode_key.value())
            gaussian_blur_level = int(self.gussian_key.value())
            threshold_value = int(self.thread_key.value())
            f.write(f"{gaussian_blur_level}\n")
            f.write(f"{erode_level}\n")
            f.write(f"{threshold_value}\n")
    def log(self):
        with open('seetings.txt', 'r') as f:
            # 从文件中读取值，并设置到对应的键上
            gaussian_blur_level = int(f.readline().strip())
            erode_level = int(f.readline().strip())
            threshold_value = int(f.readline().strip())

            # 假设这些键有 setValue 方法可以设置值
            self.erode_key.setValue(erode_level)
            self.gussian_key.setValue(gaussian_blur_level)
            self.thread_key.setValue(threshold_value)
    def closeEvent(self, event):
        self.cap.release()
        self.timer.stop()
        super(VideoStreamWindow, self).closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoStreamWindow()
    window.show()
    sys.exit(app.exec_())