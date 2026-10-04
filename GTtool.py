# By topDress
import multiprocessing
multiprocessing.freeze_support()
import sys
import os
import shutil
import zipfile
import psutil
import wmi
import platform
import subprocess
import winreg
from datetime import datetime
from cpuinfo import get_cpu_info
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QRadioButton, QCheckBox, QTextEdit, QFileDialog, QGroupBox,
                               QProgressBar, QLabel, QMessageBox, QComboBox)
from PySide6.QtCore import Qt, QThread, Signal, QSettings, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
def get_resource_path(relative_path):
    """获取打包后资源真实路径"""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
# ===================== 全局常量工具函数 =====================
GAME_PROCESS_LEGACY = "GTA5.exe"
GAME_PROCESS_ENHANCED = "GTAVEnhanced.exe"
# 增强版 / BE / 启动器相关进程，用于检测和结束
GTA_RELATED_PROCESSES = [
    "GTA5.exe",
    "GTAVEnhanced.exe",
    "GTA5_Enhanced.exe",
    "GTA5_Enhanced_BE.exe",
    "GTAVEnhancedBE.exe",
    "BEService_x64.exe",
    "PlayGTAV.exe",
]
BE_SERVICE_NAME = "BEService"
ROCKSTAR_LAUNCHER_PROC = "RockstarGamesLauncher.exe"
SUPPORT_AUDIO_EXT = [".mp3", ".wma", ".m4a"]
BACKUP_MARKER_FILENAME = "gt_tool_backup_marker.txt"
def get_documents():
    return os.path.expanduser("~\\Documents")
def get_tool_config_dir():
    """工具配置/缓存根目录:文档/GT Tool"""
    config_dir = os.path.join(get_documents(), "GT Tool")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir
def is_game_running():
    """检测传承版/增强版/BE/启动器相关进程是否运行"""
    target_names = [name.lower() for name in GTA_RELATED_PROCESSES]
    for p in psutil.process_iter(["name"]):
        name = p.info.get("name")
        if name and name.lower() in target_names:
            return True, name
    return False, ""
def find_process_by_name(name):
    name_lower = name.lower()
    for p in psutil.process_iter(["name", "pid"]):
        pname = p.info.get("name")
        if pname and pname.lower() == name_lower:
            return p
    return None
def terminate_process(name):
    """尝试正常退出 失败则强制结束"""
    proc = find_process_by_name(name)
    if not proc:
        return False, f"未找到进程: {name}"
    try:
        proc.terminate()
        proc.wait(timeout=5)
        return True, f"已终止: {name}"
    except psutil.NoSuchProcess:
        return True, f"进程已结束: {name}"
    except psutil.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=5)
            return True, f"已强制结束: {name}"
        except Exception as e:
            return False, f"强制结束失败: {name}，{e}"
    except Exception as e:
        try:
            proc.kill()
            return True, f"已强制结束: {name}"
        except Exception as e2:
            return False, f"结束进程异常: {name}，{e2}"
def stop_be_service():
    """停止 BattlEye 服务"""
    try:
        result = subprocess.run(
            ["net", "stop", BE_SERVICE_NAME],
            capture_output=True,
            text=True,
            shell=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, f"已停止服务: {BE_SERVICE_NAME}"
        else:
            return False, f"停止服务返回码非0: {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, "停止服务超时"
    except Exception as e:
        return False, f"停止服务异常: {e}"
def kill_all_game_processes():
    """结束所有 GTA 相关进程 并停止 BE 服务"""
    logs = []
    ok, msg = stop_be_service()
    logs.append(msg)
    for proc_name in GTA_RELATED_PROCESSES:
        ok, msg = terminate_process(proc_name)
        logs.append(msg)
    return logs
def get_windows_display_version():
    """获取Windows 显示版本号"""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        display_version, _ = winreg.QueryValueEx(key, "DisplayVersion")
        winreg.CloseKey(key)
        return display_version
    except Exception:
        return "未知"
def get_hardware_info_str():
    """硬件信息"""
    c = wmi.WMI()
    lines = []
    # 主板
    try:
        board = c.Win32_BaseBoard()[0]
        manu = board.Manufacturer.strip() if board.Manufacturer else ""
        prod = board.Product.strip() if board.Product else ""
        board_str = f"{manu} {prod}".strip()
        if not board_str:
            board_str = "未知"
    except Exception:
        board_str = "未知"
    lines.append(f"主板: {board_str}")
    # 中央处理器CPU
    try:
        cpu_info = get_cpu_info()
        cpu_str = cpu_info['brand_raw']
    except Exception:
        cpu_str = "未知"
    lines.append(f"中央处理器(CPU): {cpu_str}")
    # 内存
    mem_str = "未知"
    try:
        total_gb = round(psutil.virtual_memory().total / (1024**3), 1)
        mem_str = f"{total_gb}GB"
        # 内存频率与插槽
        try:
            speed = ""
            used_slots = 0
            total_slots = 0
            for mem in c.Win32_PhysicalMemory():
                used_slots += 1
                if not speed and mem.Speed:
                    speed = f"{mem.Speed} MHz"
            for arr in c.Win32_PhysicalMemoryArray():
                total_slots = arr.MemoryDevices
            if speed:
                mem_str += f"-{speed}"
            if total_slots > 0:
                mem_str += f" ({used_slots}/{total_slots} 插槽)"
        except Exception:
            pass
    except Exception:
        pass
    lines.append(f"内存: {mem_str}")
    # 显示卡GPU
    gpu_list = []
    try:
        gpus = c.Win32_VideoController()
        for gpu in gpus:
            name = gpu.Name.strip() if gpu.Name else "未知"
            vram = ""
            try:
                if gpu.AdapterRAM and int(gpu.AdapterRAM) > 0:
                    vram_gb = int(int(gpu.AdapterRAM) / (1024**3))
                    vram = f" ({vram_gb} GB)"
            except Exception:
                pass
            gpu_list.append(f"{name}{vram}")
    except Exception:
        gpu_list.append("未知")
    lines.append(f"显示卡(GPU): {gpu_list[0]}")
    for item in gpu_list[1:]:
        lines.append(f"{item}")
    # 显示器
    mon_list = []
    try:
        monitors = c.Win32_DesktopMonitor()
        for idx, mon in enumerate(monitors):
            name = mon.Name.strip() if mon.Name else "通用监视器"
            res_info = ""
            try:
                w = mon.ScreenWidth
                h = mon.ScreenHeight
                if w and h and int(w) > 0 and int(h) > 0:
                    diagonal = round((int(w)**2 + int(h)**2) ** 0.5 / 96, 1)
                    res_info = f' [{diagonal}" {w} x {h}]'
            except Exception:
                pass
            prefix = "主屏 " if idx == 0 else ""
            mon_list.append(f"{prefix}{name}{res_info}")
    except Exception:
        mon_list.append("通用监视器")
    lines.append(f"显示器: {mon_list[0]}")
    for item in mon_list[1:]:
        lines.append(f"{item}")
    # 硬盘
    disk_list = []
    try:
        disks = c.Win32_DiskDrive()
        for disk in disks:
            model = disk.Model.strip() if disk.Model else "未知"
            size = ""
            try:
                if disk.Size and int(disk.Size) > 0:
                    size_gb = round(int(disk.Size) / (1024**3), 1)
                    size = f" ({size_gb}GB)"
            except Exception:
                pass
            disk_list.append(f"{model}{size}")
    except Exception:
        disk_list.append("未知")
    lines.append(f"硬盘: {disk_list[0]}")
    for item in disk_list[1:]:
        lines.append(f"{item}")
    # 声卡
    sound_list = []
    try:
        sounds = c.Win32_SoundDevice()
        for s in sounds:
            name = s.Name.strip() if s.Name else "未知"
            sound_list.append(name)
    except Exception:
        sound_list.append("未知")
    lines.append(f"声卡: {sound_list[0]}")
    for item in sound_list[1:]:
        lines.append(f"{item}")
    # 网卡
    nic_list = []
    try:
        nics = [n for n in c.Win32_NetworkAdapter() if n.PhysicalAdapter and n.NetEnabled]
        for nic in nics:
            name = nic.Name.strip() if nic.Name else "未知"
            nic_list.append(name)
    except Exception:
        nic_list.append("未知")
    lines.append(f"网卡: {nic_list[0]}")
    for item in nic_list[1:]:
        lines.append(f"{item}")
    # 系统
    try:
        os_info = c.Win32_OperatingSystem()[0]
        sys_str = f"{os_info.Caption.strip()} {os_info.OSArchitecture.strip()}"
    except Exception:
        sys_str = f"{platform.system()} {platform.release()}"
    lines.append(f"系统: {sys_str}")
    # 系统版本
    lines.append(f"系统版本: {get_windows_display_version()}")
    # 时间戳
    now = datetime.now()
    time_str = now.strftime("%Y.%m.%d %H:%M:%S").replace(" 0", " ").replace(".0", ".")
    lines.append(f"时间戳: {time_str}")
    return "\n".join(lines)
# ===================== 备份工作线程 =====================
class BackupWorker(QThread):
    progress_update = Signal(int)
    log_msg = Signal(str)
    finished_signal = Signal(bool)
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
    def run(self):
        try:
            self.log_msg.emit("开始导出备份任务...")
            src_base = self.cfg["src_base"]
            out_path = self.cfg["out_path"]
            use_zip = self.cfg["use_zip"]
            ver_tag = self.cfg["ver_tag"]
            items = self.cfg["backup_items"]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            folder_name = f"GTA_Backup_{ver_tag}_{timestamp}"
            total_steps = max(len(items), 1)
            step = 0
            if use_zip:
                zip_path = os.path.join(out_path, folder_name + ".zip")
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    marker_content = f"GTA GT Tool Backup\nVersion:{ver_tag}\nTime:{timestamp}"
                    zf.writestr(BACKUP_MARKER_FILENAME, marker_content)
                    for item in items:
                        step += 1
                        self.progress_update.emit(int(step / total_steps * 95))
                        src = item["src"]
                        arc_root = item["arc"]
                        if not os.path.exists(src):
                            self.log_msg.emit(f"跳过不存在路径: {src}")
                            continue
                        if os.path.isdir(src):
                            for root, _, files in os.walk(src):
                                for fname in files:
                                    fp = os.path.join(root, fname)
                                    rel = os.path.relpath(fp, src)
                                    zf.write(fp, os.path.join(arc_root, rel))
                        else:
                            zf.write(src, arc_root)
                self.log_msg.emit(f"ZIP导出完成: {zip_path}")
            else:
                dest_dir = os.path.join(out_path, folder_name)
                os.makedirs(dest_dir, exist_ok=True)
                marker_path = os.path.join(dest_dir, BACKUP_MARKER_FILENAME)
                with open(marker_path, "w", encoding="utf-8") as f:
                    f.write(f"GTA GT Tool Backup\nVersion:{ver_tag}\nTime:{timestamp}")
                for item in items:
                    step += 1
                    self.progress_update.emit(int(step / total_steps * 95))
                    src = item["src"]
                    dst_sub = os.path.join(dest_dir, item["arc"])
                    if not os.path.exists(src):
                        self.log_msg.emit(f"跳过不存在路径: {src}")
                        continue
                    if os.path.isdir(src):
                        os.makedirs(os.path.dirname(dst_sub), exist_ok=True)
                        shutil.copytree(src, dst_sub, dirs_exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(dst_sub), exist_ok=True)
                        shutil.copy2(src, dst_sub)
                self.log_msg.emit(f"文件夹导出完成: {dest_dir}")
            self.progress_update.emit(100)
            self.finished_signal.emit(True)
        except Exception as e:
            self.log_msg.emit(f"导出异常: {str(e)}")
            self.finished_signal.emit(False)
# ===================== 还原工作线程 =====================
class RestoreWorker(QThread):
    progress_update = Signal(int)
    log_msg = Signal(str)
    finished_signal = Signal(bool)
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
    def run(self):
        try:
            self.log_msg.emit("开始导入还原...")
            bak_path = self.cfg["bak_path"]
            restore_items = self.cfg["restore_items"]
            use_zip = os.path.isfile(bak_path) and bak_path.lower().endswith(".zip")
            total_steps = max(len(restore_items), 1)
            step = 0
            if use_zip:
                with zipfile.ZipFile(bak_path, "r") as zf:
                    all_infos = zf.infolist()
                    file_infos = [info for info in all_infos if not info.is_dir()]
                    file_names = [info.filename for info in file_infos]
                    
                    for item in restore_items:
                        step += 1
                        self.progress_update.emit(int(step / total_steps * 95))
                        arc_path = item["arc_path"]
                        target_path = item["target_path"]
                        item_type = item["type"]
                        exclude = item.get("exclude", [])
                        if item_type == "file":
                            if arc_path in file_names:
                                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                data = zf.read(arc_path)
                                with open(target_path, "wb") as f:
                                    f.write(data)
                                self.log_msg.emit(f"已导入: {arc_path}")
                            else:
                                self.log_msg.emit(f"备份中不存在: {arc_path}，已跳过")
                        elif item_type == "dir":
                            os.makedirs(target_path, exist_ok=True)
                            count = 0
                            for info in file_infos:
                                name = info.filename
                                if arc_path and (not name.startswith(arc_path) or name == arc_path):
                                    continue
                                rel_path = name[len(arc_path):]
                                if not rel_path:
                                    continue
                                if os.path.basename(name) in exclude:
                                    continue
                                dst_file = os.path.join(target_path, rel_path)
                                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                                data = zf.read(name)
                                with open(dst_file, "wb") as f:
                                    f.write(data)
                                count += 1
                            self.log_msg.emit(f"已导入目录: {arc_path}（共{count}个文件）")
            else:
                for item in restore_items:
                    step += 1
                    self.progress_update.emit(int(step / total_steps * 95))
                    arc_path = item["arc_path"]
                    target_path = item["target_path"]
                    item_type = item["type"]
                    exclude = item.get("exclude", [])
                    src_full = os.path.join(bak_path, arc_path) if arc_path else bak_path
                    if not os.path.exists(src_full):
                        self.log_msg.emit(f"备份中不存在: {arc_path}，已跳过")
                        continue
                    if item_type == "file":
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        shutil.copy2(src_full, target_path)
                        self.log_msg.emit(f"已导入: {arc_path}")
                    elif item_type == "dir":
                        os.makedirs(target_path, exist_ok=True)
                        count = 0
                        for root, _, files in os.walk(src_full):
                            for fname in files:
                                if fname in exclude:
                                    continue
                                src_file = os.path.join(root, fname)
                                rel_path = os.path.relpath(src_file, src_full)
                                dst_file = os.path.join(target_path, rel_path)
                                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                                shutil.copy2(src_file, dst_file)
                                count += 1
                        self.log_msg.emit(f"已导入目录: {arc_path}（共{count}个文件）")
            self.progress_update.emit(100)
            self.log_msg.emit("导入完成")
            self.finished_signal.emit(True)
        except Exception as e:
            self.log_msg.emit(f"导入失败: {str(e)}")
            self.finished_signal.emit(False)
# ===================== 主窗口 =====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GT Tool")
        self.resize(900, 650)
        # 设置窗口标题栏图标
        icon_path = get_resource_path("1.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.settings = QSettings("topDress", "GT_GTA_Tool")
        self.doc_path = get_documents()
        self.game_path_legacy = self.settings.value("game_path_legacy", "")
        self.game_path_enhanced = self.settings.value("game_path_enhanced", "")
        self.config_dir = get_tool_config_dir()
        self.default_export_dir = ""
        self.use_default_export = False
        path_file = os.path.join(self.config_dir, "path.txt")
        if os.path.exists(path_file):
            try:
                with open(path_file, "r", encoding="utf-8") as f:
                    saved_path = f.read().strip()
                if saved_path and os.path.isdir(saved_path):
                    self.default_export_dir = saved_path
            except Exception:
                pass
        self.worker_backup = None
        self.worker_restore = None
        self.hw_info_text = get_hardware_info_str()
        tab_widget = QTabWidget()
        self.setCentralWidget(tab_widget)
        self.tab_backup = QWidget()
        self.tab_cache = QWidget()
        self.tab_log = QWidget()
        self.tab_reset = QWidget()
        self.tab_hwinfo = QWidget()
        self.tab_about = QWidget()
        tab_widget.addTab(self.tab_backup, "存档备份 自电台")
        tab_widget.addTab(self.tab_cache, "缓存清理")
        tab_widget.addTab(self.tab_log, "日志查看")
        tab_widget.addTab(self.tab_reset, "重置数据")
        tab_widget.addTab(self.tab_hwinfo, "硬件信息")
        tab_widget.addTab(self.tab_about, "其他信息")
        self.build_tab_backup()
        self.build_tab_cache()
        self.build_tab_log()
        self.build_tab_reset()
        self.build_tab_hwinfo()
        self.build_tab_about()
        self.refresh_game_status()
        self.log_global("GT Tool By topDress")
        self.log_global("就绪...")
    def log_global(self, txt):
        t = datetime.now().strftime("%H:%M:%S")
        self.global_log.append(f"[{t}] {txt}")
    def refresh_game_status(self):
        running, proc_name = is_game_running()
        if running:
            self.label_proc_status.setText(f"正在运行:{proc_name}")
        else:
            self.label_proc_status.setText("未运行")
        return running, proc_name
    # ==================== 备份 自电台 ====================
    def build_tab_backup(self):
        lay = QVBoxLayout(self.tab_backup)
        g_ver = QGroupBox("游戏版本选择")
        h = QHBoxLayout(g_ver)
        self.rb_legacy = QRadioButton("传承版 GTA5")
        self.rb_enhanced = QRadioButton("增强版 GTA5 Enhanced")
        self.rb_legacy.setChecked(True)
        h.addWidget(self.rb_legacy)
        h.addWidget(self.rb_enhanced)
        lay.addWidget(g_ver)
        self.g_profile = QGroupBox("Profiles 用户ID选择")
        hp = QHBoxLayout(self.g_profile)
        self.cb_profile_id = QComboBox()
        self.chk_all_profiles = QCheckBox("全选")
        self.btn_refresh_profile = QPushButton("刷新ID列表")
        self.btn_open_profile_root = QPushButton("打开Profiles根目录")
        self.btn_open_selected_id = QPushButton("打开选中ID文件夹")
        hp.addWidget(QLabel("存档ID:"))
        hp.addWidget(self.cb_profile_id)
        hp.addWidget(self.chk_all_profiles)
        hp.addWidget(self.btn_refresh_profile)
        hp.addWidget(self.btn_open_profile_root)
        hp.addWidget(self.btn_open_selected_id)
        lay.addWidget(self.g_profile)
        g_items = QGroupBox("导出/导入子项")
        h2 = QVBoxLayout(g_items)
        self.chk_save = QCheckBox("存档 Profiles [游戏进度cfg等文件]")
        self.chk_pcset = QCheckBox("设置 pc_settings.bin [全局设置画面键位等]")
        self.chk_music = QCheckBox("自电台 User Music")
        self.chk_save.setChecked(True)
        self.chk_pcset.setChecked(True)
        self.chk_music.setChecked(True)
        h2.addWidget(self.chk_save)
        h2.addWidget(self.chk_pcset)
        h2.addWidget(self.chk_music)
        
        self.btn_open_storage_dir = QPushButton("打开存储目录")
        self.btn_open_storage_dir.clicked.connect(self.open_storage_dir)
        h2.addWidget(self.btn_open_storage_dir)
        
        lay.addWidget(g_items)
        g_export_opt = QGroupBox("导出选项")
        h3 = QHBoxLayout(g_export_opt)
        self.chk_zip = QCheckBox("导出为ZIP压缩包")
        self.chk_zip.setChecked(True)
        self.chk_def_path = QCheckBox("使用默认导出路径")
        self.chk_def_path.setChecked(self.use_default_export)
        self.btn_set_def_path = QPushButton("设置默认导出目录")
        self.btn_set_def_path.clicked.connect(self.set_default_export_dir)
        h3.addWidget(self.chk_zip)
        h3.addWidget(self.chk_def_path)
        h3.addWidget(self.btn_set_def_path)
        lay.addWidget(g_export_opt)
        g_proc_status = QGroupBox("游戏进程状态")
        hproc = QHBoxLayout(g_proc_status)
        self.label_proc_status = QLabel("检测中...")
        self.btn_kill_game = QPushButton("强制结束GTA进程")
        self.btn_refresh_proc = QPushButton("刷新状态")
        hproc.addWidget(self.label_proc_status)
        hproc.addWidget(self.btn_kill_game)
        hproc.addWidget(self.btn_refresh_proc)
        lay.addWidget(g_proc_status)
        h_btn = QHBoxLayout()
        self.btn_export = QPushButton("导出备份")
        self.btn_import = QPushButton("导入还原")
        self.btn_music_batch = QPushButton("导入自电台音乐")
        self.btn_open_music_folder = QPushButton("打开自电台文件夹")
        h_btn.addWidget(self.btn_export)
        h_btn.addWidget(self.btn_import)
        h_btn.addWidget(self.btn_music_batch)
        h_btn.addWidget(self.btn_open_music_folder)
        lay.addLayout(h_btn)
        self.progress_bar = QProgressBar()
        lay.addWidget(self.progress_bar)
        self.global_log = QTextEdit()
        self.global_log.setReadOnly(True)
        lay.addWidget(self.global_log)
        self.btn_export.clicked.connect(self.run_backup)
        self.btn_import.clicked.connect(self.run_restore)
        self.btn_music_batch.clicked.connect(self.batch_import_music)
        self.btn_open_music_folder.clicked.connect(self.open_music_folder)
        self.btn_kill_game.clicked.connect(self.on_kill_gta_confirm)
        self.btn_refresh_proc.clicked.connect(self.refresh_game_status)
        self.btn_refresh_profile.clicked.connect(self.refresh_profile_combo)
        self.btn_open_profile_root.clicked.connect(self.open_profiles_root)
        self.btn_open_selected_id.clicked.connect(self.open_selected_id_folder)
        self.chk_save.stateChanged.connect(self.on_backup_item_changed)
        self.chk_pcset.stateChanged.connect(self.on_backup_item_changed)
        self.chk_music.stateChanged.connect(self.on_backup_item_changed)
        self.rb_legacy.toggled.connect(self.refresh_profile_combo)
        self.rb_enhanced.toggled.connect(self.refresh_profile_combo)
        self.chk_all_profiles.stateChanged.connect(self.on_all_profiles_toggled)
        self.refresh_profile_combo()
        self.apply_profile_related_state()
    def on_all_profiles_toggled(self):
        """全选ID复选框状态切换"""
        all_checked = self.chk_all_profiles.isChecked()
        self.cb_profile_id.setEnabled(not all_checked)
        self.btn_open_selected_id.setEnabled(not all_checked)
    def get_selected_base_path(self):
        if self.rb_legacy.isChecked():
            return os.path.join(self.doc_path, "Rockstar Games", "GTAV"), "Legacy"
        else:
            return os.path.join(self.doc_path, "Rockstar Games", "GTAV Enhanced"), "Enhanced"
    def get_selected_profile_dir(self):
        base, _ = self.get_selected_base_path()
        prof_root = os.path.join(base, "Profiles")
        sel_id = self.cb_profile_id.currentText()
        if sel_id and os.path.exists(os.path.join(prof_root, sel_id)):
            return os.path.join(prof_root, sel_id)
        return None
    def get_profiles_root(self):
        base, _ = self.get_selected_base_path()
        return os.path.join(base, "Profiles")
    def refresh_profile_combo(self):
        self.cb_profile_id.clear()
        prof_root = self.get_profiles_root()
        if not os.path.isdir(prof_root):
            self.log_global("Profiles目录不存在，可能未安装当前版本游戏或需要运行一次游戏生成")
            self.chk_all_profiles.setChecked(False)
            self.chk_all_profiles.setEnabled(False)
            self.apply_profile_related_state()
            return
        idlist = [d for d in os.listdir(prof_root) if os.path.isdir(os.path.join(prof_root, d))]
        if idlist:
            self.cb_profile_id.addItems(idlist)
            self.log_global(f"扫描到{len(idlist)}个Profiles用户ID")
            self.chk_all_profiles.setEnabled(True)
        else:
            self.chk_all_profiles.setChecked(False)
            self.chk_all_profiles.setEnabled(False)
        self.apply_profile_related_state()
    def apply_profile_related_state(self):
        """Profiles不存在时"""
        prof_root = self.get_profiles_root()
        profiles_exist = os.path.isdir(prof_root)
        if not profiles_exist:
            self.chk_save.setEnabled(True)
            self.chk_pcset.setEnabled(True)
            self.chk_music.setEnabled(True)
            self.g_profile.setEnabled(False)
            return
        self.chk_save.setEnabled(True)
        self.chk_pcset.setEnabled(True)
        self.chk_music.setEnabled(True)
        only_music = (
            self.chk_music.isChecked()
            and not self.chk_save.isChecked()
            and not self.chk_pcset.isChecked()
        )
        self.g_profile.setDisabled(only_music)
    def on_backup_item_changed(self):
        self.apply_profile_related_state()
    def open_profiles_root(self):
        pr = self.get_profiles_root()
        if os.path.exists(pr):
            os.startfile(pr)
            self.log_global(f"打开Profiles根目录: {pr}")
        else:
            QMessageBox.information(self, "GT Tool", "Profiles目录不存在,请刷新ID列表")
    def open_selected_id_folder(self):
        pd = self.get_selected_profile_dir()
        if pd and os.path.exists(pd):
            os.startfile(pd)
            self.log_global(f"打开选中ID目录:{pd}")
        else:
            QMessageBox.information(self, "GT Tool", "没有有效的存档ID目录")
    def open_music_folder(self):
        base, _ = self.get_selected_base_path()
        music_dir = os.path.join(base, "User Music")
        os.makedirs(music_dir, exist_ok=True)
        if os.path.exists(music_dir):
            os.startfile(music_dir)
            self.log_global(f"打开自电台音乐文件夹: {music_dir}")
    def open_storage_dir(self):
        """打开当前版本的存储根目录"""
        base, _ = self.get_selected_base_path()
        if os.path.exists(base):
            os.startfile(base)
            self.log_global(f"打开存储目录: {base}")
        else:
            QMessageBox.information(self, "GT Tool", "存储目录不存在，可能未安装游戏或需要运行一次游戏生成")
    def on_kill_gta_confirm(self):
        reply = QMessageBox.question(
            self,
            "GT Tool",
            "确定强制结束GTA? 未保存的游戏进度可能会丢失!",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            logs = kill_all_game_processes()
            for line in logs:
                self.log_global(line)
            self.refresh_game_status()
    def set_default_export_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择默认导出文件夹")
        if folder:
            self.default_export_dir = folder
            self.use_default_export = True
            self.chk_def_path.setChecked(True)
            path_file = os.path.join(self.config_dir, "path.txt")
            try:
                with open(path_file, "w", encoding="utf-8") as f:
                    f.write(folder)
                self.log_global(f"默认导出路径已保存: {folder}")
            except Exception as e:
                self.log_global(f"保存配置失败: {str(e)}")
    # ==================== 导出 游戏检测逻辑 ====================
    def run_backup(self):
        need_check_game = self.chk_save.isChecked() or self.chk_pcset.isChecked()
        if need_check_game:
            self.refresh_game_status()
            run, _ = is_game_running()
            if run:
                mb = QMessageBox(self)
                mb.setWindowTitle("GT Tool GTA正在运行")
                mb.setText("游戏运行中导出存档/设置可能不完整或损坏,建议保存并退出游戏后再导出")
                btn_cancel = mb.addButton("取消", QMessageBox.RejectRole)
                btn_force = mb.addButton("直接导出", QMessageBox.DestructiveRole)
                btn_close = mb.addButton("关闭游戏(强制)", QMessageBox.AcceptRole)
                mb.exec()
                clicked = mb.clickedButton()
                if clicked == btn_cancel:
                    self.log_global("取消导出")
                    return
                elif clicked == btn_close:
                    kill_all_game_processes()
                    self.log_global("已关闭GTA相关进程，请等待几秒后重试导出")
                    self.refresh_game_status()
                    return
        base, ver_tag = self.get_selected_base_path()
        prof_root = self.get_profiles_root()
        music_dir = os.path.join(base, "User Music")
        all_profiles = self.chk_all_profiles.isChecked()
        backup_items = []
        # 处理Profiles
        if os.path.isdir(prof_root):
            if all_profiles:
                # 全选所有ID导出
                id_list = [d for d in os.listdir(prof_root) if os.path.isdir(os.path.join(prof_root, d))]
                for pid in id_list:
                    pid_dir = os.path.join(prof_root, pid)
                    arc_base = f"Profiles/{pid}"
                    # 导出存档
                    if self.chk_save.isChecked():
                        for entry in os.listdir(pid_dir):
                            entry_path = os.path.join(pid_dir, entry)
                            if entry.lower() == "pc_settings.bin":
                                continue
                            backup_items.append({"src": entry_path, "arc": os.path.join(arc_base, entry)})
                    # 导出设置文件
                    if self.chk_pcset.isChecked():
                        pc_path = os.path.join(pid_dir, "pc_settings.bin")
                        if os.path.exists(pc_path):
                            backup_items.append({
                                "src": pc_path,
                                "arc": f"{arc_base}/pc_settings.bin",
                            })
            else:
                # 单个选中ID导出
                profile_dir = self.get_selected_profile_dir()
                if profile_dir and os.path.exists(profile_dir):
                    arc_base = "Profiles/" + os.path.basename(profile_dir)
                    # 导出存档
                    if self.chk_save.isChecked():
                        for entry in os.listdir(profile_dir):
                            entry_path = os.path.join(profile_dir, entry)
                            if entry.lower() == "pc_settings.bin":
                                continue
                            backup_items.append({"src": entry_path, "arc": os.path.join(arc_base, entry)})
                    # 导出设置文件
                    if self.chk_pcset.isChecked():
                        pc_set_path = os.path.join(profile_dir, "pc_settings.bin")
                        if os.path.exists(pc_set_path):
                            backup_items.append({
                                "src": pc_set_path,
                                "arc": f"{arc_base}/pc_settings.bin",
                            })
        # 处理自电台音乐
        if self.chk_music.isChecked() and os.path.exists(music_dir):
            backup_items.append({"src": music_dir, "arc": "User Music"})
        if not backup_items:
            QMessageBox.information(self, "GT Tool", "没有勾选子项或存储目录没有符合文件")
            return
        if self.chk_def_path.isChecked() and self.default_export_dir and os.path.isdir(self.default_export_dir):
            out_dir = self.default_export_dir
        else:
            out_dir = QFileDialog.getExistingDirectory(self, "选择导出保存目录")
        if not out_dir:
            self.log_global("取消导出")
            return
        cfg = {
            "src_base": base,
            "out_path": out_dir,
            "use_zip": self.chk_zip.isChecked(),
            "ver_tag": ver_tag,
            "backup_items": backup_items,
        }
        self.worker_backup = BackupWorker(cfg)
        self.worker_backup.progress_update.connect(self.progress_bar.setValue)
        self.worker_backup.log_msg.connect(self.log_global)
        self.worker_backup.finished_signal.connect(self.on_backup_done)
        self.worker_backup.start()
        self.btn_export.setEnabled(False)
    def on_backup_done(self, ok):
        self.btn_export.setEnabled(True)
        if ok:
            QMessageBox.information(self, "GT Tool", "导出完成")
    # ==================== 导入 勾选决定内容与检测 ====================
    def run_restore(self):
        need_check_game = self.chk_save.isChecked() or self.chk_pcset.isChecked()
        if need_check_game:
            self.refresh_game_status()
            run, _ = is_game_running()
            if run:
                mb = QMessageBox(self)
                mb.setWindowTitle("GT Tool GTA正在运行")
                mb.setText("游戏运行中导入存档/设置可能失败或损坏文件,建议保存并退出游戏后再导入")
                btn_cancel = mb.addButton("取消", QMessageBox.RejectRole)
                btn_force = mb.addButton("强制导入(风险)", QMessageBox.DestructiveRole)
                btn_close = mb.addButton("关闭游戏(强制)", QMessageBox.AcceptRole)
                mb.exec()
                clicked = mb.clickedButton()
                if clicked == btn_cancel:
                    self.log_global("取消导入")
                    return
                elif clicked == btn_close:
                    kill_all_game_processes()
                    self.log_global("已关闭GTA相关进程，请等待几秒后重试导入")
                    self.refresh_game_status()
                    return
        # 选择导入类型
        type_dialog = QMessageBox(self)
        type_dialog.setWindowTitle("GT Tool")
        type_dialog.setText("请选择导入类型")
        btn_zip = type_dialog.addButton("ZIP压缩包", QMessageBox.ActionRole)
        btn_folder = type_dialog.addButton("文件夹", QMessageBox.ActionRole)
        btn_cancel = type_dialog.addButton("取消", QMessageBox.RejectRole)
        type_dialog.exec()
        clicked_type = type_dialog.clickedButton()
        if clicked_type == btn_cancel:
            self.log_global("取消导入")
            return
        elif clicked_type == btn_zip:
            bak_path, _ = QFileDialog.getOpenFileName(self, "选择ZIP文件", filter="ZIP(*.zip)")
            if not bak_path:
                return
            is_zip = True
        else:
            bak_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
            if not bak_path:
                return
            is_zip = False
        # 读取备份版本标记
        bak_ver = None
        try:
            if is_zip:
                with zipfile.ZipFile(bak_path, "r") as zf:
                    if BACKUP_MARKER_FILENAME in zf.namelist():
                        txt = zf.read(BACKUP_MARKER_FILENAME).decode("utf-8")
                        for line in txt.splitlines():
                            if line.startswith("Version:"):
                                bak_ver = line.split(":")[1].strip()
            else:
                mk_path = os.path.join(bak_path, BACKUP_MARKER_FILENAME)
                if os.path.exists(mk_path):
                    with open(mk_path, "r", encoding="utf-8") as f:
                        for line in f.readlines():
                            if line.startswith("Version:"):
                                bak_ver = line.split(":")[1].strip()
        except Exception as e:
            self.log_global(f"读取备份标记失败: {e}")
        base_target, target_ver = self.get_selected_base_path()
        # 无标记时
        if not bak_ver:
            bak_ver = target_ver
            self.log_global(f"未检测到备份标记,使用当前选中版本: {bak_ver}")
        # 版本校验
        if bak_ver != target_ver:
            reply = QMessageBox.warning(
                self,
                "GT Tool",
                f"备份版本为{bak_ver} 当前选择的目标版本为{target_ver} 不兼容可能导致存档损坏\n是否继续?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                self.log_global("取消导入,版本不匹配")
                return
        user_ids = []
        user_id = None
        save_arc_prefix = ""
        music_arc_path = ""
        has_profiles_dir = False
        has_user_music_dir = False
        try:
            if is_zip:
                with zipfile.ZipFile(bak_path, "r") as zf:
                    all_names = zf.namelist()
                    for name in all_names:
                        if name.startswith("Profiles/") and name.count("/") >= 2:
                            pid = name.split("/")[1]
                            if pid not in user_ids:
                                user_ids.append(pid)
                    if user_ids:
                        save_arc_prefix = "Profiles/"
                        has_profiles_dir = True
                        user_id = user_ids[0]
                    
                    for name in all_names:
                        if name.startswith("User Music/"):
                            has_user_music_dir = True
                            music_arc_path = "User Music/"
                            break
                    
                    if not has_profiles_dir:
                        root_files = [os.path.basename(n) for n in all_names if "/" not in n]
                        if "pc_settings.bin" in root_files or any(f.startswith("SGTA5") for f in root_files):
                            user_id = self.cb_profile_id.currentText()
                            user_ids = [user_id]
                            save_arc_prefix = ""
                            self.log_global(f"检测到单用户ID存档结构，将导入到当前选中ID: {user_id}")
                    
                    if not has_user_music_dir:
                        root_files = [n for n in all_names if "/" not in n]
                        audio_count = sum(1 for f in root_files if os.path.splitext(f)[1].lower() in SUPPORT_AUDIO_EXT)
                        if audio_count > 0 and audio_count >= len(root_files) * 0.5:
                            music_arc_path = ""
                            self.log_global("检测到纯音频备份结构，将作为自电台音乐导入")
            else:
                profiles_dir = os.path.join(bak_path, "Profiles")
                if os.path.isdir(profiles_dir):
                    has_profiles_dir = True
                    save_arc_prefix = "Profiles/"
                    for d in os.listdir(profiles_dir):
                        if os.path.isdir(os.path.join(profiles_dir, d)):
                            user_ids.append(d)
                    if user_ids:
                        user_id = user_ids[0]
                
                user_music_dir = os.path.join(bak_path, "User Music")
                if os.path.isdir(user_music_dir):
                    has_user_music_dir = True
                    music_arc_path = "User Music/"
                
                if not has_profiles_dir:
                    if os.path.exists(os.path.join(bak_path, "pc_settings.bin")) or \
                       any(f.startswith("SGTA5") for f in os.listdir(bak_path) if os.path.isfile(os.path.join(bak_path, f))):
                        user_id = self.cb_profile_id.currentText()
                        user_ids = [user_id]
                        save_arc_prefix = ""
                        self.log_global(f"检测到单用户ID存档结构，将导入到当前选中ID: {user_id}")
                
                if not has_user_music_dir:
                    root_files = [f for f in os.listdir(bak_path) if os.path.isfile(os.path.join(bak_path, f))]
                    audio_count = sum(1 for f in root_files if os.path.splitext(f)[1].lower() in SUPPORT_AUDIO_EXT)
                    if audio_count > 0 and audio_count >= len(root_files) * 0.5:
                        music_arc_path = ""
                        self.log_global("检测到纯音频备份结构，将作为自电台音乐导入")
        except Exception as e:
            self.log_global(f"解析备份内容失败: {e}")
            QMessageBox.critical(self, "错误", "无法解析备份内容")
            return
        restore_items = []
        all_profiles = self.chk_all_profiles.isChecked()
        if self.chk_save.isChecked():
            if all_profiles and user_ids:
                for pid in user_ids:
                    arc_path = f"{save_arc_prefix}{pid}/" if save_arc_prefix else ""
                    target_path = os.path.join(base_target, "Profiles", pid)
                    restore_items.append({
                        "type": "dir",
                        "arc_path": arc_path,
                        "target_path": target_path,
                        "exclude": ["pc_settings.bin"]
                    })
            elif user_id:
                arc_path = f"{save_arc_prefix}{user_id}/" if save_arc_prefix else ""
                target_path = os.path.join(base_target, "Profiles", user_id)
                restore_items.append({
                    "type": "dir",
                    "arc_path": arc_path,
                    "target_path": target_path,
                    "exclude": ["pc_settings.bin"]
                })
            else:
                self.log_global("未检测到存档内容，跳过存档导入")
        if self.chk_pcset.isChecked():
            if all_profiles and user_ids:
                for pid in user_ids:
                    arc_path = f"{save_arc_prefix}{pid}/pc_settings.bin" if save_arc_prefix else "pc_settings.bin"
                    target_path = os.path.join(base_target, "Profiles", pid, "pc_settings.bin")
                    restore_items.append({
                        "type": "file",
                        "arc_path": arc_path,
                        "target_path": target_path
                    })
            elif user_id:
                arc_path = f"{save_arc_prefix}{user_id}/pc_settings.bin" if save_arc_prefix else "pc_settings.bin"
                target_path = os.path.join(base_target, "Profiles", user_id, "pc_settings.bin")
                restore_items.append({
                    "type": "file",
                    "arc_path": arc_path,
                    "target_path": target_path
                })
            else:
                self.log_global("未检测到设置文件，跳过设置导入")
        if self.chk_music.isChecked():
            target_path = os.path.join(base_target, "User Music")
            restore_items.append({
                "type": "dir",
                "arc_path": music_arc_path,
                "target_path": target_path,
                "exclude": []
            })
        if not restore_items:
            QMessageBox.information(self, "GT Tool", "没有勾选任何导入子项，或备份中无对应内容")
            return
        cfg = {
            "bak_path": bak_path,
            "target_base": base_target,
            "bak_ver": bak_ver,
            "target_ver": target_ver,
            "restore_items": restore_items
        }
        self.worker_restore = RestoreWorker(cfg)
        self.worker_restore.progress_update.connect(self.progress_bar.setValue)
        self.worker_restore.log_msg.connect(self.log_global)
        self.worker_restore.finished_signal.connect(self.on_restore_done)
        self.worker_restore.start()
        self.btn_import.setEnabled(False)
    def on_restore_done(self, ok):
        self.btn_import.setEnabled(True)
        if ok:
            QMessageBox.information(self, "GT Tool", "导入完成")
    def batch_import_music(self):
        base, _ = self.get_selected_base_path()
        music_dst = os.path.join(base, "User Music")
        files, _ = QFileDialog.getOpenFileNames(self, "选择音频文件 支持mp3,wma,m4a(AAC)")
        if not files:
            return
        unsupported = []
        for fp in files:
            ext = os.path.splitext(fp)[1].lower()
            if ext not in SUPPORT_AUDIO_EXT:
                unsupported.append(os.path.basename(fp))
        if unsupported:
            reply = QMessageBox.question(
                self,
                "GT Tool 仅兼容mp3,wma,m4a(AAC)",
                f"存在不兼容的格式 游戏可能无法播放 确定导入吗?\n{', '.join(unsupported)}",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self.log_global("已取消导入: 存在不兼容的音乐格式")
                return
        os.makedirs(music_dst, exist_ok=True)
        for fp in files:
            shutil.copy2(fp, music_dst)
        msg = f"已导入 {len(files)} 个音乐文件到 {music_dst}"
        if unsupported:
            msg += f"\n以下格式可能无法播放: {', '.join(unsupported)}"
        self.log_global(msg)
        QMessageBox.information(self, "GT Tool", msg + "\nESC-设置-声音-快速扫描 即可在游戏中收听自电台")
    # ====================缓存清理 ====================
    def build_tab_cache(self):
        lay = QVBoxLayout(self.tab_cache)
        g = QGroupBox("勾选要清理的缓存")
        vl = QVBoxLayout(g)
        self.chk_shader_legacy = QCheckBox("清理传承版着色器缓存 ShaderCache [部分机型可能无效]")
        self.chk_shader_enhanced = QCheckBox("清理增强版着色器缓存 ShaderCacheEnhanced [部分机型可能无效]")
        self.chk_shader_enhanced.setChecked(False)
        self.chk_rockstar_cache = QCheckBox("Rockstar启动器缓存")
        self.chk_rstar_logs = QCheckBox("Rockstar启动器日志 .log")
        self.chk_logs = QCheckBox("游戏日志临时文件")
        vl.addWidget(self.chk_shader_legacy)
        vl.addWidget(self.chk_shader_enhanced)
        vl.addWidget(self.chk_rockstar_cache)
        vl.addWidget(self.chk_rstar_logs)
        vl.addWidget(self.chk_logs)
        lay.addWidget(g)
        self.btn_clean_cache = QPushButton("清理选中的缓存")
        self.btn_clean_cache.clicked.connect(self.clean_cache)
        lay.addWidget(self.btn_clean_cache)
    def clean_cache(self):
        run, _ = is_game_running()
        if run:
            mb = QMessageBox(self)
            mb.setWindowTitle("GT Tool")
            mb.setText("游戏正在运行,继续吗")
            btn_cancel = mb.addButton("取消", QMessageBox.RejectRole)
            btn_force = mb.addButton("继续", QMessageBox.DestructiveRole)
            btn_close = mb.addButton("结束游戏进程", QMessageBox.AcceptRole)
            mb.exec()
            clicked = mb.clickedButton()
            if clicked == btn_cancel:
                return
            elif clicked == btn_close:
                kill_all_game_processes()
                self.log_global("已关闭GTA相关进程，请等待后重试")
                return
        local_appdata = os.environ.get("LOCALAPPDATA")
        shader_legacy_path = os.path.join(local_appdata, "Rockstar Games", "GTA V", "ShaderCache")
        shader_enhanced_path = os.path.join(local_appdata, "Rockstar Games", "GTA V", "ShaderCacheEnhanced")
        rstar_cache = os.path.expandvars("%localappdata%\\Rockstar Games\\Launcher\\Cache")
        log_path = os.path.expandvars("%documents%\\Rockstar Games\\GTAV Enhanced\\Logs")
        targets = []
        if self.chk_shader_legacy.isChecked():
            targets.append(shader_legacy_path)
        if self.chk_shader_enhanced.isChecked():
            targets.append(shader_enhanced_path)
        if self.chk_rockstar_cache.isChecked():
            targets.append(rstar_cache)
        if self.chk_logs.isChecked():
            targets.append(log_path)
        for p in targets:
            if os.path.exists(p):
                shutil.rmtree(p, ignore_errors=True)
                self.log_global(f"已清理: {p}")
        # 清理R星启动器日志
        if self.chk_rstar_logs.isChecked():
            rstar_log_dir = self.get_rstar_launcher_log_dir()
            if os.path.exists(rstar_log_dir):
                count = 0
                for fname in os.listdir(rstar_log_dir):
                    fpath = os.path.join(rstar_log_dir, fname)
                    if os.path.isfile(fpath) and fname.lower().endswith(".log"):
                        try:
                            os.remove(fpath)
                            count += 1
                        except Exception as e:
                            self.log_global(f"删除失败: {fpath} - {str(e)}")
                self.log_global(f"已清理Rockstar启动器日志，共删除 {count} 个.log 文件")
            else:
                self.log_global("Rockstar启动器日志目录不存在，跳过")
        QMessageBox.information(self, "GT Tool", "缓存清理执行完成")
    # ==================== 日志查看 ====================
    def build_tab_log(self):
        lay = QVBoxLayout(self.tab_log)
        g_game_log = QGroupBox("游戏日志")
        lay_gamelog = QVBoxLayout(g_game_log)
        h_ver = QHBoxLayout()
        self.rb_log_legacy = QRadioButton("传承版")
        self.rb_log_enhanced = QRadioButton("增强版")
        self.rb_log_legacy.setChecked(True)
        h_ver.addWidget(QLabel("游戏版本: "))
        h_ver.addWidget(self.rb_log_legacy)
        h_ver.addWidget(self.rb_log_enhanced)
        lay_gamelog.addLayout(h_ver)
        h_btn = QHBoxLayout()
        self.btn_open_log_folder = QPushButton("打开日志文件夹")
        self.btn_load_log = QPushButton("读取最新日志")
        h_btn.addWidget(self.btn_open_log_folder)
        h_btn.addWidget(self.btn_load_log)
        lay_gamelog.addLayout(h_btn)
        g_rstar_log = QGroupBox("Rockstar启动器日志")
        lay_rlog = QHBoxLayout(g_rstar_log)
        self.btn_open_rstar_log_folder = QPushButton("打开日志文件夹")
        self.btn_read_rstar_latest = QPushButton("读取最新日志")
        lay_rlog.addWidget(self.btn_open_rstar_log_folder)
        lay_rlog.addWidget(self.btn_read_rstar_latest)
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        lay.addWidget(g_game_log)
        lay.addWidget(g_rstar_log)
        lay.addWidget(self.log_viewer)
        self.btn_open_log_folder.clicked.connect(self.open_log_folder)
        self.btn_load_log.clicked.connect(self.load_log_file)
        self.btn_open_rstar_log_folder.clicked.connect(self.open_rstar_log_folder)
        self.btn_read_rstar_latest.clicked.connect(self.load_rstar_latest_log)
    def get_log_base_path(self):
        if self.rb_log_legacy.isChecked():
            return os.path.join(self.doc_path, "Rockstar Games", "GTAV")
        else:
            return os.path.join(self.doc_path, "Rockstar Games", "GTAV Enhanced")
    def open_log_folder(self):
        base = self.get_log_base_path()
        log_dir = os.path.join(base, "Logs")
        os.makedirs(log_dir, exist_ok=True)
        os.startfile(log_dir)
    def load_log_file(self):
        base = self.get_log_base_path()
        log_dir = os.path.join(base, "Logs")
        if not os.path.exists(log_dir):
            self.log_viewer.setText("日志目录不存在")
            return
        files = [os.path.join(log_dir, f) for f in os.listdir(log_dir)]
        if not files:
            self.log_viewer.setText("空空如也, 建议去崩溃几次游戏再来查看哦")
            return
        latest = max(files, key=os.path.getmtime)
        with open(latest, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        self.log_viewer.setText(content[:3000])
        self.log_global(f"加载游戏日志文件: {latest}")
    def get_rstar_launcher_log_dir(self):
        return os.path.join(self.doc_path, "Rockstar Games", "Launcher")
    def open_rstar_log_folder(self):
        d = self.get_rstar_launcher_log_dir()
        if os.path.exists(d):
            os.startfile(d)
        else:
            self.log_viewer.setText(f"Rockstar启动器日志目录不存在: {d}")
    def load_rstar_latest_log(self):
        d = self.get_rstar_launcher_log_dir()
        if not os.path.exists(d):
            self.log_viewer.setText(f"Rockstar启动器日志目录不存在: {d}")
            return
        log_files = [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(".log")]
        if not log_files:
            self.log_viewer.setText("Rockstar启动器日志目录下没有log文件")
            return
        latest_log = max(log_files, key=os.path.getmtime)
        try:
            with open(latest_log, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            self.log_viewer.setText(f"==== 读取日志：{os.path.basename(latest_log)} ====\n\n{text[:3000]}")
            self.log_global(f"加载Rockstar启动器日志：{latest_log}")
        except Exception as e:
            self.log_viewer.setText(f"读取Rockstar日志失败: {str(e)}")
    # ==================== 重置数据 ====================
    def build_tab_reset(self):
        lay = QVBoxLayout(self.tab_reset)
        g_ver_reset = QGroupBox("目标游戏版本")
        hvr = QHBoxLayout(g_ver_reset)
        self.rb_reset_legacy = QRadioButton("传承版 GTA5")
        self.rb_reset_enhanced = QRadioButton("增强版 GTA5 Enhanced")
        self.rb_reset_legacy.setChecked(True)
        hvr.addWidget(self.rb_reset_legacy)
        hvr.addWidget(self.rb_reset_enhanced)
        lay.addWidget(g_ver_reset)
        g = QGroupBox("重置选项")
        vl = QVBoxLayout(g)
        self.chk_reset_pcset = QCheckBox("删除pc_settings.bin，重置设置画面键位")
        self.chk_clear_offline_save = QCheckBox("清空用户存档数据")
        tip_label = QLabel("清空用户存档数据仅保留pc_settings.bin，所有存档及其他数据将被删除")
        tip_label.setStyleSheet("color:#dd2222;")
        self.chk_reset_rlauncher = QCheckBox("清空Rockstar启动器配置")
        vl.addWidget(self.chk_reset_pcset)
        vl.addWidget(self.chk_clear_offline_save)
        vl.addWidget(tip_label)
        vl.addWidget(self.chk_reset_rlauncher)
        lay.addWidget(g)
        self.btn_reset_exec = QPushButton("执行重置")
        self.btn_reset_exec.clicked.connect(self.do_reset)
        lay.addWidget(self.btn_reset_exec)
    def get_reset_base_path(self):
        if self.rb_reset_legacy.isChecked():
            return os.path.join(self.doc_path, "Rockstar Games", "GTAV")
        else:
            return os.path.join(self.doc_path, "Rockstar Games", "GTAV Enhanced")
    def do_reset(self):
        run, _ = is_game_running()
        if run:
            QMessageBox.warning(self, "GT Tool", "游戏运行中无法执行操作")
            return
        reply = QMessageBox.question(
            self,
            "GT Tool",
            "确认执行选中操作?无法撤销",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        base = self.get_reset_base_path()
        profile_root = os.path.join(base, "Profiles")
        # 重置设置
        if self.chk_reset_pcset.isChecked() and os.path.exists(profile_root):
            for d in os.listdir(profile_root):
                bin_path = os.path.join(profile_root, d, "pc_settings.bin")
                if os.path.exists(bin_path):
                    os.remove(bin_path)
                    self.log_global(f"删除: {bin_path}")
        # 清空用户存档数据
        if self.chk_clear_offline_save.isChecked() and os.path.exists(profile_root):
            del_count = 0
            for user_dir in os.listdir(profile_root):
                user_path = os.path.join(profile_root, user_dir)
                if not os.path.isdir(user_path):
                    continue
                for entry in os.listdir(user_path):
                    entry_path = os.path.join(user_path, entry)
                    if entry.lower() == "pc_settings.bin":
                        continue
                    try:
                        if os.path.isfile(entry_path):
                            os.remove(entry_path)
                            del_count += 1
                        elif os.path.isdir(entry_path):
                            shutil.rmtree(entry_path, ignore_errors=True)
                            del_count += 1
                    except Exception as e:
                        self.log_global(f"删除失败: {entry_path} - {str(e)}")
            self.log_global(f"已清空用户存档，共删除 {del_count} 项")
        if self.chk_reset_rlauncher.isChecked():
            rstar_cfg = os.path.expandvars("%localappdata%\\Rockstar Games\\Launcher\\settings.json")
            if os.path.exists(rstar_cfg):
                os.remove(rstar_cfg)
                self.log_global(f"已重置Rockstar启动器配置: {rstar_cfg}")
        QMessageBox.information(self, "GT Tool", "操作执行完成")
    # ==================== 硬件信息 ====================
    def build_tab_hwinfo(self):
        lay = QVBoxLayout(self.tab_hwinfo)
        self.hw_text = QTextEdit()
        self.hw_text.setReadOnly(True)
        self.hw_text.setStyleSheet("font-family: Consolas, 'Microsoft YaHei', monospace; font-size: 13px;")
        lay.addWidget(self.hw_text)
        self.hw_text.setText(self.hw_info_text)

    def open_donate_image(self):
        img_path = get_resource_path("2.png")
        if os.path.exists(img_path):
            os.startfile(img_path)
        else:
            QMessageBox.information(self, "GT Tool", "无法打开捐赠图片>_<")

    # ==================== 其他信息 ====================
    def build_tab_about(self):
        lay = QVBoxLayout(self.tab_about)
        lay.setAlignment(Qt.AlignTop)
        info_label = QLabel(
            "- GTA5 GT Tool\n"
            "- By topDress\n"
            "- Compile time 2026.10.4 R1\n"
            "- 缓存配置目录: 文档/GT Tool\n"
            "- QQ 3314771397"
        )
        info_label.setOpenExternalLinks(False)
        lay.addWidget(info_label)
        h1 = QHBoxLayout()
        btn_bilibili = QPushButton("Bilibili")
        btn_bilibili.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://space.bilibili.com/1724319756")))
        btn_douyin = QPushButton("抖音")
        btn_douyin.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://v.douyin.com/jXY2qzJ3-ts/")))
        btn_kuaishou = QPushButton("快手")
        btn_kuaishou.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://v.kuaishou.com/J5DmkFm8")))
        h1.addWidget(btn_bilibili)
        h1.addWidget(btn_douyin)
        h1.addWidget(btn_kuaishou)
        lay.addLayout(h1)
        h2 = QHBoxLayout()
        btn_qq_group = QPushButton("QQ交流群")
        btn_qq_group.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://qm.qq.com/q/2cHQu9tMjy")))
        btn_download = QPushButton("GT Tool")
        btn_download.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://1829098532.share.123pan.cn/123pan/4HUbjv-kyAG3")))
        btn_gtaweb = QPushButton("GTA Web攻略站")
        btn_gtaweb.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://gtaweb.eu/")))
        h2.addWidget(btn_qq_group)
        h2.addWidget(btn_download)
        h2.addWidget(btn_gtaweb)
        lay.addLayout(h2)
        h3 = QHBoxLayout()
        btn_rockstar = QPushButton("Rockstar Games")
        btn_rockstar.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.rockstargames.com/")))
        h3.addWidget(btn_rockstar)
        h3.addStretch()
        lay.addLayout(h3)
        h4 = QHBoxLayout()
        btn_donate = QPushButton("捐赠支持")
        btn_donate.clicked.connect(self.open_donate_image)
        h4.addWidget(btn_donate)
        h4.addStretch()
        lay.addLayout(h4)
        lay.addStretch()
if __name__ == "__main__":
    app = QApplication()
    win = MainWindow()
    win.show()
    app.exec()
