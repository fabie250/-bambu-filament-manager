import sys
import re
import json
import os
import time
import datetime
import urllib.request
import urllib.error
import webbrowser
import ctypes
from ctypes import wintypes
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image
import customtkinter as ctk

# ==============================================================================
# 模块 0: 全局版本常量、加速接口与网盘备用配置 [START]
# ==============================================================================
CURRENT_VERSION = "v3.0.5"
IS_PRE_RELEASE = False
GITHUB_REPO = "fabie250/-bambu-filament-manager"
UPDATE_API_URL = "http://mpdfyy.cn/api/latest-version"

# 备用网盘直链
BACKUP_PAN_URL = "https://1823958828.share.123pan.cn/123pan/bTEGjv-hWTS3?pwd=p3lJ"

# 国内文件加速型镜像列表（自动轮询与故障转移）
GH_PROXY_NODES = [
    "https://gh-proxy.com/",
    "https://ghproxy.net/",
    "https://ghproxy.homeboyc.cn/",
    "https://github.akams.cn/",
    "https://ghfast.top/"
]
# ==============================================================================
# 模块 0: 全局版本常量、加速接口与网盘备用配置 [END]
# ==============================================================================


# ==============================================================================
# 模块 1: 语义化版本比对与解析算法 [START]
# ==============================================================================
def parse_version_tuple(ver_str: str):
    clean_str = ver_str.strip().lower().lstrip('v')
    is_beta = 0 if any(k in clean_str for k in ["beta", "rc", "alpha"]) else 1
    nums = re.findall(r'\d+', clean_str)
    major = int(nums[0]) if len(nums) > 0 else 0
    minor = int(nums[1]) if len(nums) > 1 else 0
    patch = int(nums[2]) if len(nums) > 2 else 0
    return (major, minor, patch, is_beta)

def is_newer_version(online_ver: str, current_ver: str) -> bool:
    try:
        return parse_version_tuple(online_ver) > parse_version_tuple(current_ver)
    except Exception:
        return False
# ==============================================================================
# 模块 1: 语义化版本比对与解析算法 [END]
# ==============================================================================


# ==============================================================================
# 模块 2: 基础路径、资源定位与全局日志系统 [START]
# ==============================================================================
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
MAPPING_CACHE_FILE = os.path.join(BASE_DIR, "slot_mapping.json")
LOG_FILE = os.path.join(BASE_DIR, "log.txt")

def write_log(content):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {content}\n")
    except Exception:
        pass

LOGO_PNG_FILE = resource_path("bambu_logo.png")
LOGO_ICO_FILE = resource_path("bambu_logo.ico")
FONT_REGULAR_PATH = resource_path("MiSans-Regular.ttf")
FONT_BOLD_PATH = resource_path("MiSans-Bold.ttf")
# ==============================================================================
# 模块 2: 基础路径、资源定位与全局日志系统 [END]
# ==============================================================================


# ==============================================================================
# 模块 3: Windows 凭据管理器安全存储 [START]
# ==============================================================================
KEYRING_SERVICE_NAME = "BambuFilamentStudio"
KEYRING_ACCOUNT_NAME = "script_api_key"

try:
    import keyring
    import keyring.backends.Windows
    keyring.set_keyring(keyring.backends.Windows.WinVaultKeyring())
    HAS_KEYRING = True
except Exception:
    HAS_KEYRING = False
# ==============================================================================
# 模块 3: Windows 凭据管理器安全存储 [END]
# ==============================================================================


# ==============================================================================
# 模块 4: Windows 原生渲染优化与字体池挂载 [START]
# ==============================================================================
def enable_windows_rendering_optimizations(root=None):
    if os.name != "nt":
        return
    try:
        dwmapi = ctypes.windll.dwmapi
        if root is not None:
            hwnd = root.winfo_id()
            DWMWA_TRANSITIONS_FORCEDISABLED = 3
            value = ctypes.c_int(1)
            dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TRANSITIONS_FORCEDISABLED, ctypes.byref(value), ctypes.sizeof(value))
        write_log("🖥️ [渲染优化] Windows DWM 合成/窗口过渡优化已启用")
    except Exception as e:
        write_log(f"⚠️ [渲染优化] DWM 优化不可用: {e}")

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

def register_font_to_windows_pool(font_path):
    if os.path.exists(font_path):
        try:
            FR_PRIVATE = 0x10
            res = ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)
            write_log(f"🔤 [字体池] 注册字体文件: {os.path.basename(font_path)} (状态码: {res})")
        except Exception as e:
            write_log(f"❌ [字体池] 注册失败: {e}")

register_font_to_windows_pool(FONT_REGULAR_PATH)
register_font_to_windows_pool(FONT_BOLD_PATH)

try:
    if os.path.exists(FONT_REGULAR_PATH):
        ctk.FontManager.load_font(FONT_REGULAR_PATH)
    if os.path.exists(FONT_BOLD_PATH):
        ctk.FontManager.load_font(FONT_BOLD_PATH)
except Exception:
    pass
# ==============================================================================
# 模块 4: Windows 原生渲染优化与字体池挂载 [END]
# ==============================================================================


# ==============================================================================
# 模块 5: 配置文件与网络 API 请求通信 [START]
# ==============================================================================
DEFAULT_CONFIG = {
    "server_url": "http://127.0.0.1:8000/api/ingest/script-report",
    "filaments_url": "http://127.0.0.1:8000/api/ingest/script-filaments",
    "api_key": "",
    "filament_id": 1,
    "selected_font": "MiSans (小米澎湃)",
    "auto_watcher_enabled": True,
    "developer_mode": False,
    "debug_log_enabled": False,
    "window_width": 1160,
    "window_height": 800,
    "last_slice_weight": 0.0,
    "update_channel": "Release (正式版)",
    "skipped_version": ""
}

def get_secure_api_key():
    if HAS_KEYRING:
        try:
            key = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_NAME)
            if key:
                return key
        except Exception:
            pass
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get("api_key", "")
        except Exception:
            pass
    return ""

def set_secure_api_key(api_key):
    if HAS_KEYRING:
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_NAME, api_key)
            return True
        except Exception as e:
            write_log(f"保存凭据到 Windows 失败: {e}")
    return False

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_cfg = json.load(f)
                config.update(user_cfg)
        except Exception:
            pass
    
    secure_key = get_secure_api_key()
    if secure_key:
        config["api_key"] = secure_key
    return config

def save_config(config):
    try:
        api_key = config.get("api_key", "")
        saved_to_keyring = set_secure_api_key(api_key)

        cfg_to_save = config.copy()
        if saved_to_keyring:
            cfg_to_save["api_key"] = "[Encrypted in Windows Credential Manager]"
            
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg_to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        write_log(f"保存配置失败: {e}")

def api_request(url, api_key="", method="GET", data=None):
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        req_data = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(f"{url}?_t={int(time.time()*1000)}", data=req_data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=6) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        write_log(f"API请求失败 [{method} {url}]: {e}")
        return None
# ==============================================================================
# 模块 5: 配置文件与网络 API 请求通信 [END]
# ==============================================================================


# ==============================================================================
# 模块 6: UI 配色方案与字体映射 [START]
# ==============================================================================
COLOR_BG_MAIN = "#0C0C0E"       
COLOR_CARD_BG = "#16161A"       
COLOR_CARD_BORDER = "#26262B"   
COLOR_BAMBU_GREEN = "#00AE42"   
COLOR_TEXT_PRIMARY = "#FFFFFF" 
COLOR_TEXT_MUTED = "#8E8E93"   
COLOR_BADGE_RED = "#FA3534"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def map_font_family(cfg_font_str):
    if "MiSans" in cfg_font_str:
        return "MiSans"
    elif "YaHei" in cfg_font_str or "微软雅黑" in cfg_font_str:
        return "Microsoft YaHei UI"
    elif "Segoe" in cfg_font_str:
        return "Segoe UI Variable Text"
    return "MiSans"
# ==============================================================================
# 模块 6: UI 配色方案与字体映射 [END]
# ==============================================================================


# ==============================================================================
# 模块 7: 切片文件后台监听与多盘防抖引擎 [START]
# ==============================================================================
class BambuFileWatcher(threading.Thread):
    def __init__(self, app_instance):
        super().__init__()
        self.daemon = True
        self.app = app_instance
        self.running = False
        self.plate_cooldown = {}

    def run(self):
        self.running = True
        write_log("🚀 全局切片监控后台线程已启动 (独立分盘智能排队模式)...")
        
        appdata_local = os.getenv("LOCALAPPDATA", "")
        temp_dir = os.getenv("TEMP", "")
        
        watch_dirs = [
            os.path.join(appdata_local, "BambuStudio"),
            os.path.join(appdata_local, "OrcaSlicer"),
            temp_dir
        ]

        while self.running:
            try:
                current_cfg = self.app.cfg
                if current_cfg.get("auto_watcher_enabled", True):
                    now_time = time.time()
                    self.plate_cooldown = {k: v for k, v in self.plate_cooldown.items() if (now_time - v) < 30}

                    for w_dir in watch_dirs:
                        if not os.path.exists(w_dir):
                            continue
                        
                        for root, _, files in os.walk(w_dir):
                            for file in files:
                                f_lower = file.lower()
                                if f_lower.endswith(".tmp") or f_lower.endswith(".log") or "webcache" in root.lower() or f_lower.endswith(".3mf"):
                                    continue

                                if ".gcode" in f_lower:
                                    file_path = os.path.join(root, file)
                                    try:
                                        mtime = os.path.getmtime(file_path)
                                        if (now_time - mtime) < 3.5:
                                            slot_weights = get_bambu_project_info_strict(file_path)
                                            if slot_weights and sum(slot_weights) > 0:
                                                model_base_name = extract_model_name_from_file(file_path)
                                                plate_id = "1"
                                                p_match = re.search(r'plate_(\d+)', file, re.IGNORECASE)
                                                if p_match:
                                                    plate_id = p_match.group(1)
                                                else:
                                                    num_parts = re.findall(r'\d+', file)
                                                    if len(num_parts) >= 2:
                                                        plate_id = num_parts[-1]

                                                plate_fingerprint = f"{model_base_name}_plate_{plate_id}_{slot_weights}"
                                                last_t = self.plate_cooldown.get(plate_fingerprint, 0)
                                                
                                                if (now_time - last_t) > 4.0:
                                                    self.plate_cooldown[plate_fingerprint] = now_time
                                                    curr_total_w = round(sum(slot_weights), 2)
                                                    display_name = f"{model_base_name}_盘{plate_id}"
                                                    
                                                    write_log(f"🎯 [捕获切片盘] 任务: {display_name} | 耗材克重: {slot_weights} (总重: {curr_total_w}g)")
                                                    self.app.after(100, lambda fp=file_path, sw=slot_weights, mn=display_name: 
                                                        self.app.enqueue_auto_deduct(fp, sw, mn))
                                    except Exception:
                                        pass
            except Exception:
                pass
            time.sleep(1.2)
# ==============================================================================
# 模块 7: 切片文件后台监听与多盘防抖引擎 [END]
# ==============================================================================


# ==============================================================================
# 模块 8: 客户端主界面逻辑与核心组件 [START]
# ==============================================================================
class HyperOSFilamentApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.cfg = load_config()
        self.font_family = map_font_family(self.cfg.get("selected_font", "MiSans (小米澎湃)"))
        self.is_dialog_showing = False
        self.deduct_queue = []
        self._is_first_load = True
        self.latest_release_info = None
        self.current_user_name = "未登录"

        write_log(f"🖥️ [初始化] 启动界面, 当前全局字体设定: {self.font_family}")

        self.title("拓竹耗材台账助手")
        
        saved_w = self.cfg.get("window_width", 1160)
        saved_h = self.cfg.get("window_height", 800)
        self.geometry(f"{saved_w}x{saved_h}")
        self.minsize(960, 640)
        self.configure(fg_color=COLOR_BG_MAIN)
        enable_windows_rendering_optimizations(self)

        if os.path.exists(LOGO_ICO_FILE):
            try:
                self.iconbitmap(LOGO_ICO_FILE)
            except Exception:
                pass

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._resize_after_id = None
        self._is_resizing = False
        self._last_resize_geometry = None
        self.bind("<Configure>", self._on_window_configure, add="+")
        self._apply_windows_resize_optimizations()

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.content_area = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content_area.grid(row=0, column=0, sticky="nsew", padx=24, pady=(16, 10))
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

        self.views = {}
        self.registered_widgets_font = []
        self.init_dashboard_view()

        # 底部悬浮导航条
        self.bottom_nav = ctk.CTkFrame(self, height=60, corner_radius=30, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        self.bottom_nav.grid(row=1, column=0, pady=(0, 16), padx=30)

        self.btn_nav_dashboard = self.create_nav_item("📦  耗材台账", "dashboard")
        self.btn_nav_dashboard.pack(side="left", padx=12, pady=6)

        self.btn_nav_settings = self.create_nav_item("⚙️  服务设置", "settings")
        self.btn_nav_settings.pack(side="left", padx=12, pady=6)

        self.btn_nav_logs = self.create_nav_item("📜  运行日志", "logs")
        self.btn_nav_logs.pack(side="left", padx=12, pady=6)

        self.switch_tab("dashboard")

        self.watcher = BambuFileWatcher(self)
        self.watcher.start()

        threading.Thread(target=self.silent_check_update, daemon=True).start()
        threading.Thread(target=self.fetch_user_info_async, daemon=True).start()

    def _apply_windows_resize_optimizations(self):
        if os.name != "nt":
            return
        try:
            hwnd = self.winfo_id()
            user32 = ctypes.windll.user32
            GWL_STYLE = -16
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            WS_CLIPCHILDREN = 0x02000000
            WS_CLIPSIBLINGS = 0x04000000
            new_style = style | WS_CLIPCHILDREN | WS_CLIPSIBLINGS
            if new_style != style:
                user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)

            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            SWP_FRAMECHANGED = 0x0020
            user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER |
                SWP_NOACTIVATE | SWP_FRAMECHANGED
            )
        except Exception:
            pass

    def _on_window_configure(self, event):
        try:
            if event.widget is not self:
                return
            geometry = (event.width, event.height)
            if geometry == self._last_resize_geometry:
                return
            self._last_resize_geometry = geometry
            self._is_resizing = True

            if self._resize_after_id is not None:
                try:
                    self.after_cancel(self._resize_after_id)
                except Exception:
                    pass
            self._resize_after_id = self.after(120, self._finish_window_resize)
        except Exception:
            pass

    def _finish_window_resize(self):
        self._resize_after_id = None
        self._is_resizing = False

    def on_close(self):
        try:
            if self._resize_after_id is not None:
                self.after_cancel(self._resize_after_id)
                self._resize_after_id = None
        except Exception:
            pass
        try:
            self.cfg["window_width"] = self.winfo_width()
            self.cfg["window_height"] = self.winfo_height()
            save_config(self.cfg)
        except Exception:
            pass
        self.destroy()

    def get_font(self, size, weight="normal"):
        return ctk.CTkFont(family=self.font_family, size=size + 1, weight=weight)

    def register_widget_font(self, widget, size, weight="normal"):
        self.registered_widgets_font.append((widget, size, weight))

    def _refresh_all_fonts(self):
        for widget, size, weight in list(self.registered_widgets_font):
            try:
                if widget.winfo_exists():
                    widget.configure(font=self.get_font(size, weight))
            except Exception:
                pass

        try:
            current_view = next(
                (view for view in self.views.values() if view.winfo_ismapped()),
                None
            )
            if current_view is not None:
                self._refresh_font_family_only(current_view)
            self._refresh_font_family_only(self.bottom_nav)
        except Exception:
            pass

    def _refresh_font_family_only(self, widget):
        try:
            font_widgets = (ctk.CTkLabel, ctk.CTkButton, ctk.CTkEntry, ctk.CTkTextbox,
                            ctk.CTkComboBox, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkSwitch,
                            ctk.CTkSlider, ctk.CTkProgressBar)
            if isinstance(widget, font_widgets):
                current_font = widget.cget("font")
                if current_font is not None:
                    try:
                        current_size = abs(int(current_font.cget("size")))
                    except Exception:
                        current_size = 13
                    try:
                        current_weight = current_font.cget("weight")
                    except Exception:
                        current_weight = "normal"
                    widget.configure(font=ctk.CTkFont(family=self.font_family, size=current_size, weight=current_weight))
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._refresh_font_family_only(child)
        except Exception:
            pass

    def create_nav_item(self, text, tab_name):
        btn = ctk.CTkButton(
            self.bottom_nav, text=text, font=self.get_font(13, "bold"),
            width=120, height=40, corner_radius=20, fg_color="transparent",
            text_color=COLOR_TEXT_MUTED, hover_color=COLOR_CARD_BORDER,
            command=lambda: self.switch_tab(tab_name)
        )
        self.register_widget_font(btn, 13, "bold")
        return btn

    def switch_tab(self, tab_name):
        if tab_name not in self.views:
            if tab_name == "dashboard":
                self.init_dashboard_view()
            elif tab_name == "settings":
                self.init_settings_view()
            elif tab_name == "logs":
                self.init_logs_view()

        for name, view in self.views.items():
            if name == tab_name:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_forget()

        nav_map = {
            "dashboard": self.btn_nav_dashboard,
            "settings": self.btn_nav_settings,
            "logs": self.btn_nav_logs
        }

        for name, btn in nav_map.items():
            btn.configure(fg_color=COLOR_BAMBU_GREEN if name == tab_name else "transparent",
                          text_color="#FFFFFF" if name == tab_name else COLOR_TEXT_MUTED)

        if tab_name == "dashboard" and self._is_first_load:
            self._is_first_load = False
            self.refresh_dashboard()
        elif tab_name == "logs":
            self.load_logs()

    # --------------------------------------------------------------------------
    # 子功能: 账号/API 校验与用户名动态显示 [START]
    # --------------------------------------------------------------------------
    def fetch_user_info_async(self):
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        if not base_url or not api_key:
            self.update_user_display("未配置/未连接", False)
            return

        user_info_url = f"{base_url}/api/ingest/script-user-info"
        res = api_request(user_info_url, api_key=api_key, method="GET")
        if res and res.get("status") == "success":
            username = res.get("username", "已连接用户")
            self.current_user_name = username
            self.update_user_display(username, True)
        else:
            self.current_user_name = "未连接"
            self.update_user_display("未连接或 Key 无效", False)

    def update_user_display(self, username, is_connected):
        def _update():
            if hasattr(self, 'lbl_user_status') and self.lbl_user_status.winfo_exists():
                if is_connected:
                    self.lbl_user_status.configure(text=f"🟢 账号: {username}", text_color=COLOR_BAMBU_GREEN, fg_color="#0D2B1A")
                else:
                    self.lbl_user_status.configure(text=f"⚪ 状态: {username}", text_color=COLOR_TEXT_MUTED, fg_color="#202025")
            if hasattr(self, 'lbl_settings_user') and self.lbl_settings_user.winfo_exists():
                if is_connected:
                    self.lbl_settings_user.configure(text=f"🟢 当前已认证用户: {username}", text_color=COLOR_BAMBU_GREEN)
                else:
                    self.lbl_settings_user.configure(text="⚪ 当前未连接或 API Key 无效", text_color=COLOR_TEXT_MUTED)
        self.after(0, _update)

    def open_quick_login_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("账号登录换取 API Key")
        modal.geometry("420x360")
        modal.resizable(False, False)
        modal.attributes('-topmost', True)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(container, text="🔑 登录并一键获取 Key", font=self.get_font(17, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(container, text="输入网页端注册的账号密码，将自动生成并绑定永久 API Key", font=self.get_font(10), text_color=COLOR_TEXT_MUTED, wraplength=350, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        u_box = ctk.CTkFrame(container, fg_color="transparent")
        u_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(u_box, text="用户名 / 账号:", font=self.get_font(12, "bold")).pack(anchor="w")
        entry_user = ctk.CTkEntry(u_box, height=36, corner_radius=8, font=self.get_font(12), placeholder_text="请输入用户名")
        entry_user.pack(fill="x", pady=(2, 0))

        p_box = ctk.CTkFrame(container, fg_color="transparent")
        p_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(p_box, text="密码:", font=self.get_font(12, "bold")).pack(anchor="w")
        entry_pwd = ctk.CTkEntry(p_box, height=36, corner_radius=8, show="*", font=self.get_font(12), placeholder_text="请输入密码")
        entry_pwd.pack(fill="x", pady=(2, 0))

        lbl_tip = ctk.CTkLabel(container, text="", font=self.get_font(11), text_color="#EF4444")
        lbl_tip.pack(anchor="w", padx=16, pady=(4, 0))

        def do_quick_login():
            user = entry_user.get().strip()
            pwd = entry_pwd.get().strip()
            if not user or not pwd:
                lbl_tip.configure(text="⚠️ 请输入完整的用户名与密码！")
                return

            base_url = self.entry_server_url.get().strip().replace('/api/ingest/script-report', '')
            if not base_url:
                lbl_tip.configure(text="⚠️ 请先在设置页填写正确的扣减上报地址！")
                return

            lbl_tip.configure(text="正在连接服务端校验...", text_color=COLOR_TEXT_MUTED)
            modal.update_idletasks()

            def _login_thread():
                try:
                    login_url = f"{base_url}/api/auth/quick-api-key"
                    res = api_request(login_url, method="POST", data={"username": user, "password": pwd})
                    if res and res.get("status") == "success":
                        key = res.get("api_key")
                        name = res.get("username")
                        self.after(0, lambda: self.apply_quick_api_key(key, name, modal))
                    else:
                        self.after(0, lambda: lbl_tip.configure(text="❌ 账号或密码错误，请检查！", text_color="#EF4444"))
                except Exception as e:
                    self.after(0, lambda err=str(e): lbl_tip.configure(text=f"❌ 连接失败: {err}", text_color="#EF4444"))

            threading.Thread(target=_login_thread, daemon=True).start()

        ctk.CTkButton(
            container, text="✔ 立即获取并绑定", height=38, corner_radius=12,
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32",
            font=self.get_font(13, "bold"), command=do_quick_login
        ).pack(fill="x", padx=16, pady=(12, 12), side="bottom")

    def apply_quick_api_key(self, api_key, username, modal_window):
        self.entry_api_key.delete(0, tk.END)
        self.entry_api_key.insert(0, api_key)
        self.save_settings(silent=True)
        self.fetch_user_info_async()
        messagebox.showinfo("成功", f"🎉 欢迎回来，{username}！\n已成功获取专属 API Key 并加密存储。")
        modal_window.destroy()
    # --------------------------------------------------------------------------
    # 子功能: 账号/API 校验与用户名动态显示 [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 智能更新检测与多镜像故障转移下载 [START]
    # --------------------------------------------------------------------------
    def check_github_releases(self):
        channel = self.cfg.get("update_channel", "Release (正式版)")
        url = f"{UPDATE_API_URL}?_t={int(time.time()*1000)}"
        req = urllib.request.Request(url, headers={"User-Agent": "BambuStudio-Client"})
        
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    releases = json.loads(resp.read().decode('utf-8'))
                    if not isinstance(releases, list):
                        return (False, None, "INVALID_RESPONSE")
                    for r in releases:
                        if "Release" in channel and r.get("prerelease", False):
                            continue
                        online_tag = r.get("tag_name", "").strip()
                        if is_newer_version(online_tag, CURRENT_VERSION):
                            return (True, r, "OK")
                    return (False, None, "LATEST")
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    return (False, None, "RATE_LIMIT")
                return (False, None, f"HTTP_{e.code}")
            except Exception as e:
                if attempt == 1:
                    return (False, None, str(e))
                time.sleep(1)

    def silent_check_update(self):
        try:
            has_update, rel, code = self.check_github_releases()
            if has_update and rel:
                self.latest_release_info = rel
                online_tag = rel.get("tag_name", "")
                self.after(100, self.show_new_badge)
                if self.cfg.get("skipped_version", "") != online_tag:
                    self.after(600, lambda: self.open_update_modal(is_startup=True))
            elif code == "RATE_LIMIT":
                write_log("ℹ️ GitHub API 触发限流，已由服务器缓存保护并跳过")
        except Exception as e:
            write_log(f"静默检查异常: {e}")

    def manual_check_update(self):
        self.save_settings(silent=True)
        def _worker():
            has_update, rel, code = self.check_github_releases()
            if has_update and rel:
                self.latest_release_info = rel
                self.after(50, self.show_new_badge)
                self.after(50, lambda: self.open_update_modal(is_startup=False))
            elif code == "LATEST":
                self.after(50, lambda: messagebox.showinfo("检查更新", f"当前已是最新版本 ({CURRENT_VERSION})！"))
            elif code == "RATE_LIMIT":
                self.after(50, lambda: messagebox.showwarning("提示", "访问频次触发限制（403）！\n请稍后再试或点击【网盘备用下载】。"))
            else:
                self.after(50, lambda: messagebox.showerror("错误", f"检查更新失败: {code}"))
        threading.Thread(target=_worker, daemon=True).start()

    def show_new_badge(self):
        if hasattr(self, 'badge_new') and self.badge_new.winfo_exists():
            self.badge_new.pack(side="left", padx=(6, 0))

    def open_update_modal(self, is_startup=False):
        if not self.latest_release_info:
            return

        tag_name = self.latest_release_info.get("tag_name", "新版本")
        body = self.latest_release_info.get("body", "无更新说明。")
        html_url = self.latest_release_info.get("html_url", f"https://github.com/{GITHUB_REPO}/releases")

        raw_download_url = None
        asset_exe_name = None
        for asset in self.latest_release_info.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".exe") and "standalone" not in name.lower() and "单机" not in name and "server" not in name.lower():
                raw_download_url = asset.get("browser_download_url")
                asset_exe_name = name
                break
        
        if not raw_download_url:
            for asset in self.latest_release_info.get("assets", []):
                name = asset.get("name", "")
                if name.endswith(".exe") and "server" not in name.lower():
                    raw_download_url = asset.get("browser_download_url")
                    asset_exe_name = name
                    break

        modal = ctk.CTkToplevel(self)
        modal.title(f"发现新版本 - {tag_name}")
        modal.geometry("640x510")
        modal.minsize(620, 480)
        modal.attributes('-topmost', True)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(container, text=f"✨ 发现新版本: {tag_name}", font=self.get_font(18, "bold"), text_color=COLOR_BAMBU_GREEN).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(container, text=f"当前运行版本: {CURRENT_VERSION}", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 10))

        txt_body = ctk.CTkTextbox(container, corner_radius=12, fg_color=COLOR_BG_MAIN, font=self.get_font(12))
        txt_body.pack(fill="both", expand=True, padx=16, pady=6)
        txt_body.insert("1.0", body)
        txt_body.configure(state="disabled")

        lbl_status = ctk.CTkLabel(container, text="", font=self.get_font(11), text_color=COLOR_TEXT_MUTED)
        lbl_status.pack(anchor="w", padx=16, pady=(2, 0))

        btn_box = ctk.CTkFrame(container, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=12)

        def skip_this_version():
            self.cfg["skipped_version"] = tag_name
            save_config(self.cfg)
            modal.destroy()

        btn_auto_update = ctk.CTkButton(
            btn_box, text="⚡ 一键自覆盖更新", height=38, corner_radius=12,
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32",
            font=self.get_font(13, "bold"),
            command=lambda: self.start_auto_replace_update(raw_download_url, tag_name, asset_exe_name, lbl_status, btn_auto_update)
        )
        btn_auto_update.pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            btn_box, text="☁️ 网盘备用下载", height=38, corner_radius=12,
            fg_color="#2563EB", hover_color="#1D4ED8",
            font=self.get_font(12, "bold"),
            command=lambda: webbrowser.open(BACKUP_PAN_URL)
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            btn_box, text="🌐 GitHub", height=38, corner_radius=12,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=self.get_font(12),
            command=lambda: webbrowser.open(html_url)
        ).pack(side="right", padx=(6, 0))

        if is_startup:
            ctk.CTkButton(
                btn_box, text="跳过此版本", height=38, corner_radius=12,
                fg_color="transparent", hover_color=COLOR_CARD_BORDER,
                font=self.get_font(12), command=skip_this_version
            ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            btn_box, text="稍后", height=38, corner_radius=12,
            fg_color="transparent", hover_color=COLOR_CARD_BORDER,
            font=self.get_font(12), command=modal.destroy
        ).pack(side="right")

    def start_auto_replace_update(self, raw_github_download_url, new_tag_name, asset_exe_name, lbl_status, btn_ctrl):
        if not getattr(sys, 'frozen', False):
            messagebox.showinfo("提示", "当前为源码运行模式，请打包为 exe 后体验自覆盖更新！")
            return

        if not raw_github_download_url:
            messagebox.showwarning("提示", "当前 Release 资产中未检测到 exe 文件，请点击【网盘备用下载】！")
            return

        btn_ctrl.configure(state="disabled", text="正在下载...")
        lbl_status.configure(text="正在连接国内加速节点，请稍候...")

        def _worker():
            try:
                temp_exe = os.path.join(os.getenv("TEMP", "."), f"bambu_new_{int(time.time())}.exe")
                download_success = False
                last_err = ""

                candidate_urls = [f"{prefix}{raw_github_download_url}" for prefix in GH_PROXY_NODES]
                candidate_urls.append(raw_github_download_url)

                for idx, download_url in enumerate(candidate_urls):
                    node_label = f"节点 {idx+1}/{len(candidate_urls)}"
                    self.after(0, lambda n=node_label: lbl_status.configure(text=f"正在通过 [{n}] 下载更新包..."))
                    try:
                        req = urllib.request.Request(download_url, headers={"User-Agent": "BambuStudio-Updater"})
                        with urllib.request.urlopen(req, timeout=12) as resp, open(temp_exe, 'wb') as f:
                            total_size = int(resp.getheader('Content-Length', 0))
                            downloaded = 0
                            while True:
                                chunk = resp.read(64 * 1024)
                                if not chunk:
                                    break
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    percent = int(downloaded / total_size * 100)
                                    self.after(0, lambda p=percent, d=downloaded, t=total_size, n=node_label: 
                                        lbl_status.configure(text=f"[{n}] 进度: {p}% ({d//1024}KB / {t//1024}KB)"))

                            if downloaded > 5 * 1024 * 1024:
                                download_success = True
                                break
                            else:
                                raise Exception("文件体积异常，切换备用节点")
                    except Exception as e:
                        last_err = str(e)
                        write_log(f"加速节点 [{download_url}] 尝试失败: {e}")
                        if os.path.exists(temp_exe):
                            try: os.remove(temp_exe)
                            except Exception: pass
                        continue

                if not download_success:
                    raise Exception(f"所有镜像加速节点均超时，建议使用网盘下载: {last_err}")

                current_exe = sys.executable
                current_dir = os.path.dirname(current_exe)
                target_exe_name = asset_exe_name if asset_exe_name else os.path.basename(current_exe)
                target_exe_path = os.path.join(current_dir, target_exe_name)

                bat_script = os.path.join(os.getenv("TEMP", "."), "bambu_updater.bat")
                bat_content = f"""@echo off
chcp 65001 > nul
timeout /t 3 /nobreak > nul

:retry_del
if exist "{current_exe}" (
    del /f /q "{current_exe}" > nul 2>&1
    if exist "{current_exe}" (
        timeout /t 1 /nobreak > nul
        goto retry_del
    )
)

:move_file
move /y "{temp_exe}" "{target_exe_path}" > nul 2>&1
if not exist "{target_exe_path}" (
    timeout /t 1 /nobreak > nul
    goto move_file
)

timeout /t 1 /nobreak > nul
start "" "{target_exe_path}"
del "%~f0"
"""
                with open(bat_script, 'w', encoding='utf-8') as f:
                    f.write(bat_content)

                self.after(0, lambda: lbl_status.configure(text="下载完毕，正在重启并替换为新版本..."))
                time.sleep(1)
                subprocess.Popen(f'cmd /c "{bat_script}"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                os._exit(0)
            except Exception as e:
                write_log(f"自覆盖更新异常: {e}")
                self.after(50, lambda: messagebox.showerror("更新失败", f"下载出错: {e}\n\n请点击【☁️ 网盘备用下载】手动获取最新安装包。"))
                self.after(50, lambda: btn_ctrl.configure(state="normal", text="⚡ 一键自覆盖更新"))

        threading.Thread(target=_worker, daemon=True).start()
    # --------------------------------------------------------------------------
    # 子功能: 智能更新检测与多镜像故障转移下载 [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 扣减任务队列与自动处理 [START]
    # --------------------------------------------------------------------------
    def enqueue_auto_deduct(self, gcode_path, slot_weights, detected_model_name):
        self.deduct_queue.append((gcode_path, slot_weights, detected_model_name))
        self.process_deduct_queue()

    def process_deduct_queue(self):
        if self.is_dialog_showing or not self.deduct_queue:
            return

        self.is_dialog_showing = True
        gcode_path, slot_weights, detected_model_name = self.deduct_queue.pop(0)

        web_filaments = api_request(self.cfg["filaments_url"], self.cfg["api_key"], method="GET") or []
        
        current_total_w = sum(slot_weights)
        last_w = self.cfg.get("last_slice_weight", 0.0)
        
        is_confirmed, task_name, slot_map = ask_user_multi_slot_mapping_modern(
            slot_weights, web_filaments, detected_model_name=detected_model_name, 
            parent_window=self, font_family=self.font_family, last_weight=last_w
        )

        if is_confirmed:
            self.cfg["last_slice_weight"] = round(current_total_w, 2)
            save_config(self.cfg)

            time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            for slot_idx, info in slot_map.items():
                f_id = info["filament_id"]
                w = info["used_weight_g"]
                full_task_name = f"{task_name}_槽{slot_idx}_{time_str}_{w}g.gcode"
                
                payload = {"filament_id": f_id, "used_weight_g": w, "task_name": full_task_name}
                res = api_request(self.cfg["server_url"], self.cfg["api_key"], method="POST", data=payload)
                if res:
                    write_log(f"✅ [自动扣减成功] 槽位{slot_idx} -> 耗材ID:{f_id} 扣除 {w}g，剩余: {res.get('remaining_weight_g')}g")
                else:
                    write_log(f"❌ 槽位{slot_idx} 上报失败")
            self.refresh_dashboard()

        self.is_dialog_showing = False
        if self.deduct_queue:
            self.after(200, self.process_deduct_queue)
    # --------------------------------------------------------------------------
    # 子功能: 扣减任务队列与自动处理 [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 耗材台账看板视图 [START]
    # --------------------------------------------------------------------------
    def init_dashboard_view(self):
        view = ctk.CTkFrame(self.content_area, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(view, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        logo_box = ctk.CTkFrame(header, fg_color="transparent")
        logo_box.pack(side="left")

        if os.path.exists(LOGO_PNG_FILE):
            try:
                pil_img = Image.open(LOGO_PNG_FILE)
                self.bambu_icon = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(38, 38))
                icon_lbl = ctk.CTkLabel(logo_box, image=self.bambu_icon, text="")
                icon_lbl.pack(side="left", padx=(0, 12))
            except Exception:
                pass

        title_sub_box = ctk.CTkFrame(logo_box, fg_color="transparent")
        title_sub_box.pack(side="left")

        t_row = ctk.CTkFrame(title_sub_box, fg_color="transparent")
        t_row.pack(anchor="w")
        self.lbl_dash_title = ctk.CTkLabel(t_row, text="拓竹耗材台账", font=self.get_font(23, "bold"), text_color=COLOR_TEXT_PRIMARY)
        self.lbl_dash_title.pack(side="left")
        self.register_widget_font(self.lbl_dash_title, 23, "bold")
        
        self.badge_new = ctk.CTkButton(
            t_row, text="NEW", width=42, height=18, corner_radius=9,
            fg_color=COLOR_BADGE_RED, hover_color="#D92828",
            font=self.get_font(10, "bold"), text_color="#FFFFFF",
            command=self.open_update_modal
        )

        sub_row = ctk.CTkFrame(title_sub_box, fg_color="transparent")
        sub_row.pack(anchor="w")
        
        lbl_sub = ctk.CTkLabel(sub_row, text=f"Bambu Inventory Studio • {CURRENT_VERSION}", font=self.get_font(11), text_color=COLOR_TEXT_MUTED)
        lbl_sub.pack(side="left")
        self.register_widget_font(lbl_sub, 11)

        self.lbl_user_status = ctk.CTkLabel(
            sub_row, text="⚪ 正在同步账号...", font=self.get_font(10, "bold"),
            text_color=COLOR_TEXT_MUTED, fg_color="#202025", corner_radius=6, padx=8, pady=1
        )
        self.lbl_user_status.pack(side="left", padx=(8, 0))

        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.pack(side="right")

        btn_add = ctk.CTkButton(
            btn_box, text="＋ 新增耗材档案", width=128, height=36, corner_radius=18,
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32",
            font=self.get_font(13, "bold"),
            command=self.open_add_filament_modal
        )
        btn_add.pack(side="left", padx=(0, 8))
        self.register_widget_font(btn_add, 13, "bold")

        btn_refresh = ctk.CTkButton(
            btn_box, text="🔄 刷新数据", width=96, height=36, corner_radius=18,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=self.get_font(13, "bold"),
            command=self.refresh_dashboard
        )
        btn_refresh.pack(side="left")
        self.register_widget_font(btn_refresh, 13, "bold")

        self.banner = ctk.CTkFrame(view, height=92, fg_color=COLOR_CARD_BG, corner_radius=20, border_width=1, border_color=COLOR_CARD_BORDER)
        self.banner.grid(row=1, column=0, sticky="ew", pady=(0, 14))

        self.scroll_list = ctk.CTkScrollableFrame(view, fg_color="transparent")
        self.scroll_list.grid(row=2, column=0, sticky="nsew")
        self.scroll_list.grid_columnconfigure(0, weight=1)

        self.views["dashboard"] = view

    def refresh_dashboard(self):
        for w in self.scroll_list.winfo_children():
            w.destroy()
        for w in self.banner.winfo_children():
            w.destroy()

        filaments = api_request(self.cfg["filaments_url"], self.cfg["api_key"], method="GET")
        if filaments is None:
            filaments = []

        total_types = len(filaments)
        total_weight = sum([item.get('current_weight_g', 0) or 0 for item in filaments])
        
        total_value = 0.0
        for item in filaments:
            price = item.get('price', 0) or 0
            init_w = item.get('initial_weight_g', 1000) or 1000
            curr_w = item.get('current_weight_g', 0) or 0
            if init_w > 0:
                total_value += (price / init_w) * curr_w

        avg_unit_price = (total_value / total_weight) if total_weight > 0 else 0.0

        b_box1 = ctk.CTkFrame(self.banner, fg_color="transparent")
        b_box1.pack(side="left", padx=24, pady=12)
        ctk.CTkLabel(b_box1, text="库存预估价值", font=self.get_font(11, "bold"), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(b_box1, text=f"¥ {total_value:.2f}", font=self.get_font(24, "bold"), text_color=COLOR_BAMBU_GREEN if total_value > 0 else COLOR_TEXT_PRIMARY).pack(anchor="w")

        ctk.CTkFrame(self.banner, width=1, fg_color=COLOR_CARD_BORDER).pack(side="left", fill="y", pady=14)

        b_box2 = ctk.CTkFrame(self.banner, fg_color="transparent")
        b_box2.pack(side="left", padx=24, pady=12)
        ctk.CTkLabel(b_box2, text="剩余存量总重", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(b_box2, text=f"{total_weight:.1f} g", font=self.get_font(18, "bold"), text_color=COLOR_BAMBU_GREEN).pack(anchor="w")

        ctk.CTkFrame(self.banner, width=1, fg_color=COLOR_CARD_BORDER).pack(side="left", fill="y", pady=14)

        b_box3 = ctk.CTkFrame(self.banner, fg_color="transparent")
        b_box3.pack(side="left", padx=24, pady=12)
        ctk.CTkLabel(b_box3, text="平均克重单价", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(b_box3, text=f"¥ {avg_unit_price:.3f} /g", font=self.get_font(18, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")

        b_box4 = ctk.CTkFrame(self.banner, fg_color="transparent")
        b_box4.pack(side="right", padx=24, pady=12)
        ctk.CTkLabel(b_box4, text="在册耗材种类", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="e")
        ctk.CTkLabel(b_box4, text=f"{total_types} 款", font=self.get_font(18, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="e")

        if not filaments:
            ctk.CTkLabel(self.scroll_list, text="⚠️ 暂未获取到耗材数据，请在设置中配置服务器或点击 [新增耗材档案]", text_color=COLOR_TEXT_MUTED, font=self.get_font(13)).pack(pady=60)
            return

        for item in filaments:
            card = ctk.CTkFrame(self.scroll_list, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
            card.pack(fill="x", pady=6)
            card.grid_columnconfigure(2, weight=1)

            fid = item.get('id', '-')
            brand = item.get('brand', 'Bambu')
            material = item.get('material', '-')
            color_name = item.get('color_name', '-')
            curr_w = item.get('current_weight_g', 0) or 0
            price = item.get('price', 0) or 0
            init_w = item.get('initial_weight_g', 1000) or 1000
            
            curr_val = (price / init_w * curr_w) if init_w > 0 else 0.0

            id_badge = ctk.CTkFrame(card, corner_radius=10, fg_color="#0D2B1A")
            id_badge.grid(row=0, column=0, padx=16, pady=14)
            ctk.CTkLabel(id_badge, text=f"#{fid}", text_color=COLOR_BAMBU_GREEN, font=self.get_font(13, "bold")).pack(padx=12, pady=5)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.grid(row=0, column=1, padx=6, pady=12, sticky="w")
            ctk.CTkLabel(info, text=f"{brand} {material} • {color_name}", font=self.get_font(15, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
            ctk.CTkLabel(info, text=f"买入价: ¥{price} / {init_w}g", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

            val_box = ctk.CTkFrame(card, fg_color="transparent")
            val_box.grid(row=0, column=2, padx=16, pady=12, sticky="e")
            ctk.CTkLabel(val_box, text=f"{curr_w} g", font=self.get_font(16, "bold"), text_color=COLOR_BAMBU_GREEN).pack(anchor="e")
            ctk.CTkLabel(val_box, text=f"约 ¥ {curr_val:.2f}", font=self.get_font(12), text_color=COLOR_TEXT_MUTED).pack(anchor="e")

            ops_box = ctk.CTkFrame(card, fg_color="transparent")
            ops_box.grid(row=0, column=3, padx=16, pady=12)

            ctk.CTkButton(
                ops_box, text="手动调整", width=72, height=30, corner_radius=8,
                fg_color="#2563EB", hover_color="#1D4ED8", font=self.get_font(11, "bold"),
                command=lambda f=item: self.open_adjust_modal(f)
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                ops_box, text="历史", width=52, height=30, corner_radius=8,
                fg_color="#475569", hover_color="#334155", font=self.get_font(11, "bold"),
                command=lambda f=item: self.open_history_modal(f)
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                ops_box, text="删除", width=52, height=30, corner_radius=8,
                fg_color="#DC2626", hover_color="#B91C1C", font=self.get_font(11, "bold"),
                command=lambda fid=fid: self.delete_filament(fid)
            ).pack(side="left", padx=2)
    # --------------------------------------------------------------------------
    # 子功能: 耗材台账看板视图 [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 服务设置视图 [START]
    # --------------------------------------------------------------------------
    def init_settings_view(self):
        scroll_view = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")
        scroll_view.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(scroll_view, text="设置与关于", font=self.get_font(24, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", pady=(0, 16))

        card = ctk.CTkFrame(scroll_view, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        card.pack(fill="x", pady=(0, 14))
        card.grid_columnconfigure(1, weight=1)

        # 扣减上报地址
        item1 = ctk.CTkFrame(card, fg_color="transparent")
        item1.pack(fill="x", padx=20, pady=12)
        item1.grid_columnconfigure(1, weight=1)
        
        lbl_box1 = ctk.CTkFrame(item1, fg_color="transparent")
        lbl_box1.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box1, text="扣减上报地址", font=self.get_font(14, "bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box1, text="接收 G-code 脚本切片扣减请求", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.entry_server_url = ctk.CTkEntry(item1, height=40, corner_radius=10)
        self.entry_server_url.grid(row=0, column=1, padx=(16, 0), sticky="ew")
        self.entry_server_url.insert(0, self.cfg.get("server_url", ""))

        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=20)

        # 耗材台账地址
        item2 = ctk.CTkFrame(card, fg_color="transparent")
        item2.pack(fill="x", padx=20, pady=12)
        item2.grid_columnconfigure(1, weight=1)

        lbl_box2 = ctk.CTkFrame(item2, fg_color="transparent")
        lbl_box2.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box2, text="耗材台账地址", font=self.get_font(14, "bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box2, text="用于实时拉取耗材档案与库存概览", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.entry_filaments_url = ctk.CTkEntry(item2, height=40, corner_radius=10)
        self.entry_filaments_url.grid(row=0, column=1, padx=(16, 0), sticky="ew")
        self.entry_filaments_url.insert(0, self.cfg.get("filaments_url", ""))

        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=20)

        # 脚本 API 密钥 + 一键登录获取按钮
        item3 = ctk.CTkFrame(card, fg_color="transparent")
        item3.pack(fill="x", padx=20, pady=12)
        item3.grid_columnconfigure(1, weight=1)

        lbl_box3 = ctk.CTkFrame(item3, fg_color="transparent")
        lbl_box3.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box3, text="脚本 API 密钥 (Token)", font=self.get_font(14, "bold")).pack(anchor="w")
        self.lbl_settings_user = ctk.CTkLabel(lbl_box3, text="正在校验认证状态...", font=self.get_font(11), text_color=COLOR_BAMBU_GREEN)
        self.lbl_settings_user.pack(anchor="w")

        key_input_box = ctk.CTkFrame(item3, fg_color="transparent")
        key_input_box.grid(row=0, column=1, padx=(16, 0), sticky="ew")
        key_input_box.grid_columnconfigure(0, weight=1)

        self.entry_api_key = ctk.CTkEntry(key_input_box, height=40, corner_radius=10, show="*")
        self.entry_api_key.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.entry_api_key.insert(0, self.cfg.get("api_key", ""))

        btn_quick_login = ctk.CTkButton(
            key_input_box, text="🔑 一键登录获取", width=120, height=38, corner_radius=10,
            fg_color="#3B82F6", hover_color="#2563EB", font=self.get_font(12, "bold"),
            command=self.open_quick_login_modal
        )
        btn_quick_login.grid(row=0, column=1)

        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=20)

        # 全局字体选择通道
        item_font = ctk.CTkFrame(card, fg_color="transparent")
        item_font.pack(fill="x", padx=20, pady=12)
        item_font.grid_columnconfigure(1, weight=1)

        lbl_box_font = ctk.CTkFrame(item_font, fg_color="transparent")
        lbl_box_font.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box_font, text="🎨 界面全局渲染字体", font=self.get_font(14, "bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box_font, text="支持在小米澎湃圆润字体与微软高清字体之间自由切换", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.combo_font = ctk.CTkComboBox(
            item_font, values=["MiSans (小米澎湃)", "Microsoft YaHei UI (微软高清)", "Segoe UI Variable (Win11 字体)"],
            height=36, corner_radius=10, width=220, font=self.get_font(12),
            command=self.on_font_change_live
        )
        self.combo_font.grid(row=0, column=1, padx=(16, 0), sticky="e")
        self.combo_font.set(self.cfg.get("selected_font", "MiSans (小米澎湃)"))

        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=20)

        # 更新发布通道
        item_ch = ctk.CTkFrame(card, fg_color="transparent")
        item_ch.pack(fill="x", padx=20, pady=12)
        item_ch.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(item_ch, text="更新发布通道", font=self.get_font(14, "bold")).grid(row=0, column=0, sticky="w")
        self.combo_channel = ctk.CTkComboBox(
            item_ch, values=["Release (正式版)", "Beta (测试版)"],
            height=36, corner_radius=10, width=220, font=self.get_font(12)
        )
        self.combo_channel.grid(row=0, column=1, padx=(16, 0), sticky="e")
        self.combo_channel.set(self.cfg.get("update_channel", "Release (正式版)"))

        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=20)

        # 切片自动监听
        item4 = ctk.CTkFrame(card, fg_color="transparent")
        item4.pack(fill="x", padx=20, pady=12)
        item4.grid_columnconfigure(1, weight=1)

        lbl_box4 = ctk.CTkFrame(item4, fg_color="transparent")
        lbl_box4.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box4, text="切片打印自动监听", font=self.get_font(14, "bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box4, text="开启后切片完成即可自动唤醒扣减", font=self.get_font(11), text_color=COLOR_BAMBU_GREEN).pack(anchor="w")

        self.switch_watcher = ctk.CTkSwitch(
            item4, text="实时监听中", font=self.get_font(12, "bold"),
            progress_color=COLOR_BAMBU_GREEN, command=self.toggle_watcher
        )
        self.switch_watcher.grid(row=0, column=1, sticky="e")
        if self.cfg.get("auto_watcher_enabled", True):
            self.switch_watcher.select()
        else:
            self.switch_watcher.deselect()

        btn_box = ctk.CTkFrame(scroll_view, fg_color="transparent")
        btn_box.pack(fill="x", pady=(8, 14))

        ctk.CTkButton(
            btn_box, text="测试服务器连接", height=42, corner_radius=20,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=self.get_font(13, "bold"), command=self.test_connection
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_box, text="🔍 立即检查更新", height=42, corner_radius=20,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=self.get_font(13, "bold"), command=self.manual_check_update
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_box, text="保存设置", height=42, corner_radius=20,
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32",
            font=self.get_font(13, "bold"), command=self.save_settings
        ).pack(side="left")

        # 开源卡片
        github_card = ctk.CTkFrame(scroll_view, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        github_card.pack(fill="x", pady=(0, 36))

        gh_content = ctk.CTkFrame(github_card, fg_color="transparent")
        gh_content.pack(fill="x", padx=22, pady=16)

        gh_info = ctk.CTkFrame(gh_content, fg_color="transparent")
        gh_info.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(gh_info, text="✨ Bambu Filament Manager (开源联机版)", font=self.get_font(16, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(gh_info, text="专为拓竹 3D 打印机打造的自动化耗材资产与成本管理系统。支持切片离线自动扣减、多色切片助手与实时成本价值换算。", font=self.get_font(11), text_color=COLOR_TEXT_MUTED, justify="left", wraplength=520).pack(anchor="w", pady=(4, 6))

        tag_box = ctk.CTkFrame(gh_info, fg_color="transparent")
        tag_box.pack(anchor="w")

        ctk.CTkLabel(tag_box, text=f"{CURRENT_VERSION} Online", font=self.get_font(10, "bold"), text_color=COLOR_BAMBU_GREEN, fg_color="#0D2B1A", corner_radius=6, padx=8, pady=2).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(tag_box, text="MIT License", font=self.get_font(10), text_color=COLOR_TEXT_MUTED, fg_color="#202025", corner_radius=6, padx=8, pady=2).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(tag_box, text="🔐 WinVault Encrypted", font=self.get_font(10), text_color="#3B82F6", fg_color="#1E293B", corner_radius=6, padx=8, pady=2).pack(side="left")

        btn_github = ctk.CTkButton(
            gh_content, text="🌐 GitHub 仓库", height=40, width=130, corner_radius=20,
            fg_color="#24292F", hover_color="#1F2328", border_width=1, border_color="#30363D",
            font=self.get_font(12, "bold"),
            command=lambda: webbrowser.open(f"https://github.com/{GITHUB_REPO}")
        )
        btn_github.pack(side="right", padx=(10, 0))

        self.views["settings"] = scroll_view

    def on_font_change_live(self, choice):
        self.font_family = map_font_family(choice)
        self.cfg["selected_font"] = choice
        save_config(self.cfg)
        write_log(f"🔤 [字体动态切换] 全界面即时切换为: {self.font_family}")
        self._refresh_all_fonts()
        try:
            self.update_idletasks()
        except Exception:
            pass

    def toggle_watcher(self):
        is_on = bool(self.switch_watcher.get())
        self.cfg["auto_watcher_enabled"] = is_on
        save_config(self.cfg)
        status_str = "已开启" if is_on else "已关闭"
        messagebox.showinfo("状态已切换", f"切片打印自动监听功能{status_str}！")

    def save_settings(self, silent=False):
        self.cfg["server_url"] = self.entry_server_url.get().strip()
        self.cfg["filaments_url"] = self.entry_filaments_url.get().strip()
        self.cfg["api_key"] = self.entry_api_key.get().strip()
        self.cfg["selected_font"] = self.combo_font.get()
        self.cfg["update_channel"] = self.combo_channel.get()
        save_config(self.cfg)
        self.fetch_user_info_async()
        
        if not silent:
            messagebox.showinfo("成功", "设置与凭据已加密保存并即时生效！")

    def test_connection(self):
        self.fetch_user_info_async()
        res = api_request(self.entry_filaments_url.get().strip(), self.entry_api_key.get().strip(), method="GET")
        if res is not None:
            messagebox.showinfo("测试成功", f"🎉 成功连通服务器！\n当前登录用户: {self.current_user_name}\n读取到 {len(res)} 条耗材档案。")
        else:
            messagebox.showerror("连接失败", "无法连接服务器或 API Key 错误！")
    # --------------------------------------------------------------------------
    # 子功能: 服务设置视图 [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 运行日志视图与清空 [START]
    # --------------------------------------------------------------------------
    def init_logs_view(self):
        view = ctk.CTkFrame(self.content_area, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=1)

        top_row = ctk.CTkFrame(view, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        lbl_log_title = ctk.CTkLabel(top_row, text="客户端运行与调试日志", font=self.get_font(22, "bold"), text_color=COLOR_TEXT_PRIMARY)
        lbl_log_title.pack(side="left")
        self.register_widget_font(lbl_log_title, 22, "bold")

        btn_clear = ctk.CTkButton(
            top_row, text="🗑️ 清空日志", width=90, height=32, corner_radius=16,
            fg_color="#DC2626", hover_color="#B91C1C", font=self.get_font(11, "bold"),
            command=self.clear_logs
        )
        btn_clear.pack(side="right")
        self.register_widget_font(btn_clear, 11, "bold")

        self.txt_log = ctk.CTkTextbox(view, corner_radius=18, fg_color=COLOR_CARD_BG, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_log.grid(row=1, column=0, sticky="nsew")

        self.views["logs"] = view

    def clear_logs(self):
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 日志已清空\n")
            self.load_logs()
        except Exception:
            pass

    def load_logs(self):
        self.txt_log.delete("1.0", tk.END)
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                self.txt_log.insert(tk.END, f.read())
        self.txt_log.see(tk.END)
    # --------------------------------------------------------------------------
    # 子功能: 运行日志视图与清空 [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 耗材管理模态弹窗 (历史/新增/手动调整/删除/撤销) [START]
    # --------------------------------------------------------------------------
    def open_history_modal(self, filament):
        modal = ctk.CTkToplevel(self)
        modal.title(f"消耗与变动历史 - #{filament['id']}")
        modal.geometry("560x520")
        modal.attributes('-topmost', True)
        modal.configure(fg_color=COLOR_BG_MAIN)

        if os.path.exists(LOGO_ICO_FILE):
            try:
                modal.iconbitmap(LOGO_ICO_FILE)
            except Exception:
                pass

        container = ctk.CTkFrame(modal, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        header_box = ctk.CTkFrame(container, fg_color="transparent")
        header_box.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(header_box, text=f"耗材: {filament.get('brand')} {filament.get('material')} [{filament.get('color_name')}]", font=self.get_font(15, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(header_box, text="包含所有切片自动扣减与手动调整记录", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        logs_scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        logs_scroll.pack(fill="both", expand=True, padx=12, pady=6)
        logs_scroll.grid_columnconfigure(0, weight=1)

        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        logs_url = f"{base_url}/api/ingest/script-filament-logs/{filament['id']}"
        logs = api_request(logs_url, self.cfg['api_key'], method="GET")

        if not logs:
            ctk.CTkLabel(logs_scroll, text="暂无消耗变动记录", text_color=COLOR_TEXT_MUTED, font=self.get_font(13)).pack(pady=40)
        else:
            for log in logs:
                log_card = ctk.CTkFrame(
                    logs_scroll, corner_radius=12, fg_color=COLOR_BG_MAIN,
                    border_width=1, border_color=COLOR_CARD_BORDER
                )
                log_card.pack(fill="x", pady=4)

                log_card.grid_columnconfigure(0, weight=1, minsize=0)
                log_card.grid_columnconfigure(1, weight=0)
                log_card.grid_columnconfigure(2, weight=0)

                task_name = str(log.get('task_name') or '打印任务/变动')
                used_w = log.get('used_weight_g', 0)
                created_at = str(log.get('created_at', ''))

                info_box = ctk.CTkFrame(log_card, fg_color="transparent")
                info_box.grid(row=0, column=0, padx=(12, 4), pady=10, sticky="ew")
                info_box.grid_columnconfigure(0, weight=1)

                display_task_name = task_name
                if len(display_task_name) > 34:
                    display_task_name = display_task_name[:33] + "…"

                task_label = ctk.CTkLabel(
                    info_box,
                    text=display_task_name,
                    font=self.get_font(13, "bold"),
                    text_color=COLOR_TEXT_PRIMARY,
                    anchor="w",
                    justify="left",
                    wraplength=285
                )
                task_label.grid(row=0, column=0, sticky="ew")

                ctk.CTkLabel(
                    info_box,
                    text=created_at,
                    font=self.get_font(10),
                    text_color=COLOR_TEXT_MUTED,
                    anchor="w"
                ).grid(row=1, column=0, sticky="w", pady=(3, 0))

                def show_task_tip(event, full_text=task_name):
                    if len(full_text) <= 34:
                        return
                    tip = getattr(self, "_history_tip_window", None)
                    try:
                        if tip is not None and tip.winfo_exists():
                            tip.destroy()
                    except Exception:
                        pass
                    tip = ctk.CTkToplevel(modal)
                    self._history_tip_window = tip
                    tip.overrideredirect(True)
                    tip.attributes("-topmost", True)
                    tip.configure(fg_color=COLOR_CARD_BG)
                    label = ctk.CTkLabel(
                        tip, text=full_text, font=self.get_font(11),
                        text_color=COLOR_TEXT_PRIMARY, justify="left",
                        wraplength=420, padx=10, pady=8
                    )
                    label.pack()
                    tip.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")

                def hide_task_tip(event):
                    tip = getattr(self, "_history_tip_window", None)
                    try:
                        if tip is not None and tip.winfo_exists():
                            tip.destroy()
                    except Exception:
                        pass
                    self._history_tip_window = None

                task_label.bind("<Enter>", show_task_tip)
                task_label.bind("<Leave>", hide_task_tip)

                is_reduce = used_w > 0
                val_str = f"-{used_w:.1f} g" if is_reduce else f"+{abs(used_w):.1f} g"
                val_color = "#EF4444" if is_reduce else COLOR_BAMBU_GREEN

                ctk.CTkLabel(
                    log_card, text=val_str, font=self.get_font(14, "bold"),
                    text_color=val_color
                ).grid(row=0, column=1, padx=12)

                rec_id = log.get('id')
                btn_undo = ctk.CTkButton(
                    log_card, text="撤销", width=50, height=28, corner_radius=6,
                    fg_color="#DC2626", hover_color="#B91C1C",
                    font=self.get_font(11, "bold"),
                    command=lambda rid=rec_id, modal_w=modal: self.undo_usage_record(rid, modal_w)
                )
                btn_undo.grid(row=0, column=2, padx=(0, 12))

    def undo_usage_record(self, record_id, modal_window):
        if messagebox.askyesno("确认撤销", "确定要撤销这条记录吗？\n撤销后服务端将基于历史快照精准恢复到变动前的真实余量。"):
            base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
            undo_url = f"{base_url}/api/ingest/script-undo-record/{record_id}"
            res = api_request(undo_url, self.cfg['api_key'], method="DELETE")
            if res:
                messagebox.showinfo("成功", "已成功撤销该记录并恢复库存！")
                modal_window.destroy()
                self.refresh_dashboard()
            else:
                messagebox.showerror("失败", "撤销记录失败，请检查网络或后端配置！")

    def open_add_filament_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("新增耗材档案")
        modal.geometry("460x520")
        modal.minsize(440, 500)
        modal.attributes('-topmost', True)
        modal.configure(fg_color=COLOR_BG_MAIN)

        if os.path.exists(LOGO_ICO_FILE):
            try:
                modal.iconbitmap(LOGO_ICO_FILE)
            except Exception:
                pass

        container = ctk.CTkFrame(modal, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(container, text="录入新耗材档案", font=self.get_font(18, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=18, pady=(16, 12))

        form_scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        form_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        fields = {}
        form_defs = [
            ("耗材品牌", "brand", "Bambu"),
            ("耗材材质", "material", "PLA"),
            ("颜色名称", "color_name", "Basic Green"),
            ("初始克重 (g)", "initial_weight_g", "1000"),
            ("买入价格 (¥)", "price", "99.0")
        ]

        for label, key, default in form_defs:
            f_box = ctk.CTkFrame(form_scroll, fg_color="transparent")
            f_box.pack(fill="x", padx=6, pady=5)
            ctk.CTkLabel(f_box, text=label, font=self.get_font(12, "bold")).pack(anchor="w")
            entry = ctk.CTkEntry(f_box, height=36, corner_radius=8, font=self.get_font(12))
            entry.pack(fill="x", pady=(2, 0))
            entry.insert(0, default)
            fields[key] = entry

        def submit():
            try:
                payload = {
                    "brand": fields["brand"].get().strip(),
                    "material": fields["material"].get().strip(),
                    "color_name": fields["color_name"].get().strip(),
                    "initial_weight_g": float(fields["initial_weight_g"].get().strip()),
                    "current_weight_g": float(fields["initial_weight_g"].get().strip()),
                    "price": float(fields["price"].get().strip())
                }
                res = api_request(f"{self.cfg['server_url']}-create", self.cfg['api_key'], method="POST", data=payload)
                messagebox.showinfo("成功", "新耗材已成功录入档案！")
                modal.destroy()
                self.refresh_dashboard()
            except Exception as e:
                messagebox.showerror("错误", f"录入失败，请检查输入格式！\n{e}")

        btn_submit = ctk.CTkButton(
            container, text="✔ 提交档案", height=42, corner_radius=12,
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32",
            font=self.get_font(14, "bold"), command=submit
        )
        btn_submit.pack(fill="x", padx=18, pady=(0, 16), side="bottom")

    def open_adjust_modal(self, filament):
        modal = ctk.CTkToplevel(self)
        modal.title(f"手动调整克重 - #{filament['id']}")
        modal.geometry("440x480")
        modal.attributes('-topmost', True)
        modal.configure(fg_color=COLOR_BG_MAIN)

        if os.path.exists(LOGO_ICO_FILE):
            try:
                modal.iconbitmap(LOGO_ICO_FILE)
            except Exception:
                pass

        container = ctk.CTkFrame(modal, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(container, text=f"耗材: {filament.get('brand')} {filament.get('material')} [{filament.get('color_name')}]", font=self.get_font(15, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(container, text=f"当前剩余存量: {filament.get('current_weight_g')} g", font=self.get_font(12), text_color=COLOR_BAMBU_GREEN).pack(anchor="w", padx=16, pady=(0, 10))

        action_box = ctk.CTkFrame(container, fg_color="transparent")
        action_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(action_box, text="调整类型:", font=self.get_font(12, "bold")).pack(anchor="w")
        cb_action = ctk.CTkComboBox(action_box, values=["减少 (-)", "增加 (+)"], corner_radius=8, height=36, font=self.get_font(13))
        cb_action.pack(fill="x", pady=(2, 0))
        cb_action.set("减少 (-)")

        w_box = ctk.CTkFrame(container, fg_color="transparent")
        w_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(w_box, text="变动克重 (g):", font=self.get_font(12, "bold")).pack(anchor="w")
        entry_weight = ctk.CTkEntry(w_box, height=36, corner_radius=8, placeholder_text="请输入克重 (必须为正数，如 50)", font=self.get_font(13))
        entry_weight.pack(fill="x", pady=(2, 0))

        model_box = ctk.CTkFrame(container, fg_color="transparent")
        model_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(model_box, text="模型名称:", font=self.get_font(12, "bold")).pack(anchor="w")
        entry_model = ctk.CTkEntry(model_box, height=36, corner_radius=8, placeholder_text="例如: 手动样品 / 测试件", font=self.get_font(13))
        entry_model.pack(fill="x", pady=(2, 0))

        remark_box = ctk.CTkFrame(container, fg_color="transparent")
        remark_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(remark_box, text="备注说明:", font=self.get_font(12, "bold")).pack(anchor="w")
        entry_remark = ctk.CTkEntry(remark_box, height=36, corner_radius=8, placeholder_text="例如: 管道残料清理 / 补充新卷", font=self.get_font(13))
        entry_remark.pack(fill="x", pady=(2, 0))

        def submit():
            try:
                raw_w = float(entry_weight.get().strip())
                if raw_w <= 0:
                    messagebox.showwarning("提示", "克重请输入大于0的数值！")
                    return

                act = cb_action.get()
                model_name = entry_model.get().strip() or "手动调整"
                remark_str = entry_remark.get().strip()

                final_change_g = raw_w if "减少" in act else -raw_w
                act_text = "手动减少" if "减少" in act else "手动增加"
                
                full_task_name = f"{act_text}（{model_name} - {remark_str}）" if remark_str else f"{act_text}（{model_name}）"

                payload = {
                    "filament_id": filament['id'],
                    "used_weight_g": final_change_g,
                    "task_name": full_task_name
                }

                res = api_request(self.cfg['server_url'], self.cfg['api_key'], method="POST", data=payload)
                if res:
                    messagebox.showinfo("成功", "克重调整完成并已记录！")
                    modal.destroy()
                    self.refresh_dashboard()
                else:
                    messagebox.showerror("错误", "上报调整失败，请检查服务连接！")
            except Exception as e:
                messagebox.showerror("错误", f"提交失败，请输入格式正确的克重数值！\n{e}")

        ctk.CTkButton(container, text="确认调整", height=40, corner_radius=12, fg_color=COLOR_BAMBU_GREEN, font=self.get_font(14, "bold"), command=submit).pack(fill="x", padx=16, pady=(16, 10))

    def delete_filament(self, fid):
        if messagebox.askyesno("确认", f"确定要彻底删除 ID #{fid} 的耗材档案吗？"):
            api_request(f"{self.cfg['server_url']}-delete/{fid}", self.cfg['api_key'], method="DELETE")
            self.refresh_dashboard()
    # --------------------------------------------------------------------------
    # 子功能: 耗材管理模态弹窗 (历史/新增/手动调整/删除/撤销) [END]
    # --------------------------------------------------------------------------
# ==============================================================================
# 模块 8: 客户端主界面逻辑与核心组件 [END]
# ==============================================================================


# ==============================================================================
# 模块 9: 多色切片扣减弹窗交互系统 [START]
# ==============================================================================
def ask_user_multi_slot_mapping_modern(slot_weights, web_filaments, detected_model_name="Bambu_Model", parent_window=None, font_family="MiSans", last_weight=0.0):
    user_choice = {"confirmed": False, "task_name": "", "slot_map": {}}
    slot_cache = load_slot_cache()

    dialog = ctk.CTkToplevel(parent_window) if parent_window else ctk.CTk()
    dialog.title("Bambu Lab 多色切片扣减助手")
    dialog.attributes('-topmost', True)

    if os.path.exists(LOGO_ICO_FILE):
        try:
            dialog.iconbitmap(LOGO_ICO_FILE)
        except Exception:
            pass

    w_width, w_height = 640, 380 + (len(slot_weights) * 58)
    
    if parent_window:
        x = parent_window.winfo_x() + (parent_window.winfo_width() - w_width) // 2
        y = parent_window.winfo_y() + (parent_window.winfo_height() - w_height) // 2
    else:
        x = (dialog.winfo_screenwidth() - w_width) // 2
        y = (dialog.winfo_screenheight() - w_height) // 2

    dialog.geometry(f"{w_width}x{w_height}+{x}+{y}")
    dialog.resizable(False, False)

    container = ctk.CTkFrame(dialog, corner_radius=22, fg_color=COLOR_BG_MAIN)
    container.pack(fill="both", expand=True, padx=20, pady=20)

    total_w = sum(slot_weights)
    
    compare_str = ""
    if last_weight > 0:
        diff_w = total_w - last_weight
        symbol = "+" if diff_w > 0 else ""
        compare_str = f"（上盘: {last_weight:.2f}g | 差异: {symbol}{diff_w:.2f}g）"

    lbl_info = ctk.CTkLabel(
        container, 
        text=f"🌈 检测到切片任务: 共 {len(slot_weights)} 色, 总重: {total_w:.2f}g {compare_str}\n请为每个切片槽位匹配台账耗材：",
        font=ctk.CTkFont(family=font_family, size=13, weight="bold"), text_color=COLOR_TEXT_PRIMARY, justify="left"
    )
    lbl_info.pack(anchor="w", padx=20, pady=(14, 10))

    time_suffix = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    default_full_name = f"{detected_model_name}_{time_suffix}"

    name_card = ctk.CTkFrame(container, fg_color="transparent")
    name_card.pack(fill="x", padx=20, pady=6)
    ctk.CTkLabel(name_card, text="模型名称:", font=ctk.CTkFont(family=font_family, size=13, weight="bold")).pack(side="left", padx=(0, 12))
    entry_name = ctk.CTkEntry(name_card, height=38, corner_radius=12, placeholder_text="模型名称", font=ctk.CTkFont(family=font_family, size=13))
    entry_name.pack(side="left", fill="x", expand=True)
    entry_name.insert(0, default_full_name)

    filament_options = []
    filament_id_map = {}
    for f in web_filaments:
        opt_str = f"ID:{f['id']} - {f.get('brand','')} {f.get('material','')} [{f.get('color_name','')}] (剩:{f.get('current_weight_g',0)}g)"
        filament_options.append(opt_str)
        filament_id_map[opt_str] = f['id']

    if not filament_options:
        filament_options = ["ID:1 - 默认耗材档案"]
        filament_id_map["ID:1 - 默认耗材档案"] = 1

    combobox_vars = []
    for idx, w in enumerate(slot_weights):
        slot_idx = idx + 1
        s_card = ctk.CTkFrame(container, corner_radius=16, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        s_card.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(s_card, text=f"🎨 槽位 {slot_idx} ({w}g) ➔", font=ctk.CTkFont(family=font_family, size=13, weight="bold")).pack(side="left", padx=16)

        cb_var = ctk.StringVar()
        cb = ctk.CTkComboBox(s_card, variable=cb_var, values=filament_options, corner_radius=10, width=350, height=36, font=ctk.CTkFont(family=font_family, size=12))
        cb.pack(side="right", padx=12, pady=10)

        cached_id = slot_cache.get(str(slot_idx))
        matched_opt = None
        if cached_id:
            for opt in filament_options:
                if opt.startswith(f"ID:{cached_id} "):
                    matched_opt = opt
                    break

        cb.set(matched_opt if matched_opt else filament_options[idx if idx < len(filament_options) else 0])
        combobox_vars.append((slot_idx, w, cb_var))

    def on_confirm():
        user_choice["confirmed"] = True
        user_choice["task_name"] = entry_name.get().strip() or default_full_name
        new_cache = {}
        for slot_idx, w, cb_var in combobox_vars:
            selected_str = cb_var.get()
            selected_f_id = filament_id_map.get(selected_str, 1)
            user_choice["slot_map"][slot_idx] = {"filament_id": selected_f_id, "used_weight_g": w}
            new_cache[str(slot_idx)] = selected_f_id
        save_slot_cache(new_cache)
        dialog.destroy()

    def on_cancel():
        user_choice["confirmed"] = False
        dialog.destroy()

    btn_frame = ctk.CTkFrame(container, fg_color="transparent")
    btn_frame.pack(fill="x", side="bottom", padx=20, pady=16)

    ctk.CTkButton(btn_frame, text="确认扣减", height=40, corner_radius=20, fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32", font=ctk.CTkFont(family=font_family, size=14, weight="bold"), command=on_confirm).pack(side="right", padx=6)
    ctk.CTkButton(btn_frame, text="取消", height=40, corner_radius=20, fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, font=ctk.CTkFont(family=font_family, size=14, weight="bold"), command=on_cancel).pack(side="right", padx=6)

    if parent_window:
        dialog.wait_window()
    else:
        dialog.mainloop()

    return user_choice["confirmed"], user_choice["task_name"], user_choice["slot_map"]

def load_slot_cache():
    if os.path.exists(MAPPING_CACHE_FILE):
        try:
            with open(MAPPING_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_slot_cache(mapping):
    try:
        with open(MAPPING_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
# ==============================================================================
# 模块 9: 多色切片扣减弹窗交互系统 [END]
# ==============================================================================


# ==============================================================================
# 模块 10: G-code 解析与克重提取算法 [START]
# ==============================================================================
def extract_model_name_from_file(file_path):
    base_name = os.path.basename(file_path)
    base_name = base_name.lstrip('.')
    for ext in ['.gcode.3mf', '.gcode', '.3mf']:
        if base_name.lower().endswith(ext):
            base_name = base_name[:-len(ext)]
            break
    
    clean_name = re.sub(r'_[A-Z0-9]+_\d+h\d+m.*', '', base_name, flags=re.IGNORECASE)
    clean_name = re.sub(r'_\d{8}_\d{6}', '', clean_name)
    return clean_name.strip() or "Bambu_Model"

def parse_multi_filament_weights(text):
    weights = []
    m = re.search(r';\s*(?:total\s+)?filament\s*(?:weight|used)\s*\[g\]\s*[:=]\s*([^\r\n]+)', text, re.IGNORECASE)
    if m:
        vals = re.findall(r'[\d\.]+', m.group(1).strip())
        weights = [float(v) for v in vals if float(v) > 0]
    
    if not weights:
        m_cfg = re.search(r'"filament_weight"\s*:\s*\[([^\]]+)\]', text, re.IGNORECASE)
        if m_cfg:
            vals = re.findall(r'[\d\.]+', m_cfg.group(1))
            weights = [float(v) for v in vals if float(v) > 0]

    return weights

def get_bambu_project_info_strict(gcode_path):
    if os.path.exists(gcode_path) and os.path.isfile(gcode_path):
        try:
            with open(gcode_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(131072)
                w = parse_multi_filament_weights(content)
                if w: return w
        except Exception:
            pass
    return []
# ==============================================================================
# 模块 10: G-code 解析与克重提取算法 [END]
# ==============================================================================


# ==============================================================================
# 模块 11: 主程序入口 (GUI / 命令行后处理双分支) [START]
# ==============================================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        app = HyperOSFilamentApp()
        app.mainloop()
    else:
        cfg = load_config()
        gcode_path = sys.argv[-1]
        slot_weights = get_bambu_project_info_strict(gcode_path)
        detected_model_name = extract_model_name_from_file(gcode_path)

        if slot_weights and sum(slot_weights) > 0:
            web_filaments = api_request(cfg["filaments_url"], cfg["api_key"], method="GET") or []
            is_confirmed, task_name, slot_map = ask_user_multi_slot_mapping_modern(
                slot_weights, web_filaments, detected_model_name=detected_model_name, font_family=map_font_family(cfg.get("selected_font", "MiSans"))
            )

            if is_confirmed:
                time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                for slot_idx, info in slot_map.items():
                    f_id = info["filament_id"]
                    w = info["used_weight_g"]
                    full_task_name = f"{task_name}_槽{slot_idx}_{time_str}_{w}g.gcode"
                    
                    payload = {"filament_id": f_id, "used_weight_g": w, "task_name": full_task_name}
                    res = api_request(cfg["server_url"], cfg["api_key"], method="POST", data=payload)
                    if res:
                        write_log(f"✅ [扣减成功] 槽位{slot_idx} -> 耗材ID:{f_id} 扣除 {w}g，剩余: {res.get('remaining_weight_g')}g")
                    else:
                        write_log(f"❌ 槽位{slot_idx} 上报失败")
# ==============================================================================
# 模块 11: 主程序入口 (GUI / 命令行后处理双分支) [END]
# ==============================================================================