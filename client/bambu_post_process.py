import sys
import re
import json
import os
import glob
import time
import datetime
import urllib.request
import tkinter as tk
from tkinter import messagebox, ttk

# 默认占位符，首次运行会在同级目录下自动生成 config.json 供填写
DEFAULT_SERVER_URL = "http://你的服务器域名/api/ingest/script-report"
DEFAULT_FILAMENTS_URL = "http://你的服务器域名/api/ingest/script-filaments"
DEFAULT_API_KEY = "你的网页端专属APIKey"

BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
MAPPING_CACHE_FILE = os.path.join(BASE_DIR, "slot_mapping.json")

def load_config():
    config = {
        "server_url": DEFAULT_SERVER_URL,
        "filaments_url": DEFAULT_FILAMENTS_URL,
        "api_key": DEFAULT_API_KEY,
        "filament_id": 1
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_cfg = json.load(f)
                config.update(user_cfg)
        except Exception:
            pass
    else:
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return config

CFG = load_config()
SERVER_URL = CFG["server_url"]
GET_FILAMENTS_URL = CFG["filaments_url"]
API_KEY = CFG["api_key"]
DEFAULT_FILAMENT_ID = CFG.get("filament_id", 1)

def write_log(content):
    log_path = os.path.join(BASE_DIR, "log.txt")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(str(content) + "\n")
    except Exception:
        pass

def fetch_web_filaments():
    try:
        req = urllib.request.Request(GET_FILAMENTS_URL, headers={"X-API-Key": API_KEY})
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data
    except Exception as e:
        write_log(f"⚠️ 拉取网页耗材台账失败: {e}")
        return []

def parse_multi_filament_weights(text):
    weights = []
    m = re.search(r';\s*(?:total\s+)?filament\s*(?:weight|used)\s*\[g\]\s*[:=]\s*([^\r\n]+)', text, re.IGNORECASE)
    if m:
        raw_str = m.group(1).strip()
        vals = re.findall(r'[\d\.]+', raw_str)
        weights = [float(v) for v in vals if float(v) > 0]
    if not weights:
        m_vol = re.search(r';\s*(?:total\s+)?filament\s*volume\s*\[cm\^3\]\s*[:=]\s*([^\r\n]+)', text, re.IGNORECASE)
        if m_vol:
            vals = re.findall(r'[\d\.]+', m_vol.group(1))
            weights = [round(float(v) * 1.26, 2) for v in vals if float(v) > 0]
    return weights

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

def ask_user_multi_slot_mapping(slot_weights, web_filaments):
    user_choice = {"confirmed": False, "task_name": "", "slot_map": {}}
    slot_cache = load_slot_cache()

    root = tk.Tk()
    root.title("拓竹多色切片扣减助手")
    root.attributes('-topmost', True)

    window_width = 520
    window_height = 280 + (len(slot_weights) * 45)
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    total_w = sum(slot_weights)
    info_lbl = ttk.Label(
        frame, 
        text=f"🌈 检测到多色打印任务 (共 {len(slot_weights)} 色，总重: {total_w:.2f}g)\n请为每个切片槽位选择对应网页台账里的耗材：",
        font=("Microsoft YaHei", 10, "bold")
    )
    info_lbl.pack(anchor=tk.W, pady=(0, 10))

    name_frame = ttk.Frame(frame)
    name_frame.pack(fill=tk.X, pady=(0, 10))
    ttk.Label(name_frame, text="模型名称：", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
    task_name_var = tk.StringVar(value="Bambu_MultiColor_Model")
    entry_name = ttk.Entry(name_frame, textvariable=task_name_var, font=("Microsoft YaHei", 9))
    entry_name.pack(side=tk.LEFT, fill=tk.X, expand=True)
    entry_name.focus()
    entry_name.selection_range(0, tk.END)

    filament_options = []
    filament_id_map = {}
    for f in web_filaments:
        opt_str = f"ID:{f['id']} - {f.get('brand','')} {f.get('material','')} [{f.get('color_name','')}] (剩余:{f.get('current_weight_g',0)}g)"
        filament_options.append(opt_str)
        filament_id_map[opt_str] = f['id']

    if not filament_options:
        filament_options = ["ID:1 - 默认耗材档案"]
        filament_id_map["ID:1 - 默认耗材档案"] = 1

    combobox_vars = []
    for idx, w in enumerate(slot_weights):
        slot_idx = idx + 1
        s_frame = ttk.Frame(frame)
        s_frame.pack(fill=tk.X, pady=4)

        lbl_text = f"🎨 槽位 {slot_idx} (消耗 {w}g)  ➔  "
        ttk.Label(s_frame, text=lbl_text, font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        cb_var = tk.StringVar()
        cb = ttk.Combobox(s_frame, textvariable=cb_var, values=filament_options, state="readonly", font=("Microsoft YaHei", 9))
        cb.pack(side=tk.LEFT, fill=tk.X, expand=True)

        cached_id = slot_cache.get(str(slot_idx))
        matched_opt = None
        if cached_id:
            for opt in filament_options:
                if opt.startswith(f"ID:{cached_id} "):
                    matched_opt = opt
                    break

        if matched_opt:
            cb.set(matched_opt)
        else:
            def_idx = idx if idx < len(filament_options) else 0
            cb.set(filament_options[def_idx])

        combobox_vars.append((slot_idx, w, cb_var))

    def on_confirm():
        user_choice["confirmed"] = True
        user_choice["task_name"] = task_name_var.get().strip() or "Bambu_MultiColor_Model"
        
        new_cache = {}
        for slot_idx, w, cb_var in combobox_vars:
            selected_str = cb_var.get()
            selected_f_id = filament_id_map.get(selected_str, DEFAULT_FILAMENT_ID)
            user_choice["slot_map"][slot_idx] = {
                "filament_id": selected_f_id,
                "used_weight_g": w
            }
            new_cache[str(slot_idx)] = selected_f_id

        save_slot_cache(new_cache)
        root.destroy()

    def on_cancel():
        user_choice["confirmed"] = False
        root.destroy()

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(15, 0))

    ttk.Button(btn_frame, text="取消/不扣减", command=on_cancel).pack(side=tk.RIGHT, padx=(5, 0))
    ttk.Button(btn_frame, text="确认多色扣减", command=on_confirm).pack(side=tk.RIGHT)

    root.bind('<Return>', lambda event: on_confirm())
    root.bind('<Escape>', lambda event: on_cancel())
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    root.mainloop()
    return user_choice["confirmed"], user_choice["task_name"], user_choice["slot_map"]

def get_bambu_project_info(gcode_path):
    base_dir = os.path.dirname(os.path.abspath(gcode_path))
    project_root = os.path.dirname(base_dir) if "Metadata" in base_dir else base_dir

    slot_weights = []
    if os.path.exists(project_root):
        for root_dir, _, files in os.walk(project_root):
            for file in files:
                file_p = os.path.join(root_dir, file)
                try:
                    with open(file_p, 'r', encoding='utf-8', errors='ignore') as f:
                        weights = parse_multi_filament_weights(f.read())
                        if len(weights) > len(slot_weights):
                            slot_weights = weights
                except Exception:
                    pass
    return slot_weights, project_root

def main():
    write_log("=== 后处理脚本触发 ===")
    if len(sys.argv) < 2:
        write_log("❌ 未传入 G-code 路径")
        return

    gcode_path = sys.argv[-1]
    slot_weights, project_root = get_bambu_project_info(gcode_path)

    if not slot_weights or sum(slot_weights) <= 0:
        write_log("ℹ️ [切片预览阶段] 未解析到多色克重，静默跳过弹窗")
        return

    web_filaments = fetch_web_filaments()
    is_confirmed, task_name, slot_map = ask_user_multi_slot_mapping(slot_weights, web_filaments)

    if not is_confirmed:
        write_log("⛔ 用户取消了多色扣减。")
        return

    time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    for slot_idx, info in slot_map.items():
        f_id = info["filament_id"]
        w = info["used_weight_g"]
        full_task_name = f"{task_name}_槽{slot_idx}_{time_str}_{w}g.gcode"
        
        headers = {"Content-Type": "application/json", "X-API-Key": API_KEY}
        payload = {
            "filament_id": f_id,
            "used_weight_g": w,
            "task_name": full_task_name
        }

        try:
            req = urllib.request.Request(SERVER_URL, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=5) as response:
                res = json.loads(response.read().decode('utf-8'))
                write_log(f"✅ [多色扣减成功] 槽位{slot_idx} -> 网页耗材ID:{f_id} 扣除 {w}g，剩余: {res.get('remaining_weight_g')}g")
        except Exception as e:
            write_log(f"❌ 槽位{slot_idx} 上报失败: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        write_log(f"💥 崩溃捕获: {e}")
    sys.exit(0)