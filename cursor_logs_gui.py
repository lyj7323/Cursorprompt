#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cursor 프롬프트 추출 GUI 애플리케이션
"""

import os
import sys
import threading
import datetime
import traceback
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, 
                            QWidget, QLabel, QTextEdit, QFileDialog, QProgressBar, QMessageBox,
                            QCheckBox, QGroupBox, QComboBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, pyqtSlot, QTimer
from PyQt5.QtGui import QFont, QIcon
import logging

# 기존 코드 임포트
import debug_extraction
from debug_extraction import WORKSPACE_PATH, SAVE_PATH

# 로그 핸들러 클래스
class ThreadLogHandler(logging.Handler):
    """GUI로 로그 메시지를 전송하는 핸들러"""
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        
    def emit(self, record):
        log_entry = self.format(record)
        self.signal.emit(log_entry)

# 시그널 클래스 (스레드 간 통신용)
class WorkerSignals(QObject):
    """추출 작업 스레드로부터 UI 스레드로 신호를 보내기 위한 클래스"""
    progress = pyqtSignal(int)  # 진행 정도 (0-100)
    status = pyqtSignal(str)    # 상태 메시지
    finished = pyqtSignal(tuple)  # 완료 신호 (성공 여부, 결과 메시지)
    log = pyqtSignal(str)  # 로그 메시지

# 작업 스레드 클래스
class ExtractionThread(threading.Thread):
    """백그라운드에서 프롬프트 추출을 실행하는 스레드"""
    
    def __init__(self, workspace_path, save_path):
        super().__init__()
        self.workspace_path = workspace_path
        self.save_path = save_path
        self.signals = WorkerSignals()
        
    def run(self):
        """스레드 실행 함수"""
        try:
            # 진행 상황 업데이트 (시작)
            self.signals.progress.emit(10)
            self.signals.status.emit("프롬프트 추출 중...")
            
            # 로그 메시지 설정
            log_handler = ThreadLogHandler(self.signals.log)
            debug_extraction.logger.addHandler(log_handler)
            
            # 프롬프트 추출 및 저장
            saved_files = debug_extraction.extract_prompts(
                workspace_path=self.workspace_path,
                save_path=self.save_path
            )
            
            # 진행 상황 업데이트 (완료)
            self.signals.progress.emit(100)
            
            if saved_files:
                success_message = f"{len(saved_files)}개 파일 저장 완료:\n"
                for file_path in saved_files:
                    success_message += f"  - {file_path}\n"
                self.signals.status.emit("추출 및 저장 완료!")
                self.signals.finished.emit((True, success_message))
            else:
                self.signals.status.emit("저장된 파일 없음")
                self.signals.finished.emit((False, "저장된 파일이 없습니다."))
            
        except Exception as e:
            error_msg = f"오류 발생: {str(e)}\n{traceback.format_exc()}"
            self.signals.log.emit(error_msg)
            self.signals.status.emit("오류 발생")
            self.signals.finished.emit((False, error_msg))
            
        finally:
            # 로그 핸들러 제거
            for handler in debug_extraction.logger.handlers[:]:
                if isinstance(handler, ThreadLogHandler):
                    debug_extraction.logger.removeHandler(handler)

# 메인 윈도우 클래스
class CursorLogsGUI(QMainWindow):
    """Cursor 프롬프트 추출 GUI 메인 윈도우"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
        # 기본 경로 설정
        self.workspace_path = WORKSPACE_PATH
        self.save_path = SAVE_PATH
        
        # 자동 추출 관련 설정
        self.timer = QTimer()
        self.timer.timeout.connect(self.start_extraction)
        self.timer_interval = 5 * 60 * 1000  # 5분(밀리초 단위)
        self.auto_extract_running = False
        
        # 상태 표시
        self.update_path_labels()
    
    def init_ui(self):
        """UI 초기화"""
        # 윈도우 설정
        self.setWindowTitle("Cursor 프롬프트 추출기")
        self.setGeometry(100, 100, 900, 700)  # 윈도우 크기 증가
        
        # 버튼 스타일 공통 설정
        button_style = """
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
                min-width: 120px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #e6e6e6;
            }
            QPushButton:pressed {
                background-color: #d9d9d9;
            }
        """
        
        # 중앙 위젯 및 레이아웃
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)  # 여백 추가
        main_layout.setSpacing(15)  # 간격 설정
        
        # 타이틀
        title_label = QLabel("Cursor 프롬프트 추출 도구")
        title_font = QFont("Arial", 18, QFont.Bold)  # 폰트 크기 증가
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("margin-bottom: 15px;")  # 아래 여백 추가
        main_layout.addWidget(title_label)
        
        # 경로 설정 섹션
        path_group = QGroupBox("경로 설정")
        path_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        path_layout = QVBoxLayout()
        path_layout.setContentsMargins(15, 20, 15, 15)  # 내부 여백
        path_layout.setSpacing(15)  # 간격 설정
        
        # 워크스페이스 경로
        workspace_layout = QHBoxLayout()
        self.workspace_label = QLabel("워크스페이스 경로:")
        self.workspace_label.setMinimumWidth(120)  # 최소 폭 설정
        self.workspace_label.setStyleSheet("font-weight: bold;")
        workspace_layout.addWidget(self.workspace_label)
        
        self.workspace_path_label = QLabel()
        self.workspace_path_label.setMinimumWidth(400)  # 최소 폭 설정
        self.workspace_path_label.setFrameStyle(QLabel.Panel | QLabel.Sunken)  # 테두리 스타일
        self.workspace_path_label.setStyleSheet("background-color: #000000; color: #ffffff; padding: 8px; border-radius: 4px; border: 1px solid #aaa;")
        self.workspace_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)  # 텍스트 선택 가능
        workspace_layout.addWidget(self.workspace_path_label, 1)  # 1은 stretch factor
        
        workspace_btn = QPushButton("변경")
        workspace_btn.setFixedWidth(80)  # 고정 폭 설정
        workspace_btn.setMinimumHeight(30)  # 최소 높이 설정
        workspace_btn.setStyleSheet(button_style)
        workspace_btn.clicked.connect(self.set_workspace_path)
        workspace_layout.addWidget(workspace_btn)
        path_layout.addLayout(workspace_layout)
        
        # 저장 경로
        save_layout = QHBoxLayout()
        self.save_label = QLabel("저장 경로:")
        self.save_label.setMinimumWidth(120)  # 최소 폭 설정
        self.save_label.setStyleSheet("font-weight: bold;")
        save_layout.addWidget(self.save_label)
        
        self.save_path_label = QLabel()
        self.save_path_label.setMinimumWidth(400)  # 최소 폭 설정
        self.save_path_label.setFrameStyle(QLabel.Panel | QLabel.Sunken)  # 테두리 스타일
        self.save_path_label.setStyleSheet("background-color: #000000; color: #ffffff; padding: 8px; border-radius: 4px; border: 1px solid #aaa;")
        self.save_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)  # 텍스트 선택 가능
        save_layout.addWidget(self.save_path_label, 1)  # 1은 stretch factor
        
        save_btn = QPushButton("변경")
        save_btn.setFixedWidth(80)  # 고정 폭 설정
        save_btn.setMinimumHeight(30)  # 최소 높이 설정
        save_btn.setStyleSheet(button_style)
        save_btn.clicked.connect(self.set_save_path)
        save_layout.addWidget(save_btn)
        path_layout.addLayout(save_layout)
        
        path_group.setLayout(path_layout)
        main_layout.addWidget(path_group)
        
        # 자동 추출 설정 섹션
        auto_extract_group = QGroupBox("자동 추출 설정")
        auto_extract_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        auto_extract_layout = QVBoxLayout()
        auto_extract_layout.setContentsMargins(15, 20, 15, 15)  # 내부 여백
        auto_extract_layout.setSpacing(15)  # 간격 설정
        
        # 자동 추출 설명
        auto_extract_desc = QLabel("자동 추출 기능을 활성화하면 5분마다 자동으로 데이터가 추출됩니다.")
        auto_extract_desc.setStyleSheet("color: #555; font-style: italic;")
        auto_extract_layout.addWidget(auto_extract_desc)
        
        # 자동 추출 버튼
        auto_button_layout = QHBoxLayout()
        
        self.auto_extract_btn = QPushButton("자동 추출 시작")
        self.auto_extract_btn.setStyleSheet(button_style + "background-color: #2196F3; color: white; font-weight: bold;")
        self.auto_extract_btn.clicked.connect(self.toggle_auto_extract)
        auto_button_layout.addWidget(self.auto_extract_btn)
        
        auto_extract_layout.addLayout(auto_button_layout)
        auto_extract_group.setLayout(auto_extract_layout)
        main_layout.addWidget(auto_extract_group)
        
        # 진행 상태 표시 레이아웃
        progress_layout = QVBoxLayout()
        progress_layout.setContentsMargins(10, 10, 10, 10)
        progress_layout.setSpacing(5)
        
        progress_label = QLabel("진행 상태")
        progress_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        progress_layout.addWidget(progress_label)
        
        self.progressbar = QProgressBar()
        self.progressbar.setStyleSheet("""
            QProgressBar {
                background-color: #000000;
                color: #ffffff;
                border-radius: 5px;
                text-align: center;
                height: 25px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 5px;
            }
        """)
        self.progressbar.setValue(0)
        progress_layout.addWidget(self.progressbar)
        
        # 로그 표시 영역
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(10, 10, 10, 10)
        log_layout.setSpacing(5)
        
        log_label = QLabel("로그")
        log_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        log_layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #000000;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 5px;
                font-family: Consolas, Monaco, monospace;
                font-size: 11px;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        progress_group = QGroupBox("진행 상황")
        progress_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        log_group = QGroupBox("로그")
        log_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group, 1)  # 로그 창에 stretch factor 1 적용 (나머지 공간 채우기)
        
        # 버튼 섹션
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)  # 버튼 간격
        button_layout.setContentsMargins(5, 10, 5, 5)  # 여백
        
        self.start_btn = QPushButton("수동 추출 시작")
        self.start_btn.setStyleSheet(button_style + "background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_btn.clicked.connect(self.start_extraction)
        button_layout.addWidget(self.start_btn)
        
        self.open_dir_btn = QPushButton("저장 폴더 열기")
        self.open_dir_btn.setStyleSheet(button_style)
        self.open_dir_btn.clicked.connect(self.open_save_dir)
        button_layout.addWidget(self.open_dir_btn)
        
        self.exit_btn = QPushButton("종료")
        self.exit_btn.setStyleSheet(button_style)
        self.exit_btn.clicked.connect(self.close)
        button_layout.addWidget(self.exit_btn)
        
        main_layout.addLayout(button_layout)
        
        # 상태바
        self.statusBar().setStyleSheet("QStatusBar { border-top: 1px solid #ccc; padding: 5px; }")
        self.statusBar().showMessage("준비됨")
    
    def update_path_labels(self):
        """경로 레이블 업데이트"""
        self.workspace_path_label.setText(self.workspace_path)
        self.save_path_label.setText(self.save_path)
    
    def set_workspace_path(self):
        """워크스페이스 경로 설정"""
        path = QFileDialog.getExistingDirectory(self, "워크스페이스 경로 선택", self.workspace_path)
        if path:
            self.workspace_path = path
            self.update_path_labels()
    
    def set_save_path(self):
        """저장 경로 설정"""
        path = QFileDialog.getExistingDirectory(self, "저장 경로 선택", self.save_path)
        if path:
            self.save_path = path
            self.update_path_labels()
    
    def open_save_dir(self):
        """저장 폴더 열기"""
        if os.path.exists(self.save_path):
            import subprocess
            
            # 운영체제에 따라 폴더 열기 명령 실행
            if sys.platform == 'win32':
                os.startfile(self.save_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.Popen(['open', self.save_path])
            else:  # Linux
                subprocess.Popen(['xdg-open', self.save_path])
        else:
            QMessageBox.warning(self, "경로 없음", f"경로가 존재하지 않습니다: {self.save_path}")
    
    def toggle_auto_extract(self):
        """자동 추출 기능 토글"""
        if self.auto_extract_running:
            # 타이머 중지
            self.timer.stop()
            self.auto_extract_running = False
            self.auto_extract_btn.setText("자동 추출 시작")
            self.auto_extract_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    padding: 8px 12px;
                    font-size: 13px;
                    min-width: 120px;
                    min-height: 40px;
                    background-color: #2196F3;
                    color: white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #0b7dda;
                }
            """)
            self.log_text.append("자동 추출이 중지되었습니다.")
            self.statusBar().showMessage("자동 추출 중지됨")
        else:
            # 타이머 시작
            self.timer.start(self.timer_interval)
            self.auto_extract_running = True
            self.auto_extract_btn.setText("자동 추출 중지")
            self.auto_extract_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    padding: 8px 12px;
                    font-size: 13px;
                    min-width: 120px;
                    min-height: 40px;
                    background-color: #F44336;
                    color: white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
            """)
            self.log_text.append(f"자동 추출이 시작되었습니다. (5분 간격)")
            current_time = datetime.datetime.now()
            next_time = current_time + datetime.timedelta(minutes=5)
            self.log_text.append(f"다음 추출 시간: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.statusBar().showMessage("자동 추출 실행 중...")
            
            # 즉시 한 번 실행
            self.start_extraction()
    
    def start_extraction(self):
        """추출 시작"""
        # 저장 경로 생성
        os.makedirs(self.save_path, exist_ok=True)
        
        # 버튼 비활성화 (자동 추출 버튼은 비활성화하지 않음)
        self.start_btn.setEnabled(False)
        
        # 진행바 초기화
        self.progressbar.setValue(0)
        
        # 로그 창 지우기 (자동 모드에서는 로그를 계속 추가)
        if not self.auto_extract_running:
            self.log_text.clear()
        
        # 추출 시작 정보 표시
        start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.log_text.append(f"='='='='='='='='='='='='='='='='='='='='='='='='='='='='='")
        self.log_text.append(f"Cursor 프롬프트 추출 시작 (시간: {start_time})")
        self.log_text.append(f"='='='='='='='='='='='='='='='='='='='='='='='='='='='='='")
        self.log_text.append(f"워크스페이스 경로: {self.workspace_path}")
        self.log_text.append(f"저장 경로: {self.save_path}")
        
        # 추출 스레드 생성 및 실행
        self.extraction_thread = ExtractionThread(
            workspace_path=self.workspace_path,
            save_path=self.save_path
        )
        
        # 시그널 연결
        self.extraction_thread.signals.progress.connect(self.update_progress)
        self.extraction_thread.signals.status.connect(self.update_status)
        self.extraction_thread.signals.finished.connect(self.on_extraction_finished)
        self.extraction_thread.signals.log.connect(self.update_log)
        
        # 스레드 시작
        self.extraction_thread.start()
    
    @pyqtSlot(int)
    def update_progress(self, value):
        """진행 상황 업데이트"""
        self.progressbar.setValue(value)
    
    @pyqtSlot(str)
    def update_status(self, message):
        """상태 메시지 업데이트"""
        self.statusBar().showMessage(message)
    
    @pyqtSlot(str)
    def update_log(self, message):
        """로그 메시지 업데이트"""
        self.log_text.append(message)
        # 스크롤 맨 아래로
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
    
    @pyqtSlot(tuple)
    def on_extraction_finished(self, result):
        """추출 완료 처리"""
        success, message = result
        
        # 상태 업데이트
        finish_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.log_text.append(f"\n추출 작업 완료 (시간: {finish_time})")
        
        # 버튼 활성화
        self.start_btn.setEnabled(True)
        
        # 자동 모드에서는 다음 추출 시간 표시
        if self.auto_extract_running:
            current_time = datetime.datetime.now()
            next_time = current_time + datetime.timedelta(milliseconds=self.timer_interval)
            self.log_text.append(f"다음 추출 시간: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.statusBar().showMessage(f"자동 추출 실행 중... 다음 추출: {next_time.strftime('%H:%M:%S')}")
        else:
            # 결과 메시지 표시
            if success:
                QMessageBox.information(self, "완료", message)
            else:
                QMessageBox.warning(self, "오류", message)
    
    def closeEvent(self, event):
        """프로그램 종료 시 이벤트 처리"""
        if self.auto_extract_running:
            reply = QMessageBox.question(
                self, '종료 확인', 
                "자동 추출이 실행 중입니다. 종료하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 타이머 중지
                self.timer.stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

# 메인 실행 코드
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 모던한 스타일 적용
    window = CursorLogsGUI()
    window.show()
    sys.exit(app.exec_()) 