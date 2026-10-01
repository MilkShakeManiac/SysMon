import sys
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Core hardware monitoring library
import psutil

# Optional GPU handling (NVIDIA)
try:
    import pynvml
    pynvml.nvmlInit()
    HAS_GPU = True
except Exception:
    HAS_GPU = False


class SystemMonitorWorker(QThread):
    """Worker thread that gathers system stats without freezing the GUI thread."""
    stats_updated = pyqtSignal(dict)

    def run(self):
        while True:
            # CPU Metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            freq_ghz = f"{cpu_freq.current / 1000:.1f} GHz" if cpu_freq else "N/A"

            # RAM Metrics
            ram = psutil.virtual_memory()
            ram_used_gb = ram.used / (1024**3)
            ram_total_gb = ram.total / (1024**3)
            ram_free_gb = ram.available / (1024**3)

            # Disk Metrics
            disk = psutil.disk_usage("/")
            
            # Network Metrics
            net = psutil.net_io_counters()

            # GPU Metrics (NVIDIA Fallback Check)
            gpu_percent = 0
            gpu_temp = "N/A"
            gpu_vram = "N/A"
            gpu_name = "No Discrete GPU"

            if HAS_GPU:
                try:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    gpu_name = pynvml.nvmlDeviceGetName(handle)
                    if isinstance(gpu_name, bytes):
                        gpu_name = gpu_name.decode("utf-8")
                        
                    utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_percent = utilization.gpu

                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    gpu_temp = f"{temp}°C"

                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_vram = f"{mem_info.used / (1024**3):.1f} GB / {mem_info.total / (1024**3):.1f} GB"
                except Exception:
                    pass

            stats = {
                "cpu_percent": int(cpu_percent),
                "cpu_cores": f"{cpu_count} Threads",
                "cpu_freq": freq_ghz,
                
                "ram_percent": int(ram.percent),
                "ram_text": f"{ram_used_gb:.1f} GB / {ram_total_gb:.1f} GB",
                "ram_free": f"{ram_free_gb:.1f} GB",

                "gpu_percent": int(gpu_percent),
                "gpu_name": gpu_name,
                "gpu_temp": gpu_temp,
                "gpu_vram": gpu_vram,

                "disk_percent": int(disk.percent),
                "net_sent": f"{net.bytes_sent / (1024**2):.1f} MB",
                "net_recv": f"{net.bytes_recv / (1024**2):.1f} MB",
            }

            self.stats_updated.emit(stats)


class ModernCard(QFrame):
    """Custom styled card widget with update helper methods."""

    def __init__(self, title: str, subtitle: str = "", accent_color: str = "#00adb5"):
        super().__init__()
        self.setObjectName("Card")
        self.setStyleSheet(
            f"""
            QFrame#Card {{
                background-color: #222831;
                border: 1px solid #393e46;
                border-radius: 12px;
            }}
            QFrame#Card:hover {{
                border: 1px solid {accent_color};
                background-color: #252c37;
            }}
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        # Title Row
        title_layout = QHBoxLayout()
        accent_indicator = QFrame()
        accent_indicator.setFixedWidth(4)
        accent_indicator.setFixedHeight(18)
        accent_indicator.setStyleSheet(
            f"background-color: {accent_color}; border-radius: 2px;"
        )

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #eeeeee; text-transform: uppercase; letter-spacing: 1px;"
        )

        title_layout.addWidget(accent_indicator)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        self.sub_label = QLabel(subtitle)
        self.sub_label.setStyleSheet("font-size: 12px; color: #929aab;")
        layout.addWidget(self.sub_label)

        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(8)
        layout.addLayout(self.content_layout)
        layout.addStretch()

        self.stat_labels = {}
        self.progress_bar = None

    def set_subtitle(self, text: str):
        self.sub_label.setText(text)

    def add_stat_row(self, key: str, label_text: str, default_val: str = "0"):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #929aab; font-size: 13px;")
        val = QLabel(default_val)
        val.setStyleSheet("color: #eeeeee; font-weight: 600; font-size: 13px;")
        
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val)
        self.content_layout.addLayout(row)
        
        self.stat_labels[key] = val

    def add_progress_bar(self, color: str = "#00adb5"):
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: #393e46;
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """
        )
        self.content_layout.addWidget(self.progress_bar)

    def update_val(self, key: str, value_text: str):
        if key in self.stat_labels:
            self.stat_labels[key].setText(value_text)

    def update_progress(self, val: int):
        if self.progress_bar:
            self.progress_bar.setValue(val)


class SystemMonitorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Monitor")
        self.resize(1050, 680)

        self.setStyleSheet("QMainWindow { background-color: #1a1e24; }")

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. SIDEBAR
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(
            """
            QFrame {
                background-color: #14171c;
                border-right: 1px solid #282d37;
            }
        """
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 24, 12, 24)
        sidebar_layout.setSpacing(8)

        brand_label = QLabel("MONITOR")
        brand_label.setStyleSheet(
            "color: #00adb5; font-size: 18px; font-weight: 800; padding: 0 8px 16px 8px; letter-spacing: 2px;"
        )
        sidebar_layout.addWidget(brand_label)

        nav_items = ["Dashboard", "CPU", "RAM", "GPU", "Settings"]
        for i, item in enumerate(nav_items):
            btn = QPushButton(item)
            btn.setCheckable(True)
            if i == 0:
                btn.setChecked(True)

            btn.setStyleSheet(
                """
                QPushButton {
                    border: none;
                    border-radius: 8px;
                    padding: 12px 16px;
                    text-align: left;
                    font-size: 13px;
                    font-weight: 600;
                    color: #929aab;
                    background-color: transparent;
                }
                QPushButton:hover {
                    background-color: #222831;
                    color: #eeeeee;
                }
                QPushButton:checked {
                    background-color: #00adb5;
                    color: #ffffff;
                }
            """
            )
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        status_label = QLabel("System Status: Active")
        status_label.setStyleSheet("color: #4ecca3; font-size: 11px; padding: 8px;")
        sidebar_layout.addWidget(status_label)

        main_layout.addWidget(sidebar)

        # 2. MAIN CONTENT AREA
        content_widget = QWidget()
        grid_layout = QGridLayout(content_widget)
        grid_layout.setContentsMargins(28, 28, 28, 28)
        grid_layout.setSpacing(20)

        # Header
        top_banner = ModernCard(
            "System Dashboard", "Hardware Overview & Performance Metrics", "#00adb5"
        )
        grid_layout.addWidget(top_banner, 0, 0, 1, 2)

        # CPU Card
        self.cpu_card = ModernCard("CPU Usage", "Loading...", "#ff2e63")
        self.cpu_card.add_stat_row("load", "Current Load", "0%")
        self.cpu_card.add_progress_bar("#ff2e63")
        self.cpu_card.add_stat_row("freq", "Clock Speed", "0 GHz")
        grid_layout.addWidget(self.cpu_card, 1, 0)

        # RAM Card
        self.ram_card = ModernCard("Memory Usage", "System RAM", "#00adb5")
        self.ram_card.add_stat_row("used", "Used Memory", "0 GB")
        self.ram_card.add_progress_bar("#00adb5")
        self.ram_card.add_stat_row("free", "Available", "0 GB")
        grid_layout.addWidget(self.ram_card, 1, 1)

        # GPU Card
        self.gpu_card = ModernCard("GPU Performance", "Detecting...", "#fce38a")
        self.gpu_card.add_stat_row("load", "Core Utilization", "0%")
        self.gpu_card.add_progress_bar("#fce38a")
        self.gpu_card.add_stat_row("vram", "VRAM Usage", "N/A")
        self.gpu_card.add_stat_row("temp", "Temperature", "N/A")
        grid_layout.addWidget(self.gpu_card, 2, 0)

        # Network/Disk Card
        self.net_card = ModernCard("Network & Disk", "Live Metrics", "#4ecca3")
        self.net_card.add_stat_row("disk", "Primary Disk Used", "0%")
        self.net_card.add_progress_bar("#4ecca3")
        self.net_card.add_stat_row("sent", "Sent Data", "0 MB")
        self.net_card.add_stat_row("recv", "Received Data", "0 MB")
        grid_layout.addWidget(self.net_card, 2, 1)

        main_layout.addWidget(content_widget)

        # Initialize background monitor thread
        self.worker = SystemMonitorWorker()
        self.worker.stats_updated.connect(self.apply_live_stats)
        self.worker.start()

    def apply_live_stats(self, stats: dict):
        """Receives metrics dictionary every second and updates UI elements."""
        # CPU Updates
        self.cpu_card.set_subtitle(stats["cpu_cores"])
        self.cpu_card.update_val("load", f"{stats['cpu_percent']}%")
        self.cpu_card.update_progress(stats["cpu_percent"])
        self.cpu_card.update_val("freq", stats["cpu_freq"])

        # RAM Updates
        self.ram_card.update_val("used", stats["ram_text"])
        self.ram_card.update_progress(stats["ram_percent"])
        self.ram_card.update_val("free", stats["ram_free"])

        # GPU Updates
        self.gpu_card.set_subtitle(stats["gpu_name"])
        self.gpu_card.update_val("load", f"{stats['gpu_percent']}%")
        self.gpu_card.update_progress(stats["gpu_percent"])
        self.gpu_card.update_val("vram", stats["gpu_vram"])
        self.gpu_card.update_val("temp", stats["gpu_temp"])

        # Network/Disk Updates
        self.net_card.update_val("disk", f"{stats['disk_percent']}%")
        self.net_card.update_progress(stats["disk_percent"])
        self.net_card.update_val("sent", stats["net_sent"])
        self.net_card.update_val("recv", stats["net_recv"])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SystemMonitorApp()
    window.show()
    sys.exit(app.exec())