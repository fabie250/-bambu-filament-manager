import sys
import re
import json
import os
import time
import datetime
import urllib.request
import webbrowser
import ctypes
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image
import customtkinter as ctk

# ----------------- 0. Windows 凭据管理器 (安全存储) -----------------
KEYRING_SERVICE_NAME = "BambuFilamentStudio"
KEYRING_ACCOUNT_NAME = "script_api_key"

try:
    import keyring
    import keyring.backends.Windows
    keyring.set_keyring(keyring.backends.Windows.WinVaultKeyring())
    HAS_KEYRING = True
except Exception:
    HAS_KEYRING = False

# ----------------- 1. Windows 原生 DPI 高清抗锯齿 -----------------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
    except Exception:
        pass

# ----------------- 2. 基础路径与配置 -----------------
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
MAPPING_CACHE_FILE = os.path.join(BASE_DIR, "slot_mapping.json")
LOG_FILE = os.path.join(BASE_DIR, "log.txt")

CURRENT_EXE_PATH = os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__)

LOGO_PNG_FILE = resource_path("bambu_logo.png")
LOGO_ICO_FILE = resource_path("bambu_logo.ico")
FONT_REGULAR_PATH = resource_path("MiSans-Regular.ttf")
FONT_BOLD_PATH = resource_path("MiSans-Bold.ttf")

FONT_MAIN = "Segoe UI"
try:
    if os.path.exists(FONT_REGULAR_PATH):
        ctk.FontManager.load_font(FONT_REGULAR_PATH)
    if os.path.exists(FONT_BOLD_PATH):
        ctk.FontManager.load_font(FONT_BOLD_PATH)
    FONT_MAIN = "MiSans"
except Exception:
    pass

DEFAULT_CONFIG = {
    "server_url": "http://127.0.0.1:8000/api/ingest/script-report",
    "filaments_url": "http://127.0.0.1:8000/api/ingest/script-filaments",
    "api_key": "",
    "filament_id": 1,
    "auto_watcher_enabled": True
}

# ----------------- 安全凭据读写逻辑 -----------------
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

def write_log(content):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {content}\n")
    except Exception:
        pass

def api_request(url, api_key, method="GET", data=None):
    try:
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        req_data = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(f"{url}?_t={int(time.time()*1000)}", data=req_data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=6) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        write_log(f"API请求失败 [{method} {url}]: {e}")
        return None

# ----------------- 3. 配色与风格系统 (HyperOS 3 + 拓竹绿) -----------------
COLOR_BG_MAIN = "#0C0C0E"       
COLOR_CARD_BG = "#16161A"       
COLOR_CARD_BORDER = "#26262B"   
COLOR_BAMBU_GREEN = "#00AE42"   
COLOR_TEXT_PRIMARY = "#FFFFFF" 
COLOR_TEXT_MUTED = "#8E8E93"   

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ----------------- 4. 全局临时文件后台监视器 -----------------
class BambuFileWatcher(threading.Thread):
    def __init__(self, app_instance):
        super().__init__()
        self.daemon = True
        self.app = app_instance
        self.running = False
        self.processed_files = set()

    def run(self):
        self.running = True
        write_log("🚀 全局切片监控后台线程已启动...")
        
        appdata_local = os.getenv("LOCALAPPDATA", "")
        temp_dir = os.getenv("TEMP", "")
        
        watch_dirs = [
            os.path.join(appdata_local, "BambuStudio"),
            os.path.join(appdata_local, "OrcaSlicer"),
            temp_dir
        ]

        while self.running:
            try:
                if self.app.cfg.get("auto_watcher_enabled", True):
                    for w_dir in watch_dirs:
                        if not os.path.exists(w_dir):
                            continue
                        
                        now_time = time.time()
                        for root, _, files in os.walk(w_dir):
                            for file in files:
                                if file.endswith(".gcode") or file.endswith(".gcode.3mf") or file.endswith(".3mf"):
                                    file_path = os.path.join(root, file)
                                    try:
                                        mtime = os.path.getmtime(file_path)
                                        if (now_time - mtime) < 8 and file_path not in self.processed_files:
                                            self.processed_files.add(file_path)
                                            if len(self.processed_files) > 100:
                                                self.processed_files.clear()
                                            
                                            slot_weights = get_bambu_project_info(file_path)
                                            if slot_weights and sum(slot_weights) > 0:
                                                # 提取模型基础名字
                                                model_base_name = extract_model_name_from_file(file_path)
                                                write_log(f"🔍 捕获到切片打印动作: {model_base_name}")
                                                self.app.after(100, lambda fp=file_path, sw=slot_weights, mn=model_base_name: self.app.trigger_auto_deduct(fp, sw, mn))
                                    except Exception:
                                        pass
            except Exception as e:
                pass
            time.sleep(1.5)

# ----------------- 5. 拓竹耗材台账客户端主界面 -----------------
class HyperOSFilamentApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.cfg = load_config()

        self.title("拓竹耗材台账助手")
        self.geometry("880x820")
        self.minsize(760, 680)
        self.configure(fg_color=COLOR_BG_MAIN)

        if os.path.exists(LOGO_ICO_FILE):
            try:
                self.iconbitmap(LOGO_ICO_FILE)
            except Exception:
                pass

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.content_area = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content_area.grid(row=0, column=0, sticky="nsew", padx=20, pady=(15, 10))
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

        self.views = {}
        self.init_dashboard_view()
        self.init_settings_view()
        self.init_logs_view()

        # 底部悬浮大胶囊导航
        self.bottom_nav = ctk.CTkFrame(self, height=60, corner_radius=30, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        self.bottom_nav.grid(row=1, column=0, pady=(0, 15), padx=30)

        self.btn_nav_dashboard = self.create_nav_item("📦  耗材台账", "dashboard")
        self.btn_nav_dashboard.pack(side="left", padx=10, pady=6)

        self.btn_nav_settings = self.create_nav_item("⚙️  服务设置", "settings")
        self.btn_nav_settings.pack(side="left", padx=10, pady=6)

        self.btn_nav_logs = self.create_nav_item("📜  运行日志", "logs")
        self.btn_nav_logs.pack(side="left", padx=10, pady=6)

        self.switch_tab("dashboard")

        # 启动后台监听线程
        self.watcher = BambuFileWatcher(self)
        self.watcher.start()

    def create_nav_item(self, text, tab_name):
        return ctk.CTkButton(
            self.bottom_nav, text=text, font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold"),
            width=115, height=40, corner_radius=20, fg_color="transparent",
            text_color=COLOR_TEXT_MUTED, hover_color=COLOR_CARD_BORDER,
            command=lambda: self.switch_tab(tab_name)
        )

    def switch_tab(self, tab_name):
        for view in self.views.values():
            view.grid_forget()

        nav_map = {"dashboard": self.btn_nav_dashboard, "settings": self.btn_nav_settings, "logs": self.btn_nav_logs}

        for name, btn in nav_map.items():
            if name == tab_name:
                btn.configure(fg_color=COLOR_BAMBU_GREEN, text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT_MUTED)

        self.views[tab_name].grid(row=0, column=0, sticky="nsew")
        if tab_name == "dashboard":
            self.refresh_dashboard()
        elif tab_name == "logs":
            self.load_logs()

    # 触发自动扣减弹窗 (支持自动填入【模型名称 + 当前时间】)
    def trigger_auto_deduct(self, gcode_path, slot_weights, detected_model_name="Bambu_Model"):
        web_filaments = api_request(self.cfg["filaments_url"], self.cfg["api_key"], method="GET") or []
        is_confirmed, task_name, slot_map = ask_user_multi_slot_mapping_modern(
            slot_weights, web_filaments, detected_model_name=detected_model_name, parent_window=self
        )

        if is_confirmed:
            time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
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

    # --- 1. 耗材台账与概览看板 ---
    def init_dashboard_view(self):
        view = ctk.CTkFrame(self.content_area, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(view, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        logo_box = ctk.CTkFrame(header, fg_color="transparent")
        logo_box.pack(side="left")

        if os.path.exists(LOGO_PNG_FILE):
            try:
                pil_img = Image.open(LOGO_PNG_FILE)
                self.bambu_icon = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(36, 36))
                icon_lbl = ctk.CTkLabel(logo_box, image=self.bambu_icon, text="")
                icon_lbl.pack(side="left", padx=(0, 10))
            except Exception:
                pass

        title_sub_box = ctk.CTkFrame(logo_box, fg_color="transparent")
        title_sub_box.pack(side="left")

        ctk.CTkLabel(title_sub_box, text="拓竹耗材台账", font=ctk.CTkFont(family=FONT_MAIN, size=22, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(title_sub_box, text="Bambu Lab Inventory Studio", font=ctk.CTkFont(family=FONT_MAIN, size=11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.pack(side="right")

        ctk.CTkButton(
            btn_box, text="＋ 新增耗材档案", width=120, height=36, corner_radius=18,
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32",
            font=ctk.CTkFont(family=FONT_MAIN, size=13, weight="bold"),
            command=self.open_add_filament_modal
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_box, text="🔄 刷新数据", width=90, height=36, corner_radius=18,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=ctk.CTkFont(family=FONT_MAIN, size=13, weight="bold"),
            command=self.refresh_dashboard
        ).pack(side="left")

        self.banner = ctk.CTkFrame(view, height=90, fg_color=COLOR_CARD_BG, corner_radius=20, border_width=1, border_color=COLOR_CARD_BORDER)
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
        b_box1.pack(side="left", padx=22, pady=12)
        ctk.CTkLabel(b_box1, text="库存预估价值", font=ctk.CTkFont(family=FONT_MAIN, size=11, weight="bold"), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(b_box1, text=f"¥ {total_value:.2f}", font=ctk.CTkFont(family=FONT_MAIN, size=24, weight="bold"), text_color=COLOR_BAMBU_GREEN if total_value > 0 else COLOR_TEXT_PRIMARY).pack(anchor="w")

        ctk.CTkFrame(self.banner, width=1, fg_color=COLOR_CARD_BORDER).pack(side="left", fill="y", pady=14)

        b_box2 = ctk.CTkFrame(self.banner, fg_color="transparent")
        b_box2.pack(side="left", padx=22, pady=12)
        ctk.CTkLabel(b_box2, text="剩余存量总重", font=ctk.CTkFont(family=FONT_MAIN, size=11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(b_box2, text=f"{total_weight:.1f} g", font=ctk.CTkFont(family=FONT_MAIN, size=18, weight="bold"), text_color=COLOR_BAMBU_GREEN).pack(anchor="w")

        ctk.CTkFrame(self.banner, width=1, fg_color=COLOR_CARD_BORDER).pack(side="left", fill="y", pady=14)

        b_box3 = ctk.CTkFrame(self.banner, fg_color="transparent")
        b_box3.pack(side="left", padx=22, pady=12)
        ctk.CTkLabel(b_box3, text="平均克重单价", font=ctk.CTkFont(family=FONT_MAIN, size=11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(b_box3, text=f"¥ {avg_unit_price:.3f} /g", font=ctk.CTkFont(family=FONT_MAIN, size=18, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")

        b_box4 = ctk.CTkFrame(self.banner, fg_color="transparent")
        b_box4.pack(side="right", padx=22, pady=12)
        ctk.CTkLabel(b_box4, text="在册耗材种类", font=ctk.CTkFont(family=FONT_MAIN, size=11), text_color=COLOR_TEXT_MUTED).pack(anchor="e")
        ctk.CTkLabel(b_box4, text=f"{total_types} 款", font=ctk.CTkFont(family=FONT_MAIN, size=18, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="e")

        if not filaments:
            ctk.CTkLabel(self.scroll_list, text="⚠️ 暂未获取到耗材数据，请在设置中配置服务器或点击 [新增耗材档案]", text_color=COLOR_TEXT_MUTED, font=ctk.CTkFont(family=FONT_MAIN, size=13)).pack(pady=60)
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
            id_badge.grid(row=0, column=0, padx=14, pady=14)
            ctk.CTkLabel(id_badge, text=f"#{fid}", text_color=COLOR_BAMBU_GREEN, font=ctk.CTkFont(family=FONT_MAIN, weight="bold", size=13)).pack(padx=12, pady=5)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.grid(row=0, column=1, padx=6, pady=12, sticky="w")
            ctk.CTkLabel(info, text=f"{brand} {material} • {color_name}", font=ctk.CTkFont(family=FONT_MAIN, size=15, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
            ctk.CTkLabel(info, text=f"买入价: ¥{price} / {init_w}g", font=ctk.CTkFont(family=FONT_MAIN, size=11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

            val_box = ctk.CTkFrame(card, fg_color="transparent")
            val_box.grid(row=0, column=2, padx=14, pady=12, sticky="e")
            ctk.CTkLabel(val_box, text=f"{curr_w} g", font=ctk.CTkFont(family=FONT_MAIN, size=16, weight="bold"), text_color=COLOR_BAMBU_GREEN).pack(anchor="e")
            ctk.CTkLabel(val_box, text=f"约 ¥ {curr_val:.2f}", font=ctk.CTkFont(family=FONT_MAIN, size=12), text_color=COLOR_TEXT_MUTED).pack(anchor="e")

            ops_box = ctk.CTkFrame(card, fg_color="transparent")
            ops_box.grid(row=0, column=3, padx=14, pady=12)

            ctk.CTkButton(
                ops_box, text="手动调整", width=70, height=30, corner_radius=8,
                fg_color="#2563EB", hover_color="#1D4ED8", font=ctk.CTkFont(family=FONT_MAIN, size=11, weight="bold"),
                command=lambda f=item: self.open_adjust_modal(f)
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                ops_box, text="历史", width=50, height=30, corner_radius=8,
                fg_color="#475569", hover_color="#334155", font=ctk.CTkFont(family=FONT_MAIN, size=11, weight="bold"),
                command=lambda f=item: self.open_history_modal(f)
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                ops_box, text="删除", width=50, height=30, corner_radius=8,
                fg_color="#DC2626", hover_color="#B91C1C", font=ctk.CTkFont(family=FONT_MAIN, size=11, weight="bold"),
                command=lambda fid=fid: self.delete_filament(fid)
            ).pack(side="left", padx=2)

    # --- 1.1 查看历史明细弹窗 ---
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

        ctk.CTkLabel(header_box, text=f"耗材: {filament.get('brand')} {filament.get('material')} [{filament.get('color_name')}]", font=ctk.CTkFont(family=FONT_MAIN, size=15, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(header_box, text="包含所有切片自动扣减与手动调整记录", font=ctk.CTkFont(family=FONT_MAIN, size=11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        logs_scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        logs_scroll.pack(fill="both", expand=True, padx=12, pady=6)
        logs_scroll.grid_columnconfigure(0, weight=1)

        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        logs_url = f"{base_url}/api/ingest/script-filament-logs/{filament['id']}"
        logs = api_request(logs_url, self.cfg['api_key'], method="GET")

        if not logs:
            ctk.CTkLabel(logs_scroll, text="暂无消耗变动记录", text_color=COLOR_TEXT_MUTED, font=ctk.CTkFont(family=FONT_MAIN, size=13)).pack(pady=40)
        else:
            for log in logs:
                log_card = ctk.CTkFrame(logs_scroll, corner_radius=12, fg_color=COLOR_BG_MAIN, border_width=1, border_color=COLOR_CARD_BORDER)
                log_card.pack(fill="x", pady=4)
                log_card.grid_columnconfigure(0, weight=1)

                task_name = log.get('task_name') or '打印任务/变动'
                used_w = log.get('used_weight_g', 0)
                created_at = log.get('created_at', '')

                info_box = ctk.CTkFrame(log_card, fg_color="transparent")
                info_box.grid(row=0, column=0, padx=12, pady=10, sticky="w")

                ctk.CTkLabel(info_box, text=task_name, font=ctk.CTkFont(family=FONT_MAIN, size=13, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
                ctk.CTkLabel(info_box, text=created_at, font=ctk.CTkFont(family=FONT_MAIN, size=10), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

                is_reduce = used_w > 0
                val_str = f"-{used_w:.1f} g" if is_reduce else f"+{abs(used_w):.1f} g"
                val_color = "#EF4444" if is_reduce else COLOR_BAMBU_GREEN

                ctk.CTkLabel(log_card, text=val_str, font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold"), text_color=val_color).grid(row=0, column=1, padx=12)

                rec_id = log.get('id')
                btn_undo = ctk.CTkButton(
                    log_card, text="撤销", width=50, height=28, corner_radius=6,
                    fg_color="#DC2626", hover_color="#B91C1C", font=ctk.CTkFont(family=FONT_MAIN, size=11, weight="bold"),
                    command=lambda rid=rec_id, modal_w=modal: self.undo_usage_record(rid, modal_w)
                )
                btn_undo.grid(row=0, column=2, padx=(0, 12))

    def undo_usage_record(self, record_id, modal_window):
        if messagebox.askyesno("确认撤销", "确定要撤销这条记录吗？\n撤销后，关联耗材的剩余克重将被反向退回或扣除。"):
            base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
            undo_url = f"{base_url}/api/ingest/script-undo-record/{record_id}"
            res = api_request(undo_url, self.cfg['api_key'], method="DELETE")
            if res:
                messagebox.showinfo("成功", "已成功撤销该记录并更新库存！")
                modal_window.destroy()
                self.refresh_dashboard()
            else:
                messagebox.showerror("失败", "撤销记录失败，请检查网络或后端配置！")

    # --- 新增耗材档案弹窗 ---
    def open_add_filament_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("新增耗材档案")
        modal.geometry("420x460")
        modal.attributes('-topmost', True)
        modal.configure(fg_color=COLOR_BG_MAIN)

        if os.path.exists(LOGO_ICO_FILE):
            try:
                modal.iconbitmap(LOGO_ICO_FILE)
            except Exception:
                pass

        container = ctk.CTkFrame(modal, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(container, text="录入新耗材档案", font=ctk.CTkFont(family=FONT_MAIN, size=18, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(14, 10))

        fields = {}
        for label, key, default in [("耗材品牌", "brand", "Bambu"), ("耗材材质", "material", "PLA"), ("颜色名称", "color_name", "Basic Green"), ("初始克重 (g)", "initial_weight_g", "1000"), ("买入价格 (¥)", "price", "99.0")]:
            f_box = ctk.CTkFrame(container, fg_color="transparent")
            f_box.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(f_box, text=label, font=ctk.CTkFont(family=FONT_MAIN, size=12)).pack(anchor="w")
            entry = ctk.CTkEntry(f_box, height=34, corner_radius=8)
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

        ctk.CTkButton(container, text="提交档案", height=38, corner_radius=12, fg_color=COLOR_BAMBU_GREEN, command=submit).pack(fill="x", padx=16, pady=16)

    # --- 手动调整克重表单弹窗 ---
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

        ctk.CTkLabel(container, text=f"耗材: {filament.get('brand')} {filament.get('material')} [{filament.get('color_name')}]", font=ctk.CTkFont(family=FONT_MAIN, size=15, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(container, text=f"当前剩余存量: {filament.get('current_weight_g')} g", font=ctk.CTkFont(family=FONT_MAIN, size=12), text_color=COLOR_BAMBU_GREEN).pack(anchor="w", padx=16, pady=(0, 10))

        action_box = ctk.CTkFrame(container, fg_color="transparent")
        action_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(action_box, text="调整类型:", font=ctk.CTkFont(family=FONT_MAIN, size=12, weight="bold")).pack(anchor="w")
        cb_action = ctk.CTkComboBox(action_box, values=["减少 (-)", "增加 (+)"], corner_radius=8, height=36, font=ctk.CTkFont(family=FONT_MAIN, size=13))
        cb_action.pack(fill="x", pady=(2, 0))
        cb_action.set("减少 (-)")

        w_box = ctk.CTkFrame(container, fg_color="transparent")
        w_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(w_box, text="变动克重 (g):", font=ctk.CTkFont(family=FONT_MAIN, size=12, weight="bold")).pack(anchor="w")
        entry_weight = ctk.CTkEntry(w_box, height=36, corner_radius=8, placeholder_text="请输入克重 (必须为正数，如 50)", font=ctk.CTkFont(family=FONT_MAIN, size=13))
        entry_weight.pack(fill="x", pady=(2, 0))

        model_box = ctk.CTkFrame(container, fg_color="transparent")
        model_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(model_box, text="模型名称:", font=ctk.CTkFont(family=FONT_MAIN, size=12, weight="bold")).pack(anchor="w")
        entry_model = ctk.CTkEntry(model_box, height=36, corner_radius=8, placeholder_text="例如: 手动样品 / 测试件", font=ctk.CTkFont(family=FONT_MAIN, size=13))
        entry_model.pack(fill="x", pady=(2, 0))

        remark_box = ctk.CTkFrame(container, fg_color="transparent")
        remark_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(remark_box, text="备注说明:", font=ctk.CTkFont(family=FONT_MAIN, size=12, weight="bold")).pack(anchor="w")
        entry_remark = ctk.CTkEntry(remark_box, height=36, corner_radius=8, placeholder_text="例如: 管道残料清理 / 补充新卷", font=ctk.CTkFont(family=FONT_MAIN, size=13))
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

        ctk.CTkButton(container, text="确认调整", height=40, corner_radius=12, fg_color=COLOR_BAMBU_GREEN, font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold"), command=submit).pack(fill="x", padx=16, pady=(16, 10))

    def delete_filament(self, fid):
        if messagebox.askyesno("确认", f"确定要彻底删除 ID #{fid} 的耗材档案吗？"):
            api_request(f"{self.cfg['server_url']}-delete/{fid}", self.cfg['api_key'], method="DELETE")
            self.refresh_dashboard()

    # --- 2. 服务设置视图 ---
    def init_settings_view(self):
        view = ctk.CTkFrame(self.content_area, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(view, text="设置与关于", font=ctk.CTkFont(family=FONT_MAIN, size=24, weight="bold"), text_color=COLOR_TEXT_PRIMARY).grid(row=0, column=0, sticky="w", pady=(0, 16))

        # 参数配置卡片
        card = ctk.CTkFrame(view, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        card.grid(row=1, column=0, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        item1 = ctk.CTkFrame(card, fg_color="transparent")
        item1.pack(fill="x", padx=18, pady=12)
        item1.grid_columnconfigure(1, weight=1)
        
        lbl_box1 = ctk.CTkFrame(item1, fg_color="transparent")
        lbl_box1.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box1, text="扣减上报地址", font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box1, text="接收 G-code 脚本切片扣减请求", font=ctk.CTkFont(family=FONT_MAIN, size=11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.entry_server_url = ctk.CTkEntry(item1, height=40, corner_radius=10)
        self.entry_server_url.grid(row=0, column=1, padx=(16, 0), sticky="ew")
        self.entry_server_url.insert(0, self.cfg.get("server_url", ""))

        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=18)

        item2 = ctk.CTkFrame(card, fg_color="transparent")
        item2.pack(fill="x", padx=18, pady=12)
        item2.grid_columnconfigure(1, weight=1)

        lbl_box2 = ctk.CTkFrame(item2, fg_color="transparent")
        lbl_box2.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box2, text="耗材台账地址", font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box2, text="用于实时拉取耗材档案与库存概览", font=ctk.CTkFont(family=FONT_MAIN, size=11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.entry_filaments_url = ctk.CTkEntry(item2, height=40, corner_radius=10)
        self.entry_filaments_url.grid(row=0, column=1, padx=(16, 0), sticky="ew")
        self.entry_filaments_url.insert(0, self.cfg.get("filaments_url", ""))

        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=18)

        item3 = ctk.CTkFrame(card, fg_color="transparent")
        item3.pack(fill="x", padx=18, pady=12)
        item3.grid_columnconfigure(1, weight=1)

        lbl_box3 = ctk.CTkFrame(item3, fg_color="transparent")
        lbl_box3.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box3, text="脚本 API 密钥", font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box3, text="加密安全存储在 Windows 凭据管理器中", font=ctk.CTkFont(family=FONT_MAIN, size=11), text_color=COLOR_BAMBU_GREEN).pack(anchor="w")

        self.entry_api_key = ctk.CTkEntry(item3, height=40, corner_radius=10, show="*")
        self.entry_api_key.grid(row=0, column=1, padx=(16, 0), sticky="ew")
        self.entry_api_key.insert(0, self.cfg.get("api_key", ""))

        # 全局自动监控开关
        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=18)

        item4 = ctk.CTkFrame(card, fg_color="transparent")
        item4.pack(fill="x", padx=18, pady=12)
        item4.grid_columnconfigure(1, weight=1)

        lbl_box4 = ctk.CTkFrame(item4, fg_color="transparent")
        lbl_box4.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box4, text="切片打印自动监听", font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box4, text="开启后直接点【打印】即可自动唤醒扣减，无须修改任何预设或后处理", font=ctk.CTkFont(family=FONT_MAIN, size=11), text_color=COLOR_BAMBU_GREEN).pack(anchor="w")

        self.switch_watcher = ctk.CTkSwitch(
            item4, text="实时监听中", font=ctk.CTkFont(family=FONT_MAIN, size=12, weight="bold"),
            progress_color=COLOR_BAMBU_GREEN, command=self.toggle_watcher
        )
        self.switch_watcher.grid(row=0, column=1, sticky="e")
        if self.cfg.get("auto_watcher_enabled", True):
            self.switch_watcher.select()
        else:
            self.switch_watcher.deselect()

        # 按钮栏
        btn_box = ctk.CTkFrame(view, fg_color="transparent")
        btn_box.grid(row=2, column=0, sticky="ew", pady=(12, 14))

        ctk.CTkButton(
            btn_box, text="测试服务器连接", height=42, corner_radius=20,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=ctk.CTkFont(family=FONT_MAIN, size=13, weight="bold"), command=self.test_connection
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_box, text="保存设置", height=42, corner_radius=20,
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32",
            font=ctk.CTkFont(family=FONT_MAIN, size=13, weight="bold"), command=self.save_settings
        ).pack(side="left")

        # GitHub 开源项目介绍卡片
        github_card = ctk.CTkFrame(view, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        github_card.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        gh_content = ctk.CTkFrame(github_card, fg_color="transparent")
        gh_content.pack(fill="x", padx=20, pady=14)

        gh_info = ctk.CTkFrame(gh_content, fg_color="transparent")
        gh_info.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(gh_info, text="✨ Bambu Filament Manager (开源项目)", font=ctk.CTkFont(family=FONT_MAIN, size=16, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(gh_info, text="专为拓竹 3D 打印机打造的自动化耗材资产与成本管理系统。支持切片离线自动扣减、多色切片助手与实时成本价值换算。", font=ctk.CTkFont(family=FONT_MAIN, size=11), text_color=COLOR_TEXT_MUTED, justify="left", wraplength=480).pack(anchor="w", pady=(4, 6))

        tag_box = ctk.CTkFrame(gh_info, fg_color="transparent")
        tag_box.pack(anchor="w")

        ctk.CTkLabel(tag_box, text="v2.7 Beta版", font=ctk.CTkFont(family=FONT_MAIN, size=10, weight="bold"), text_color=COLOR_BAMBU_GREEN, fg_color="#0D2B1A", corner_radius=6, padx=8, pady=2).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(tag_box, text="MIT License", font=ctk.CTkFont(family=FONT_MAIN, size=10), text_color=COLOR_TEXT_MUTED, fg_color="#202025", corner_radius=6, padx=8, pady=2).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(tag_box, text="🔐 WinVault Encrypted", font=ctk.CTkFont(family=FONT_MAIN, size=10), text_color="#3B82F6", fg_color="#1E293B", corner_radius=6, padx=8, pady=2).pack(side="left")

        btn_github = ctk.CTkButton(
            gh_content, text="🌐 GitHub 仓库", height=40, width=130, corner_radius=20,
            fg_color="#24292F", hover_color="#1F2328", border_width=1, border_color="#30363D",
            font=ctk.CTkFont(family=FONT_MAIN, size=12, weight="bold"),
            command=lambda: webbrowser.open("https://github.com/fabie250/-bambu-filament-manager")
        )
        btn_github.pack(side="right", padx=(10, 0))

        self.views["settings"] = view

    def toggle_watcher(self):
        is_on = bool(self.switch_watcher.get())
        self.cfg["auto_watcher_enabled"] = is_on
        save_config(self.cfg)
        status_str = "已开启" if is_on else "已关闭"
        messagebox.showinfo("状态已切换", f"切片打印自动监听功能{status_str}！")

    def save_settings(self):
        self.cfg["server_url"] = self.entry_server_url.get().strip()
        self.cfg["filaments_url"] = self.entry_filaments_url.get().strip()
        self.cfg["api_key"] = self.entry_api_key.get().strip()
        save_config(self.cfg)
        messagebox.showinfo("成功", "设置与凭据已加密保存！")

    def test_connection(self):
        res = api_request(self.entry_filaments_url.get().strip(), self.entry_api_key.get().strip(), method="GET")
        if res is not None:
            messagebox.showinfo("测试成功", f"成功连通！当前读取到 {len(res)} 条耗材档案。")
        else:
            messagebox.showerror("连接失败", "无法连接服务器或 API Key 错误！")

    # --- 3. 运行日志视图 ---
    def init_logs_view(self):
        view = ctk.CTkFrame(self.content_area, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(view, text="客户端运行日志", font=ctk.CTkFont(family=FONT_MAIN, size=24, weight="bold"), text_color=COLOR_TEXT_PRIMARY).grid(row=0, column=0, sticky="w", pady=(0, 14))

        self.txt_log = ctk.CTkTextbox(view, corner_radius=18, fg_color=COLOR_CARD_BG, font=ctk.CTkFont(family="Consolas", size=12))
        self.txt_log.grid(row=1, column=0, sticky="nsew")

        self.views["logs"] = view

    def load_logs(self):
        self.txt_log.delete("1.0", tk.END)
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                self.txt_log.insert(tk.END, f.read())

# ----------------- 6. 多色切片自动扣减助手弹窗 -----------------
def ask_user_multi_slot_mapping_modern(slot_weights, web_filaments, detected_model_name="Bambu_Model", parent_window=None):
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

    w_width, w_height = 620, 360 + (len(slot_weights) * 58)
    
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
    lbl_info = ctk.CTkLabel(
        container, 
        text=f"🌈 检测到切片任务 (共 {len(slot_weights)} 色, 总重: {total_w:.2f}g)\n请为每个切片槽位匹配台账耗材：",
        font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold"), text_color=COLOR_TEXT_PRIMARY
    )
    lbl_info.pack(anchor="w", padx=20, pady=(16, 12))

    # 智能模型名称 + 年月日时分秒拼接
    time_suffix = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    default_full_name = f"{detected_model_name}_{time_suffix}"

    name_card = ctk.CTkFrame(container, fg_color="transparent")
    name_card.pack(fill="x", padx=20, pady=6)
    ctk.CTkLabel(name_card, text="模型名称:", font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold")).pack(side="left", padx=(0, 12))
    entry_name = ctk.CTkEntry(name_card, height=38, corner_radius=12, placeholder_text="模型名称", font=ctk.CTkFont(family=FONT_MAIN, size=13))
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

        ctk.CTkLabel(s_card, text=f"🎨 槽位 {slot_idx} ({w}g) ➔", font=ctk.CTkFont(family=FONT_MAIN, size=13, weight="bold")).pack(side="left", padx=16)

        cb_var = ctk.StringVar()
        cb = ctk.CTkComboBox(s_card, variable=cb_var, values=filament_options, corner_radius=10, width=340, height=36, font=ctk.CTkFont(family=FONT_MAIN, size=12))
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

    ctk.CTkButton(btn_frame, text="确认扣减", height=40, corner_radius=20, fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32", font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold"), command=on_confirm).pack(side="right", padx=6)
    ctk.CTkButton(btn_frame, text="取消", height=40, corner_radius=20, fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold"), command=on_cancel).pack(side="right", padx=6)

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

# 提取模型名字与耗材数据解析
def extract_model_name_from_file(file_path):
    base_name = os.path.basename(file_path)
    # 去除后缀
    for ext in ['.gcode.3mf', '.gcode', '.3mf']:
        if base_name.lower().endswith(ext):
            base_name = base_name[:-len(ext)]
            break
    
    # 清理掉类似 _PLA_1h30m 或时间戳的杂质结尾
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
        m_vol = re.search(r';\s*(?:total\s+)?filament\s*volume\s*\[cm\^3\]\s*[:=]\s*([^\r\n]+)', text, re.IGNORECASE)
        if m_vol:
            vals = re.findall(r'[\d\.]+', m_vol.group(1))
            weights = [round(float(v) * 1.26, 2) for v in vals if float(v) > 0]
    return weights

def get_bambu_project_info(gcode_path):
    base_dir = os.path.dirname(os.path.abspath(gcode_path))
    project_root = os.path.dirname(base_dir) if "Metadata" in base_dir else base_dir
    slot_weights = []
    if os.path.exists(project_root):
        for root_dir, _, files in os.walk(project_root):
            for file in files:
                try:
                    with open(os.path.join(root_dir, file), 'r', encoding='utf-8', errors='ignore') as f:
                        weights = parse_multi_filament_weights(f.read())
                        if len(weights) > len(slot_weights):
                            slot_weights = weights
                except Exception:
                    pass
    if not slot_weights and os.path.exists(gcode_path):
        try:
            with open(gcode_path, 'r', encoding='utf-8', errors='ignore') as f:
                slot_weights = parse_multi_filament_weights(f.read())
        except Exception:
            pass
    return slot_weights

if __name__ == "__main__":
    if len(sys.argv) < 2:
        app = HyperOSFilamentApp()
        app.mainloop()
    else:
        cfg = load_config()
        gcode_path = sys.argv[-1]
        slot_weights = get_bambu_project_info(gcode_path)
        detected_model_name = extract_model_name_from_file(gcode_path)

        if slot_weights and sum(slot_weights) > 0:
            web_filaments = api_request(cfg["filaments_url"], cfg["api_key"], method="GET") or []
            is_confirmed, task_name, slot_map = ask_user_multi_slot_mapping_modern(
                slot_weights, web_filaments, detected_model_name=detected_model_name
            )

            if is_confirmed:
                time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
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