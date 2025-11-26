# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, colorchooser, filedialog, messagebox
from PIL import Image, ImageDraw, ImageFilter, ImageTk, ImageOps, ImageChops, ImageEnhance
import math, time, os, colorsys

# ========== Utility Functions ==========
def clamp(v, lo, hi): return max(lo, min(hi, v))
def distance(p1, p2): return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

def make_circle_mask(d, blur=0):
    """Create circular mask with optional blur effect"""
    m = Image.new("L", (d, d), 0); ImageDraw.Draw(m).ellipse((0,0,d-1,d-1), fill=255)
    if blur>0: m = m.filter(ImageFilter.GaussianBlur(blur)); return m
    return m

def make_ellipse_mask(w, h, blur=0, angle_deg=0):
    """Create elliptical mask with optional blur and rotation"""
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).ellipse((0,0,w-1,h-1), fill=255)
    if blur>0: m = m.filter(ImageFilter.GaussianBlur(blur))
    if angle_deg % 360: m = m.rotate(angle_deg, resample=Image.BICUBIC, expand=True)
    return m

def color_rgba(hex_color, alpha):
    """Convert hex color and alpha to RGBA tuple"""
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2],16), int(hex_color[2:4],16), int(hex_color[4:6],16), alpha)

# ========== Main Application ==========
class PainterApp(tk.Tk):
    """Circular canvas painting application with pencil texture brush"""
    
    # Built-in brush configuration (reserved for future extension)
    BUILTIN_BRUSH_FILES = {}

    def __init__(self):
        super().__init__()
        self.title("Painter - Circle Mode")

        # Canvas dimensions
        self.W = self.H = 720

        # Image layers: black background with white circle + transparent stroke layer
        self.main_img = Image.new("RGBA", (self.W, self.H), (0,0,0,255))
        ImageDraw.Draw(self.main_img).ellipse((0,0,self.W-1,self.H-1), fill=(255,255,255,255))
        self.stroke_layer = Image.new("RGBA", (self.W, self.H), (0,0,0,0))
        self.circle_mask = make_circle_mask(self.W)
        self.photo = ImageTk.PhotoImage(self.main_img)

        # Undo management
        self.undo_stack = []; self.undo_limit = 20

        # Brush state
        self.brush_color = "#222222"
        r_init = int(self.brush_color[1:3],16)/255.0
        g_init = int(self.brush_color[3:5],16)/255.0
        b_init = int(self.brush_color[5:7],16)/255.0
        self._h, self._s, self._v = colorsys.rgb_to_hsv(r_init,g_init,b_init)
        self.brush_type = tk.StringVar(value="铅笔纹理")
        
        # Color picker state
        self.color_picker_frame = None
        self._color_picker_open = False
        
        # Brush parameters
        self.brush_size = tk.IntVar(value=22)
        self.opacity = tk.IntVar(value=100)
        self.smoothing = tk.DoubleVar(value=0.28)

        # Custom brush support (reserved for extension)
        self.custom_brush_img = None
        self.spacing_pct = tk.IntVar(value=25)
        self._custom_cache = {}

        # Drawing state
        self.is_drawing = False
        self.points = []
        self.last_drawn_bbox = None

        # Frame rate limiting (60 FPS)
        self._last_refresh_ts = 0.0
        self._min_refresh_dt  = 1/60.0

        # UI layout management
        self.flow_items = []
        self._reflow_job = None
        self._last_flow_width = -1

        # Load built-in brushes
        self.builtin_brushes = self._load_builtin_brushes()

        self.build_ui()
        self.bind_hotkeys()
        self.after_idle(self._adjust_initial_geometry)
        self.after(600, self._auto_expand_if_needed)
        self.resizable(True, True)
        
        # Color picker performance cache
        self._last_sv_square_h = None
        self._last_sv_square_ts = 0.0
        self._sv_square_hue_step = 0.004
        self._sv_redraw_min_dt = 1/200.0
    def _load_builtin_brushes(self):
        brushes = {}
        base_dir = os.path.dirname(os.path.abspath(__file__))
        for name, relpath in self.BUILTIN_BRUSH_FILES.items():
            fp = os.path.join(base_dir, relpath)
            try:
                img = Image.open(fp).convert("RGBA")
                brushes[name] = img
            except Exception as e:
                print(f"[WARN] 内置笔刷 '{name}' 加载失败：{fp} -> {e}")
        return brushes

    # ========== UI Construction ==========
    def build_ui(self):
        # Canvas only (no parameter panel)
        self.draw_frame = ttk.Frame(self, padding=(8,4,8,8))
        self.draw_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.draw_frame, width=self.W, height=self.H, bg="black",
                                highlightthickness=0, highlightbackground="#000")
        # Fixed-size canvas, centered using place
        self.canvas.place(relx=0.5, rely=0.5, anchor="center")
        self.draw_frame.bind("<Configure>", lambda e: self._center_canvas())
        self.img_on_canvas = self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        # Hidden color preview widget for color picker compatibility
        if not hasattr(self, 'color_preview'):
            self.color_preview = tk.Label(self, width=2, background=self.brush_color)
            self.color_preview.place_forget()
        # Ensure color preview widget exists
        if not hasattr(self, 'color_preview'):
            self.color_preview = tk.Label(self, width=2, background=self.brush_color)
            self.color_preview.place_forget()

        # Mouse event bindings
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>",    self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        # Initialize overlay icons (undo & clear)
        self._init_overlay_icons()

    def _add_flow_item(self, w): self.flow_items.append(w)

    # ===== UI Widget Helpers =====
    def _group_label_combo(self, text, var, values):
        f = ttk.Frame(self.flow); ttk.Label(f, text=text).pack(side=tk.LEFT)
        cb = ttk.Combobox(f, width=18, textvariable=var, state="readonly", values=values)
        cb.pack(side=tk.LEFT, padx=(4,0)); return f

    def _group_label_spin(self, text, var, frm, to, inc=1.0, width=5):
        f = ttk.Frame(self.flow); ttk.Label(f, text=text).pack(side=tk.LEFT)
        s = ttk.Spinbox(f, from_=frm, to=to, increment=inc, textvariable=var, width=width)
        s.pack(side=tk.LEFT, padx=(4,0)); return f

    def _group_color(self, text):
        f = ttk.Frame(self.flow)
        ttk.Button(f, text=text, command=self.open_color_picker).pack(side=tk.LEFT)
        self.color_preview = tk.Label(f, width=2, background=self.brush_color, relief="groove")
        self.color_preview.pack(side=tk.LEFT, padx=(6,0))
        return f

    # ===== Responsive Layout =====
    def _on_root_configure(self, e):
        if e.widget is self:
            if self._reflow_job: self.after_cancel(self._reflow_job)
            self._reflow_job = self.after(80, self._do_reflow)

    def _do_reflow(self):
        self.update_idletasks()
        W = max(200, self.flow.winfo_width())
        if W == self._last_flow_width: return
        self._last_flow_width = W

        padx, pady = 6, 4
        for w in self.flow_items: w.grid_forget()

        row, col, x_used = 0, 0, 0
        for w in self.flow_items:
            w.update_idletasks()
            ww = w.winfo_reqwidth()
            if x_used > 0 and (x_used + ww + padx) > W:
                row, col, x_used = row+1, 0, 0
            w.grid(row=row, column=col, padx=(0, padx), pady=(0, pady), sticky="w")
            col += 1; x_used += ww + padx

    def _adjust_initial_geometry(self):
        # Set initial window size to match circular canvas
        pad = 40
        total_w = self.W + pad
        total_h = self.H + pad
        self.geometry(f"{int(total_w)}x{int(total_h)}")
        self.minsize(total_w, total_h)
        self._center_canvas()

    def _auto_expand_if_needed(self):
        # Auto-expand window if canvas is clipped
        try:
            f = self.canvas.master
        except Exception:
            return
        self.update_idletasks()
        need_w = self.W
        need_h = self.H
        cur_w = f.winfo_width()
        cur_h = f.winfo_height()
        if cur_w < need_w or cur_h < need_h:
            extra_w = max(0, need_w - cur_w) + 40
            extra_h = max(0, need_h - cur_h) + 40
            new_w = self.winfo_width() + extra_w
            new_h = self.winfo_height() + extra_h
            self.geometry(f"{new_w}x{new_h}")
            self.after(50, self._center_canvas)

    def _center_canvas(self):
        # Re-center fixed-size canvas
        try:
            self.canvas.place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            pass

    # ========== Overlay Icon Buttons ==========
    def _init_overlay_icons(self):
        """Initialize overlay icons for undo and clear operations"""
        """在圆形画布上方添加两个图标按钮：撤回 与 清空。
        图标文件：./icon/withdraw.jpg  ./icon/delete.jpg （相对当前脚本目录）。
        如果文件缺失则自动使用文字按钮作为回退方案。
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_dir = os.path.join(base_dir, 'icon')
        undo_path = os.path.join(icon_dir, 'withdraw.jpg')
        clear_path = os.path.join(icon_dir, 'delete.jpg')

        # 统一图标显示尺寸（相对于直径）
        icon_size = max(32, int(self.W * 0.07))  # 约占直径7%，不少于32

        def load_icon(fp):
            try:
                img = Image.open(fp).convert('RGBA')
                # 等比例缩放到 icon_size
                w, h = img.size
                scale = icon_size / max(w, h)
                nw, nh = max(1, int(w*scale)), max(1, int(h*scale))
                img = img.resize((nw, nh), Image.LANCZOS)
                return ImageTk.PhotoImage(img)
            except Exception:
                return None

        self._icon_undo_photo = load_icon(undo_path)
        self._icon_clear_photo = load_icon(clear_path)

        margin = max(14, int(self.W * 0.025))  # 与圆边距离；稍微增大便于贴边

        # —— 使用圆弧定位：选择三个角度（更分开 & 贴合圆边） ——
        # 中间颜色：270°（正下）; 撤回：270° 左偏 ~220°; 清空：270° 右偏 ~320°
        angle_deg_undo  = 120
        angle_deg_color = 90
        angle_deg_clear = 60
        cx = self.W / 2.0
        cy = self.H / 2.0
        # 有效半径：留 margin 和半个图标尺寸，避免出界
        effective_r = (self.W / 2.0) - margin - icon_size/2.0

        def polar(angle_deg):
            rad = math.radians(angle_deg)
            x = cx + math.cos(rad) * effective_r
            y = cy + math.sin(rad) * effective_r
            return int(x), int(y)

        undo_x, undo_y   = polar(angle_deg_undo)
        color_x, color_y = polar(angle_deg_color)
        clear_x, clear_y = polar(angle_deg_clear)

        # 中央当前颜色指示圆（沿圆弧）
        self._canvas_color_item = self.canvas.create_oval(
            color_x - icon_size//2, color_y - icon_size//2,
            color_x + icon_size//2, color_y + icon_size//2,
            fill=self.brush_color, outline='#ddd', width=2
        )
        # 单击打开颜色选择器
        self.canvas.tag_bind(self._canvas_color_item, '<Button-1>', lambda e: self.open_color_picker())
        self.canvas.tag_bind(self._canvas_color_item, '<Enter>', lambda e: self._hover_cursor(True))
        self.canvas.tag_bind(self._canvas_color_item, '<Leave>', lambda e: self._hover_cursor(False))

        # 如果加载成功，用图像；否则使用文字+背景
        if self._icon_undo_photo:
            self._canvas_undo_item = self.canvas.create_image(undo_x, undo_y, image=self._icon_undo_photo, anchor='center')
            # 改为双击触发撤回
            self.canvas.tag_bind(self._canvas_undo_item, '<Button-1>', lambda e: self.undo())
        else:
            self._canvas_undo_item = self.canvas.create_oval(undo_x-icon_size//2, undo_y-icon_size//2,
                                                             undo_x+icon_size//2, undo_y+icon_size//2,
                                                             fill='#444', outline='#ddd')
            txt = self.canvas.create_text(undo_x, undo_y, text='Undo', fill='white', font=('Arial', 10, 'bold'))
            self.canvas.tag_bind(self._canvas_undo_item, '<Button-1>', lambda e: self.undo())
            self.canvas.tag_bind(txt, '<Button-1>', lambda e: self.undo())
            # 记录文字元素以便点击判定
            self._canvas_undo_text = txt

        if self._icon_clear_photo:
            self._canvas_clear_item = self.canvas.create_image(clear_x, clear_y, image=self._icon_clear_photo, anchor='center')
            # 改为双击触发清空
            self.canvas.tag_bind(self._canvas_clear_item, '<Button-1>', lambda e: self.clear())
        else:
            self._canvas_clear_item = self.canvas.create_oval(clear_x-icon_size//2, clear_y-icon_size//2,
                                                              clear_x+icon_size//2, clear_y+icon_size//2,
                                                              fill='#444', outline='#ddd')
            txt2 = self.canvas.create_text(clear_x, clear_y, text='Clear', fill='white', font=('Arial', 10, 'bold'))
            self.canvas.tag_bind(self._canvas_clear_item, '<Button-1>', lambda e: self.clear())
            self.canvas.tag_bind(txt2, '<Button-1>', lambda e: self.clear())
            self._canvas_clear_text = txt2

        # 添加悬停提示（仅在图标存在或文字按钮上）
        self.canvas.tag_bind(self._canvas_undo_item, '<Enter>', lambda e: self._hover_cursor(True))
        self.canvas.tag_bind(self._canvas_undo_item, '<Leave>', lambda e: self._hover_cursor(False))
        self.canvas.tag_bind(self._canvas_clear_item, '<Enter>', lambda e: self._hover_cursor(True))
        self.canvas.tag_bind(self._canvas_clear_item, '<Leave>', lambda e: self._hover_cursor(False))

        # 收集所有覆盖按钮相关 item，供按下时过滤绘制
        items = [self._canvas_undo_item, self._canvas_clear_item, self._canvas_color_item]
        if hasattr(self, '_canvas_undo_text'): items.append(self._canvas_undo_text)
        if hasattr(self, '_canvas_clear_text'): items.append(self._canvas_clear_text)
        self._overlay_items = set(items)

    def _hover_cursor(self, inside):
        try:
            self.canvas.config(cursor='hand2' if inside else '')
        except Exception:
            pass

    # ========= 快捷键 =========
    def bind_hotkeys(self):
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-s>", lambda e: self.save())

    # ===== 圆形区域判定 =====
    def _inside_circle(self, x, y):
        cx = self.W/2.0; cy = self.H/2.0; r = self.W/2.0
        return (x-cx)**2 + (y-cy)**2 <= r*r

    # ========= 文件/颜色 =========
    def load_custom_brush(self):
        fp = filedialog.askopenfilename(
            title="Select Brush Image",
            filetypes=[("Images","*.png;*.jpg;*.jpeg;*.bmp;*.webp;*.gif"),("All Files","*.*")]
        )
        if not fp: return
        try: img = Image.open(fp).convert("RGBA")
        except Exception as e:
            messagebox.showerror("Load Brush", f"Failed to load image:\n{e}"); return
        self.custom_brush_img = img
        self._custom_cache.clear()
        self.brush_type.set("自定义笔刷（图片）")
        messagebox.showinfo("Brush Loaded", os.path.basename(fp))

    # ===== 自定义颜色选择器 =====
    def open_color_picker(self):
        if self._color_picker_open:
            return
        self._color_picker_open = True
        # 隐藏绘图区域
        self.draw_frame.pack_forget()
        # 创建取色器容器
        self.color_picker_frame = tk.Frame(self, bg="white")
        self.color_picker_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        # === 清理旧的画布元素引用（防止第二次打开复用失效的 item id） ===
        for _old in ['_wheel_marker','_picker_color_item','_sv_marker','_sv_inner','_sv_cross_h','_sv_cross_v','_sv_img_item']:
            if hasattr(self, _old):
                try: delattr(self, _old)
                except Exception: pass
        self._sv_canvas_ref = None
        self._wheel_canvas_ref = None

        outer = int(self.W)
        ring_thickness = max(24, int(outer * 0.115))
        inner_r = outer/2 - ring_thickness
        wheel_img = Image.new("RGBA", (outer, outer), (0,0,0,0))
        px = wheel_img.load(); cx = cy = outer/2
        for y in range(outer):
            for x in range(outer):
                dx = x - cx; dy = y - cy
                r = math.hypot(dx, dy)
                if inner_r < r <= outer/2:
                    ang = (math.degrees(math.atan2(dy, dx)) + 360) % 360
                    h = ang/360.0
                    r1,g1,b1 = colorsys.hsv_to_rgb(h,1,1)
                    px[x,y] = (int(r1*255), int(g1*255), int(b1*255), 255)
        self._wheel_photo = ImageTk.PhotoImage(wheel_img)
        wheel_canvas = tk.Canvas(self.color_picker_frame, width=outer, height=outer,
                                 highlightthickness=0, bg="white")
        wheel_canvas.pack(padx=4, pady=4)
        wheel_canvas.create_image(0,0, anchor='nw', image=self._wheel_photo)
        # 保存引用用于后续更新颜色指示圆
        self._wheel_canvas = wheel_canvas
        self._wheel_canvas_ref = wheel_canvas

        square_size = max(32, int(inner_r*math.sqrt(2)) - 8)
        self._sv_size = square_size
        self._sv_canvas = tk.Canvas(wheel_canvas, width=square_size, height=square_size,
                                    highlightthickness=1, highlightbackground="#888", bd=0, bg="white")
        self._sv_canvas.place(relx=0.5, rely=0.5, anchor='center')

        # --- 关键修复点 ---
        # 第二次打开时旧的 _sv_img_item / _sv_marker 等仍指向第一次的 Canvas 项目 ID，
        # 这些 ID 在新建的 Canvas 上无效，导致 _draw_sv_square 走 "itemconfig" 分支却没有真正创建图像。
        # 这里主动清理相关属性，强制重新创建。
        for _old in ['_sv_img_item', '_sv_marker', '_sv_inner', '_sv_cross_h', '_sv_cross_v']:
            if hasattr(self, _old):
                try: delattr(self, _old)
                except Exception: pass
        # 记录当前 SV Canvas 引用，用于后续判断是否需要重建图像
        self._sv_canvas_ref = self._sv_canvas

        h, s, v = self._h, self._s, self._v
        self._draw_sv_square(h)
        self._update_sv_marker(s, v)
        # 首次创建 Hue 指针（三角形），不再使用占位椭圆，避免后续 coords 出错
        self._update_wheel_marker(wheel_canvas, h, outer/2, inner_r)
        wheel_canvas.bind('<Button-1>', lambda e: self._wheel_click(e, wheel_canvas, outer/2, inner_r))
        wheel_canvas.bind('<B1-Motion>', lambda e: self._wheel_click(e, wheel_canvas, outer/2, inner_r))
        # 额外全局拖动绑定（防止某些平台 Canvas 不连续触发 B1-Motion）
        def _global_hue_drag(ev):
            if not self._color_picker_open: return
            # 将全局坐标转换到 wheel_canvas 局部
            x = ev.x_root - wheel_canvas.winfo_rootx()
            y = ev.y_root - wheel_canvas.winfo_rooty()
            # 构造一个简单事件对象
            class _E: pass
            e = _E(); e.x = x; e.y = y
            self._wheel_click(e, wheel_canvas, outer/2, inner_r)
        self._hue_global_bind_id = self.bind('<B1-Motion>', _global_hue_drag)
        self._sv_canvas.bind('<Button-1>', self._sv_click)
        self._sv_canvas.bind('<B1-Motion>', self._sv_click)

        # ===== 恢复：左侧当前色预览 + 右侧确认按钮 =====
        self._pending_color = self.brush_color  # 暂存待确认颜色
        center = outer/2
        square_left  = center - square_size/2
        square_right = center + square_size/2
        gap_w = outer - square_size
        icon_side = max(32, min(int(ring_thickness*0.85), int(gap_w*0.4)))
        margin_icon = max(6, int(icon_side*0.15))
        # 左侧预览圆
        preview_color = self.brush_color
        color_x = square_left - icon_side/2 - margin_icon
        color_y = center
        self._picker_color_item = wheel_canvas.create_oval(
            color_x - icon_side/2, color_y - icon_side/2,
            color_x + icon_side/2, color_y + icon_side/2,
            fill=preview_color, outline='#ddd', width=2
        )
        wheel_canvas.tag_bind(self._picker_color_item, '<Enter>', lambda e: wheel_canvas.config(cursor='hand2'))
        wheel_canvas.tag_bind(self._picker_color_item, '<Leave>', lambda e: wheel_canvas.config(cursor=''))
        # 右侧确认按钮：优先加载图片；失败则绘制简易“✔”
        try:
            confirm_fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon', 'confirm.jpg')
            img = Image.open(confirm_fp).convert('RGBA').resize((icon_side, icon_side), Image.LANCZOS)
            self._confirm_photo = ImageTk.PhotoImage(img)
            icon_x = square_right + icon_side/2 + margin_icon
            icon_y = center
            self._confirm_item = wheel_canvas.create_image(icon_x, icon_y, image=self._confirm_photo, anchor='center')
        except Exception:
            icon_x = square_right + icon_side/2 + margin_icon
            icon_y = center
            self._confirm_item = wheel_canvas.create_oval(icon_x-icon_side/2, icon_y-icon_side/2,
                                                          icon_x+icon_side/2, icon_y+icon_side/2,
                                                          fill='#222', outline='white', width=2)
            # 画简单对勾
            s = icon_side/2.8
            wheel_canvas.create_line(icon_x-s*0.6, icon_y, icon_x-s*0.15, icon_y+s*0.55,
                                     icon_x+s*0.7, icon_y-s*0.6, fill='white', width=2, capstyle='round', joinstyle='round')
        wheel_canvas.tag_bind(self._confirm_item, '<Button-1>', lambda e: self._apply_color_and_close())
        wheel_canvas.tag_bind(self._confirm_item, '<Enter>', lambda e: wheel_canvas.config(cursor='hand2'))
        wheel_canvas.tag_bind(self._confirm_item, '<Leave>', lambda e: wheel_canvas.config(cursor=''))
        # ESC 取消（不应用）
        self.bind('<Escape>', lambda e: self._close_color_picker())

    def _close_color_picker(self):
        if self.color_picker_frame is not None:
            self.color_picker_frame.destroy()
            self.color_picker_frame = None
        if not self.draw_frame.winfo_ismapped():
            self.draw_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        self._color_picker_open = False
        # 解除全局拖动绑定
        try:
            if hasattr(self, '_hue_global_bind_id') and self._hue_global_bind_id:
                self.unbind('<B1-Motion>', self._hue_global_bind_id)
                self._hue_global_bind_id = None
        except Exception:
            pass

    def _apply_color_and_close(self):
        # 应用待确认颜色
        final_color = getattr(self, '_pending_color', self.brush_color)
        self.brush_color = final_color
        if hasattr(self, 'color_preview'):
            try: self.color_preview.config(background=final_color)
            except Exception: pass
        # 更新底部中央颜色指示圆
        try:
            if hasattr(self, '_canvas_color_item'):
                self.canvas.itemconfig(self._canvas_color_item, fill=final_color)
        except Exception: pass
        self._close_color_picker()

    def _wheel_click(self, event, canvas, R, inner_r):
        # 计算点击到的角决定 hue
        cx = R; cy = R
        dx = event.x - cx; dy = event.y - cy
        r = math.hypot(dx, dy)
        if r < inner_r or r > R:  # 不在环上
            return
        ang = (math.degrees(math.atan2(dy, dx)) + 360) % 360
        self._h = ang/360.0
        # 节流刷新 SV 方块
        self._maybe_update_sv_square(self._h)
        self._update_wheel_marker(canvas, self._h, R, inner_r)
        # 不改变 s,v 只更新预览临时色
        r1,g1,b1 = colorsys.hsv_to_rgb(self._h, self._s, self._v)
        preview = f"#{int(r1*255):02x}{int(g1*255):02x}{int(b1*255):02x}"
        # 仅更新“待确认”颜色与预览，不立即应用到主画笔
        self._pending_color = preview
        if hasattr(self, 'color_preview'):
            try: self.color_preview.config(background=preview)
            except Exception: pass
        # 左侧预览圆
        try:
            if hasattr(self, '_picker_color_item'):
                canvas.itemconfig(self._picker_color_item, fill=preview)
        except Exception: pass

    def _draw_sv_square(self, h):
        size = self._sv_size
        img = Image.new('RGB', (size, size))
        for y in range(size):
            v = 1 - y / (size-1)
            for x in range(size):
                s = x / (size-1)
                r,g,b = colorsys.hsv_to_rgb(h, s, v)
                img.putpixel((x,y),(int(r*255), int(g*255), int(b*255)))
        self._sv_photo = ImageTk.PhotoImage(img)
        # 如果之前的 _sv_img_item 属于旧 Canvas，则必须重新创建
        reuse = False
        if getattr(self, '_sv_img_item', None) is not None and getattr(self, '_sv_canvas_ref', None) is self._sv_canvas:
            try:
                self._sv_canvas.itemconfig(self._sv_img_item, image=self._sv_photo)
                reuse = True
            except Exception:
                reuse = False
        if not reuse:
            try:
                self._sv_img_item = self._sv_canvas.create_image(0,0, anchor='nw', image=self._sv_photo)
                self._sv_canvas_ref = self._sv_canvas
            except Exception:
                pass
        self._last_sv_square_h = h
        self._last_sv_square_ts = time.time()

    def _maybe_update_sv_square(self, h):
        now = time.time()
        if self._last_sv_square_h is None:
            self._draw_sv_square(h); return
        if abs(h - self._last_sv_square_h) >= self._sv_square_hue_step or (now - self._last_sv_square_ts) >= self._sv_redraw_min_dt:
            self._draw_sv_square(h)

    def _sv_click(self, event):
        size = self._sv_size
        x = max(0, min(size-1, event.x))
        y = max(0, min(size-1, event.y))
        self._s = x/(size-1)
        self._v = 1 - y/(size-1)
        self._update_sv_marker(self._s, self._v)
        r,g,b = colorsys.hsv_to_rgb(self._h, self._s, self._v)
        hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        # 仅更新待确认颜色与预览
        self._pending_color = hex_color
        if hasattr(self, 'color_preview'):
            try: self.color_preview.config(background=hex_color)
            except Exception: pass
        try:
            if hasattr(self, '_picker_color_item'):
                self._wheel_canvas.itemconfig(self._picker_color_item, fill=hex_color)
        except Exception: pass

    def _update_wheel_marker(self, canvas, h, R, inner_r):
        # Hue 三角指针：指向当前 hue 的环中间半径位置
        ang = h * 2 * math.pi
        mid_r = (R + inner_r) / 1.9
        tip_x = R + math.cos(ang) * mid_r
        tip_y = R + math.sin(ang) * mid_r
        # 三角基底朝向圆心稍外侧：沿法线（垂直于指向角）偏移
        normal_ang = ang + math.pi/2
        base_offset = 15  # 三角底边半宽
        back_offset = 25  # 三角向内（圆心方向）回退距离
        base_center_x = tip_x - math.cos(ang) * back_offset
        base_center_y = tip_y - math.sin(ang) * back_offset
        p1_x = base_center_x + math.cos(normal_ang) * base_offset
        p1_y = base_center_y + math.sin(normal_ang) * base_offset
        p2_x = base_center_x - math.cos(normal_ang) * base_offset
        p2_y = base_center_y - math.sin(normal_ang) * base_offset
        points = [tip_x, tip_y, p1_x, p1_y, p2_x, p2_y]
        # 删除旧指针
        # 计算对比描边色（基于最终当前色）
        r_c,g_c,b_c = colorsys.hsv_to_rgb(h, self._s, self._v)
        lum = (0.299*r_c + 0.587*g_c + 0.114*b_c)
        # 指针描边改为始终白色以增强可见性
        outline = 'white'
        fill_hex = f"#{int(r_c*255):02x}{int(g_c*255):02x}{int(b_c*255):02x}"
        need_new = True
        if getattr(self, '_wheel_marker', None) is not None and getattr(self, '_wheel_canvas_ref', None) is canvas:
            try:
                canvas.coords(self._wheel_marker, *points)
                canvas.itemconfig(self._wheel_marker, fill=fill_hex, outline=outline)
                need_new = False
            except Exception:
                need_new = True
        if need_new:
            try:
                self._wheel_marker = canvas.create_polygon(points, fill=fill_hex, outline=outline, width=2, smooth=True)
                self._wheel_canvas_ref = canvas
            except Exception:
                return  # 创建失败直接返回
        # 保持在最上层
        try:
            canvas.tag_raise(self._wheel_marker)
        except Exception:
            pass

    def _update_sv_marker(self, s, v):
        size = self._sv_size
        x = s*(size-1)
        y = (1-v)*(size-1)
        # 删除旧 marker
        # 仅在首次创建，后续直接移动与更新属性
        # 颜色与指示点（指示点始终使用白色描边）
        r_c,g_c,b_c = colorsys.hsv_to_rgb(self._h, s, v)
        fill_hex = f"#{int(r_c*255):02x}{int(g_c*255):02x}{int(b_c*255):02x}"
        if not hasattr(self, '_sv_marker'):
            self._sv_marker = self._sv_canvas.create_oval(x-7, y-7, x+7, y+7, outline='white', width=2)
            self._sv_inner = self._sv_canvas.create_oval(x-4, y-4, x+4, y+4, outline='white', fill=fill_hex)
            self._sv_cross_h = self._sv_canvas.create_line(0, y, size, y, fill='white')
            self._sv_cross_v = self._sv_canvas.create_line(x, 0, x, size, fill='white')
        else:
            self._sv_canvas.coords(self._sv_marker, x-7, y-7, x+7, y+7)
            self._sv_canvas.coords(self._sv_inner, x-4, y-4, x+4, y+4)
            self._sv_canvas.itemconfig(self._sv_inner, fill=fill_hex)
            self._sv_canvas.coords(self._sv_cross_h, 0, y, size, y)
            self._sv_canvas.coords(self._sv_cross_v, x, 0, x, size)

    # ========== Drawing Events ==========
    def on_press(self, event):
        # Ignore clicks on overlay icons
        try:
            if hasattr(self, '_overlay_items'):
                clicked = self.canvas.find_withtag('current')
                if clicked and clicked[0] in self._overlay_items:
                    return
        except Exception:
            pass
        if not (0 <= event.x < self.W and 0 <= event.y < self.H): return
        if not self._inside_circle(event.x, event.y): return
        if len(self.undo_stack) >= self.undo_limit: self.undo_stack.pop(0)
        self.undo_stack.append(self.main_img.copy())

        self.is_drawing = True
        self.points = [(event.x, event.y, time.time())]
        self.stroke_layer = Image.new("RGBA", (self.W, self.H), (0,0,0,0))
        self.last_drawn_bbox = None

        # Initial stamp
        self._stamp_at((event.x, event.y), prev=None)
        self.refresh_display(force=True)

    def on_drag(self, event):
        if not self.is_drawing: return
        x, y = clamp(event.x, 0, self.W-1), clamp(event.y, 0, self.H-1)
        if not self._inside_circle(x, y):
            return
        t = time.time()
        prev = self.points[-1]
        self.points.append((x, y, t))

        if self.brush_type.get() == "自定义笔刷（图片）":
            step = max(1, int(self.brush_size.get() * (self.spacing_pct.get()/100.0)))
        else:
            step = max(1, int(self.brush_size.get() * self.smoothing.get()))

        px, py, _ = prev
        dx, dy = x - px, y - py
        seg_len = math.hypot(dx, dy)

        if seg_len == 0:
            self._stamp_at((x, y), prev=prev)
        else:
            n = max(1, int(seg_len // step))
            for i in range(1, n+1):
                ix = px + dx * (i/n); iy = py + dy * (i/n)
                self._stamp_at((ix, iy), prev=prev)
                prev = (ix, iy, t)

        self.refresh_display()

    def on_release(self, event):
        if not self.is_drawing: return
        self.is_drawing = False

        # Clip stroke layer to circular area before merging
        if hasattr(self, 'circle_mask') and self.stroke_layer.getbbox():
            a = self.stroke_layer.split()[-1]
            a = ImageChops.multiply(a, self.circle_mask)
            masked = self.stroke_layer.copy(); masked.putalpha(a)
        else:
            masked = self.stroke_layer
        self.main_img = Image.alpha_composite(self.main_img, masked)
        self.stroke_layer = Image.new("RGBA", (self.W, self.H), (0,0,0,0))
        self.refresh_display(force=True)

    # ========== Display Refresh (Rate-Limited) ==========
    def refresh_display(self, force=False):
        now = time.time()
        if not force and (now - self._last_refresh_ts) < self._min_refresh_dt:
            return
        self._last_refresh_ts = now
        # Clip stroke layer to prevent rendering outside circle
        if hasattr(self, 'circle_mask') and self.stroke_layer.getbbox():
            a = self.stroke_layer.split()[-1]
            a = ImageChops.multiply(a, self.circle_mask)
            masked = self.stroke_layer.copy(); masked.putalpha(a)
            merged = Image.alpha_composite(self.main_img, masked)
        else:
            merged = Image.alpha_composite(self.main_img, self.stroke_layer)
        self.photo = ImageTk.PhotoImage(merged)
        self.canvas.itemconfig(self.img_on_canvas, image=self.photo)

    # ========== Core Rendering ==========
    def _stamp_at(self, pos, prev):
        """Render brush stamp at position with selected brush type"""
        x, y = pos
        size  = int(self.brush_size.get())
        alpha = int(clamp(self.opacity.get(),1,100) * 2.55)
        brush = self.brush_type.get()

        # Pencil texture (default brush)
        if brush == "铅笔纹理":
            m_soft = make_circle_mask(size, blur=max(1, size//10))
            noise = ImageOps.autocontrast(Image.effect_noise(m_soft.size, 48.0))
            noise_bright = ImageEnhance.Brightness(noise).enhance(1.3)
            final_alpha = ImageChops.multiply(m_soft, noise_bright)
            if alpha < 255: final_alpha = ImageEnhance.Brightness(final_alpha).enhance(alpha/255.0)
            stamp = Image.new("RGBA", m_soft.size, color_rgba(self.brush_color, 255)); stamp.putalpha(final_alpha)

        # Custom brush from image (reserved for extension)
        elif brush == "自定义笔刷（图片）" and self.custom_brush_img is not None:
            stamp = self._make_stamp_from_image(self.custom_brush_img, size, alpha, key_prefix="__custom__")

        # Fallback: simple circular brush
        else:
            mask = make_circle_mask(size, blur=max(0, size//16))
            stamp = Image.new("RGBA", mask.size, color_rgba(self.brush_color, alpha)); stamp.putalpha(mask)

        sx, sy = int(x - stamp.size[0]//2), int(y - stamp.size[1]//2)
        self.stroke_layer.paste(stamp, (sx, sy), stamp)
        bbox = (sx, sy, sx+stamp.size[0], sy+stamp.size[1])
        if self.last_drawn_bbox is None: self.last_drawn_bbox = bbox
        else:
            self.last_drawn_bbox = (min(self.last_drawn_bbox[0], bbox[0]),
                                    min(self.last_drawn_bbox[1], bbox[1]),
                                    max(self.last_drawn_bbox[2], bbox[2]),
                                    max(self.last_drawn_bbox[3], bbox[3]))

    # ========== Image Brush Helper ==========
    def _make_stamp_from_image(self, src, size, global_alpha, key_prefix=""):
        """Generate brush stamp from image with caching"""
        sw, sh = src.size
        if sw >= sh: nw, nh = size, max(1, int(sh * size / sw))
        else:        nh, nw = size, max(1, int(sw * size / sh))
        key = (key_prefix, nw, nh)
        if key in self._custom_cache:
            stamp_base = self._custom_cache[key].copy()
        else:
            brush = src.resize((nw, nh), resample=Image.BICUBIC)
            if "A" in brush.getbands(): alpha_mask = brush.split()[-1]
            else: alpha_mask = ImageOps.invert(brush.convert("L"))
            color_img = Image.new("RGBA", brush.size, color_rgba(self.brush_color, 255))
            stamp_base = color_img; stamp_base.putalpha(alpha_mask)
            self._custom_cache[key] = stamp_base.copy()
        if global_alpha < 255:
            a = stamp_base.split()[-1]
            a = ImageEnhance.Brightness(a).enhance(global_alpha/255.0)
            stamp_base = stamp_base.copy(); stamp_base.putalpha(a)
        return stamp_base

    # ========== User Operations ==========
    def refresh_display_force(self): self.refresh_display(force=True)

    def undo(self):
        """Undo last drawing operation"""
        if not self.undo_stack: return
        self.main_img = self.undo_stack.pop()
        self.stroke_layer = Image.new("RGBA", (self.W, self.H), (0,0,0,0))
        self.refresh_display(force=True)

    def clear(self):
        """Clear canvas and reset to white circle"""
        self.main_img = Image.new("RGBA", (self.W, self.H), (0,0,0,255))
        ImageDraw.Draw(self.main_img).ellipse((0,0,self.W-1,self.H-1), fill=(255,255,255,255))
        self.stroke_layer = Image.new("RGBA", (self.W, self.H), (0,0,0,0))
        self.undo_stack.clear()
        self.refresh_display(force=True)

    def save(self):
        """Save canvas to file (PNG/JPEG)"""
        fp = filedialog.asksaveasfilename(defaultextension=".png",
            filetypes=[("PNG Image","*.png"),("JPEG Image","*.jpg;*.jpeg"),("All Files","*.*")])
        if not fp: return
        merged = Image.alpha_composite(self.main_img, self.stroke_layer)
        if fp.lower().endswith((".jpg",".jpeg")): merged = merged.convert("RGB")
        merged.save(fp); messagebox.showinfo("Saved", f"Saved:\n{fp}")

if __name__ == "__main__":
    app = PainterApp()
    app.mainloop()
