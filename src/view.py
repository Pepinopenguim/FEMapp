import tkinter as tk
import tkinter.ttk as ttk
import TKinterModernThemes as tmt
from tkinter import simpledialog, filedialog
from math import cos, sin
from typing import Literal, Callable
from PIL import Image, ImageTk

from typing import List, Tuple, Dict

class MainView:
    # ============================
    # SETUP AND BUILDERS 
    # ============================
    def __init__(self):

        self.root = tmt.ThemedTKinterFrame(
            title="CaST",
            theme="azure",
            mode="dark",
            usecommandlineargs=False,
        )
        
        self.start_width, self.start_height = 1400, 900

        self.root.master.geometry(f"{self.start_width}x{self.start_height}")

        self.preview_item_ids = []
        
        # load image and resize it to wanted size
        img = Image.open(r"assets/cast_wtext.png")        
        w = 200 # pxls
        h = int(img.height * w / img.width)
        img = img.resize((w, h), Image.Resampling.LANCZOS,)

        self.watermark = ImageTk.PhotoImage(img)

        self._build_ui()

    def _build_ui(self):

        self.main_frame = ttk.Frame(self.root.master)
        self.main_frame.pack(fill="both", expand=True)

        self._build_toolbar()
        self._build_canvas()
        self._build_logbar()

    def _build_toolbar(self):

        toolbar = ttk.Frame(self.main_frame)
        toolbar.pack(fill="x")
    
        self.file_btn = ttk.Menubutton(
            toolbar,
            text="📁 File"
        )

        self.file_menu = tk.Menu(
            self.file_btn,
            tearoff=False
        )

        self.file_btn["menu"] = self.file_menu

        self.file_btn.pack(
            side="left",
            padx=4,
            pady=4
        )
        
        self.mode_text_var = tk.StringVar(value="✏️ Node")
        self.mode_btn = ttk.Menubutton(
            toolbar,
            textvariable=self.mode_text_var
        )

        self.mode_menu = tk.Menu(
            self.mode_btn,
            tearoff=False
        )

        self.mode_btn["menu"] = self.mode_menu

        self.mode_btn.pack(
            side="left",
            padx=4
        )

        self.is_external_var = tk.BooleanVar(value=False) # Default to False (Internal)
        
        # === boundary group manager ===
        self.edge_container = ttk.Frame(toolbar)
        self.edge_container.pack(side="left", padx=10)
        self.boundary_var = tk.StringVar(value="external")
        
        # The Dropdown
        self.boundary_cb = ttk.Combobox(
            self.edge_container,
            textvariable=self.boundary_var,
            values=["external"],
            state="readonly",
            width=12
        )
        self.boundary_cb.pack(side="left")

        # The Add Hole Button
        self.add_hole_btn = ttk.Button(
            self.edge_container,
            text="+",
            width=2, # binded from controller
        )
        self.add_hole_btn.pack(side="left", padx=(5, 0))

        # == Support Container ==
        self.support_container = ttk.Frame(toolbar)

        self.fix_x_var = tk.BooleanVar(value=True)
        self.fix_y_var = tk.BooleanVar(value=True)
        self.fix_z_var = tk.BooleanVar(value=False)

        self.fix_x_cb = ttk.Checkbutton(
            self.support_container,
            text="Fix X",
            variable=self.fix_x_var,
            command=self._support_var_helper
        )

        self.fix_y_cb = ttk.Checkbutton(
            self.support_container,
            text="Fix Y",
            variable=self.fix_y_var,
            command=self._support_var_helper
        )

        self.fix_z_cb = ttk.Checkbutton(
            self.support_container,
            text="Fix θ",
            variable=self.fix_z_var,
            command=self._support_var_helper
        )
        for widget in [self.fix_x_cb, self.fix_y_cb]: widget.pack(side="left", padx=(5, 0))

        # === force items ===
        self.force_container = ttk.Frame(toolbar)

        # -- nodes --
        self.force_node_frame = ttk.Frame(self.force_container)

        self.fx_var = tk.DoubleVar(value=0.0)
        self.fy_var = tk.DoubleVar(value=0.0)
        self.m_var = tk.DoubleVar(value=0.0) 
        # NOTE - Removed from software because is never actually used
        # kept in case i want to define a beam solver

        for text, var in [("Fx [f]:", self.fx_var), ("Fy [f]:", self.fy_var)]:
            f = ttk.Frame(self.force_node_frame)
            f.pack(side="left", padx=5)
            ttk.Label(f, text=text).pack(side="left", padx=(0, 2))
            ttk.Entry(f, textvariable=var, width=8).pack(side="left")

        # -- edges --
        self.force_edge_frame = ttk.Frame(self.force_container)
        
        self.edge_dir_var = tk.StringVar(value="Normal")
        self.q_start_var = tk.DoubleVar(value=0.0)
        self.q_end_var = tk.DoubleVar(value=0.0)
        self.edge_ang_var = tk.DoubleVar(value=0.0)
        self.edge_m_var = tk.DoubleVar(value=0.0)

        # Direction Dropdown (Normal vs Global Angle)
        self.dir_cb = ttk.Combobox(
            self.force_edge_frame, 
            textvariable=self.edge_dir_var, 
            values=["Normal", "Global"], 
            state="readonly", 
            width=8
        )
        self.dir_cb.pack(side="left", padx=5)

        for text, var in [("Start [f/u]:", self.q_start_var), ("End [f/u]:", self.q_end_var), ("Ang [°]:", self.edge_ang_var),]:
            f = ttk.Frame(self.force_edge_frame)
            f.pack(side="left", padx=5)
            ttk.Label(f, text=text).pack(side="left", padx=(0, 2))
            ttk.Entry(f, textvariable=var, width=8).pack(side="left")

        # === mesh items ===

        self.mesh_container = ttk.Frame(toolbar)
        self.mesh_container.pack(side="left", padx=10)
        self.mesh_slider_var = tk.DoubleVar()

        self.mesh_slider = ttk.Scale(
            self.mesh_container,
            from_=-10,
            to=10,
            orient="horizontal",
            variable=self.mesh_slider_var,
        )
        self.mesh_slider.pack(side="left", padx=10)

        self.solver_method_var = tk.StringVar(value="Plane Strain")
        ttk.Combobox(
            self.mesh_container,
            textvariable=self.solver_method_var,
            state="readonly",
            values=[
                "Plane Strain",
                "Plane Stress",
            ]
        ).pack(side="left", padx=10)

        self.run_solver_btn = ttk.Button(
            self.mesh_container,
            text="Solve",
        )
        self.run_solver_btn.pack(side="left", padx=15)

        # === material items ===
        self.material_container = ttk.Frame(toolbar)
        self.material_container.pack(side="left", padx=10)
        
        self.E_double_var = tk.DoubleVar(value=1.0)
        self.poisson_double_var = tk.DoubleVar(value=0.1)
        self.gamma_double_var = tk.DoubleVar(value=0.0)
        self.h_double_var = tk.DoubleVar(value=1.0)

        for text, var in [
            ("E (Young's Module)[f/u²]:", self.E_double_var),
            ("ν (Poisson's ratio):", self.poisson_double_var),
            ("γ (Specific Weight)[f/u³]:", self.gamma_double_var),
            ("h (width) [u]:", self.h_double_var),
        ]:
            f = ttk.Frame(self.material_container)
            f.pack(side="left", padx=5)
            ttk.Label(f, text=text).pack(side="left", padx=(0, 2))
            ttk.Entry(f, textvariable=var, width=8).pack(side="left")

        self.apply_material_btn = ttk.Button(
            self.material_container,
            text="Apply"
        )
        
        self.apply_material_btn.pack(side="left", padx=10)

        # == results ==
        self.results_container = tk.Frame(toolbar)

        ttk.Label(self.results_container, text="Scale:").pack(side="left")
        self.scale_slider_var = tk.DoubleVar() # defines pxl size of max displacement
        self.scale_slider = ttk.Scale(
            self.results_container, from_=1.0, to=300.0, 
            orient="horizontal", variable=self.scale_slider_var, length=150
        )
        self.scale_slider.pack(side="left", padx=10)

        self.heatmap_metric_var = tk.StringVar(value="Disp (Avg)")
        self.heatmap_btn = ttk.Menubutton(
            self.results_container,
            textvariable=self.heatmap_metric_var
        )
        self.heatmap_menu = tk.Menu(self.heatmap_btn, tearoff=False)
        self.heatmap_btn["menu"] = self.heatmap_menu
        self.heatmap_btn.pack(side="left", padx=10)

        self.disp_menu = tk.Menu(self.heatmap_menu, tearoff=False)
        self.heatmap_menu.add_cascade(label="Displacements", menu=self.disp_menu)

        self.stress_menu = tk.Menu(self.heatmap_menu, tearoff=False)
        self.heatmap_menu.add_cascade(label="Stress", menu=self.stress_menu)
        
        # on startup, mode is node
        self.set_toolbar_visibility("node")

        self.settings_btn = ttk.Button(
            toolbar,
            text="⚙️"
        )

        self.settings_btn.pack(
            side="right",
            padx=5
        )

    def _build_canvas(self):

        canvas_frame = ttk.Frame(self.main_frame)

        canvas_frame.pack(
            fill="both",
            expand=True
        )

        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#202020",
            highlightthickness=0
        )

        self.canvas.pack(
            fill="both",
            expand=True
        )

    def _build_logbar(self):
        logbar = ttk.Frame(self.main_frame)
        logbar.pack(fill="x")

        # === logs ===
        self.log_text_var = tk.StringVar(value="")
        self.log_label = ttk.Label(
            logbar, 
            textvariable=self.log_text_var,
            font=("Consolas", 16)
        )
        self.log_label.pack(side="left", padx=4)

    def set_toolbar_visibility(self, mode: str, submode: str | None = None):
        """
        Updates the toolbar based on the active mode and submode.
        """
        all_containers = {
            self.edge_container, 
            self.mesh_container, 
            self.support_container, 
            self.force_container,
            self.material_container,
            self.results_container
        }

        # Hide everything first
        for widget in all_containers:
            widget.pack_forget()

        mapper = {
            "edge": self.edge_container,
            "mesh": self.mesh_container,
            "support": self.support_container,
            "force": self.force_container,
            "material": self.material_container,
            "results": self.results_container,
        }

        active_container = mapper.get(mode)
        if active_container:
            active_container.pack(side="left", padx=10, after=self.mode_btn)

        if mode == "force" and submode:
            self._sync_force_submode(submode)

    # ============================
    # BINDINGS 
    # ============================
    def bind_mesh_change(self, callback):

        self.mesh_slider.config(command=lambda _: callback(self.mesh_slider_var.get()))

    def bind_boundary_change(self, callback: Callable[[str], None]):
        self.boundary_cb.bind(
            "<<ComboboxSelected>>",
            lambda _: callback(self.boundary_var.get())
        )

    def bind_apply_material_btn(self, callback: Callable[[float, float, float], None]):
        
        def internal_handler():
            # These are now evaluated ONLY when the button is clicked!
            E = self._safe_get_double(self.E_double_var)
            nu = self._safe_get_double(self.poisson_double_var)
            gamma = self._safe_get_double(self.gamma_double_var)
            h = self._safe_get_double(self.h_double_var)
            
            callback(E, nu, gamma, h)

        self.apply_material_btn.config(
            command=internal_handler
        )

    def bind_run_solver_btn(self, callback: Callable[[str], None]):
        def internal_handler():
            # get combobox value
            method = self.solver_method_var.get()
            callback(method)

        self.run_solver_btn.config(
            command=internal_handler
        )

    def bind_file_change(self, callback: Callable[[str, str], None]):

        self.file_menu.add_command(
            label="Open",
            command=lambda: callback(
                "open",
                filedialog.askopenfilename(
                    title='Open',
                    filetypes=[
                        ('json files', '*.json'),
                        ('All files', '*.*')
                        ]
                    )
                ),
            )
        self.file_menu.add_command(
            label="Save",
            command=lambda: callback(
                "save",
                filedialog.asksaveasfilename(
                    title='Save as json file',
                    filetypes=[
                        ('json files', '*.json'),
                        ('All files', '*.*')
                        ]
                    )
                )
            )
        
    def bind_mode_change(self, callback):
        """Passes the selected string mode and sub-mode to the controller."""
        
        # 1. Main Node mode
        self.mode_menu.add_command(
            label="Node", 
            command=lambda: callback("node", None)
        )
        
        # 2. Create the Edge Sub-menu
        self.edge_menu = tk.Menu(self.mode_menu, tearoff=False)
        self.edge_menu.add_command(
            label="Linear", 
            command=lambda: callback("edge", "linear")
        )
        self.edge_menu.add_command(
            label="Parabola", 
            command=lambda: callback("edge", "parabola")
        )
        self.edge_menu.add_command(
            label="Circle", 
            command=lambda: callback("edge", "circle")
        )

        # Attach the sub-menu to the main menu
        self.mode_menu.add_cascade(label="Edge", menu=self.edge_menu)

        # 3. Support mode
        self.support_menu = tk.Menu(self.mode_menu, tearoff=False)
        self.support_menu.add_command(
            label="At Node",
            command=lambda: callback("support", "node")
        )
        self.support_menu.add_command(
            label="At Edge",
            command=lambda: callback("support", "edge")
        )

        # attach sub menu
        self.mode_menu.add_cascade(label="Support", menu=self.support_menu)

        # 4. Force mode
        self.force_menu = tk.Menu(self.mode_menu, tearoff=False)
        self.force_menu.add_command(
            label="At Node",
            command=lambda: callback("force", "node")
        )
        self.force_menu.add_command(
            label="At Edge",
            command=lambda: callback("force", "edge")
        )

        self.mode_menu.add_cascade(label="Force", menu=self.force_menu)
        
        # 5. Material
        self.material_menu = tk.Menu(self.mode_menu)
        self.mode_menu.add_command(
            label="Material",
            command=lambda: callback("material", None)
        )
        
        # 6. Utils
        self.utils_menu = tk.Menu(self.mode_menu, tearoff=False)
        self.utils_menu.add_command(
            label="Split Edge",
            command=lambda: callback("utils", "split")
        )
        self.utils_menu.add_command(
            label="Move Node",
            command=lambda: callback("utils", "move")
        )
        self.mode_menu.add_cascade(label="Utilities", menu=self.utils_menu)

        # 7. Mesh mode
        self.mode_menu.add_command(
            label="Mesh",
            command=lambda: callback("mesh", None)
        )

        # 8. results
        self.results_menu = tk.Menu(self.mode_menu, tearoff=False)
        self.results_menu.add_command(label="Nodes", command=lambda: callback("results", "nodes"))
        self.results_menu.add_command(label="Heatmap", command=lambda: callback("results", "heatmap"))
        self.mode_menu.add_cascade(label="Results", menu=self.results_menu)

    def bind_results_scale(self, callback):
        self.scale_slider.config(
            command= lambda _: callback()
        )

    def bind_heatmap_change(self, callback):
        def internal_handler(display_name, internal_metric):
            self.heatmap_metric_var.set(display_name)
            callback(internal_metric)
        
        self.disp_menu.add_command(label="Average", command=lambda: internal_handler("Disp (Avg)", "disp_mag"))
        self.disp_menu.add_command(label="X-Axis", command=lambda: internal_handler("Disp (X)", "dx"))
        self.disp_menu.add_command(label="Y-Axis", command=lambda: internal_handler("Disp (Y)", "dy"))

        self.stress_menu.add_command(label="Von Mises", command=lambda: internal_handler("Stress (VM)", "vm"))
        self.stress_menu.add_command(label="X-Axis", command=lambda: internal_handler("Stress (X)", "sx"))
        self.stress_menu.add_command(label="Y-Axis", command=lambda: internal_handler("Stress (Y)", "sy"))
        self.stress_menu.add_command(label="Shear (XY)", command=lambda: internal_handler("Stress (XY)", "txy"))

    def bind_canvas_click(self, callback):
        """
        Passes the x and y pixel coordinates to the callback.
        """

        def internal_handler(event:tk.Event, side:"str"):
            callback(side, event.x, event.y)

        self.canvas.bind("<Button-1>", lambda e: internal_handler(e, "left"))
        self.canvas.bind("<Button-3>", lambda e: internal_handler(e, "right"))

    def bind_mouse_scroll(self, callback):
        def internal_handler(event, modifier):
            if event.num == 4 or getattr(event, 'delta', 0) > 0:
                direction = 1  # Scrolled UP
            elif event.num == 5 or getattr(event, 'delta', 0) < 0:
                direction = -1 # Scrolled DOWN
            else:
                return
            
            callback(direction, modifier)

        # Windows / macOS bindings
        self.root.master.bind("<MouseWheel>", lambda e: internal_handler(e, "none"))
        self.root.master.bind("<Shift-MouseWheel>", lambda e: internal_handler(e, "shift")) # Fixed double << >>
        self.root.master.bind("<Control-MouseWheel>", lambda e: internal_handler(e, "ctrl"))
        self.root.master.bind("<Control-Shift-MouseWheel>", lambda e: internal_handler(e, "ctrl-shift"))

        # Linux (X11) bindings
        self.root.master.bind("<Button-4>", lambda e: internal_handler(e, "none"))
        self.root.master.bind("<Button-5>", lambda e: internal_handler(e, "none"))
        self.root.master.bind("<Shift-Button-4>", lambda e: internal_handler(e, "shift"))
        self.root.master.bind("<Shift-Button-5>", lambda e: internal_handler(e, "shift"))
        self.root.master.bind("<Control-Button-4>", lambda e: internal_handler(e, "ctrl"))
        self.root.master.bind("<Control-Button-5>", lambda e: internal_handler(e, "ctrl"))
        self.root.master.bind("<Control-Shift-Button-4>", lambda e: internal_handler(e, "ctrl-shift"))
        self.root.master.bind("<Control-Shift-Button-5>", lambda e: internal_handler(e, "ctrl-shift"))
    
    def bind_mouse_move(self, callback): self.canvas.bind("<Motion>", lambda e: callback(e.x, e.y))

    def bind_canvas_update(self, callback): self.canvas.bind("<Configure>", lambda _: callback())

    def bind_enter_press(self, callback): self.root.master.bind("<Return>", lambda _: callback())

    def bind_space_press(self, callback): self.root.master.bind("<space>", lambda _: callback())

    def bind_panning(self, callback):
        def internal_handler(event:tk.Event, kind:str):
            if kind == "start":
                self.canvas.config(cursor="hand2")
            elif kind == "end":
                self.canvas.config(cursor="")
            
            callback(event.x, event.y, kind)


        self.canvas.bind("<ButtonPress-2>", lambda e: internal_handler(e, "start"))
        self.canvas.bind("<B2-Motion>", lambda e: internal_handler(e, "drag"))
        self.canvas.bind("<ButtonRelease-2>", lambda e: internal_handler(e, "end"))

    def bind_key_press(self, callback): 
        def internal_handler(event:tk.Event):
            callback(event.char, event.keysym)
        self.root.master.bind("<Key>", internal_handler)
    
    # ============================
    # UPDATERS AND HELPERS
    # ============================
    def update_boundary_values(self, values:list[str]):
        self.boundary_cb["values"] = values
    
    def update_coord_input(self, cur_buffer:dict, cur_editing:str):
        if all({cur_buffer[key] == "" for key in cur_buffer.keys()}):
            self.log_text_var.set("")
            return
        x, y = cur_buffer["x"], cur_buffer["y"]
        if y == "" and cur_editing == "x": y = "?"
        if cur_editing == "x":
            x = f">{x}<"
        else:
            y = f">{y}<"
        self.update_status_message(f"Nova Coordenada: [{x}, {y}] u", kind="input")

    def clear_misc_from_canvas(self):
        # == mouse coord ==
        self.canvas.delete("coord_lbl")
        self.canvas.delete("hover_info")
        self.canvas.delete("results")
        self.canvas.delete("mesh")

    def update_status_message(self, message: str, kind:str):
        """Displays a message to the user on the UI."""
        self.log_text_var.set(message)

        match kind:
            case "normal":
                self.log_label.config(foreground="white")
            case "warn":
                self.log_label.config(foreground="red")
            case "input":
                self.log_label.config(foreground="lightblue")
    
    def _sync_force_submode(self, submode: str):
        """Swaps force toolbars"""
        self.force_node_frame.pack_forget()
        self.force_edge_frame.pack_forget()

        if submode == "node": self.force_node_frame.pack(side="left")
        if submode == "edge": self.force_edge_frame.pack(side="left")

    def _safe_get_double(self, var: tk.DoubleVar) -> float:
        try:
            return var.get()
        except tk.TclError:
            var.set(0.0)
            return 0.0
        
    def get_node_force_data(self) -> tuple[float, float, float]:
        return (
            self._safe_get_double(self.fx_var),
            self._safe_get_double(self.fy_var),
            self._safe_get_double(self.m_var),
        )
    
    def get_edge_force_data(self) -> tuple[str, float, float, float, float]:
        return (
            self.edge_dir_var.get(),
            self._safe_get_double(self.q_start_var),
            self._safe_get_double(self.q_end_var),
            self._safe_get_double(self.edge_ang_var),
            self._safe_get_double(self.edge_m_var),
        )

    def _support_var_helper(self):
        if not any([
            self.fix_x_var.get(),
            self.fix_y_var.get(),
            self.fix_z_var.get(),
        ]):
            self.fix_x_var.set(True)
            self.update_status_message("At least one support must be active!", "warn")

    def get_support(self) -> str:
        mapper = {
            "x": self.fix_x_var.get(),
            "y": self.fix_y_var.get(),
            "z": self.fix_z_var.get(),
        }

        r = ""

        for i, bool_ in mapper.items():
            if bool_: r += i

        return r
        
    def get_force(self) -> tuple[bool, float, float, float]:
        
        is_pressure = self.is_pressure_var.get()

        for var in [
            self.fx_double_var,
            self.fy_double_var,
            self.m_double_var
        ]:
            try:
                var.get()
            except tk.TclError:
                var.set(0.0)

        if is_pressure:
            return (
                is_pressure,
                self.fx_double_var.get(),
                0.0,
                0.0,
            )
        return (
            is_pressure,
            self.fx_double_var.get(),
            self.fy_double_var.get(),
            self.m_double_var.get(),
        )
    
    # ============================
    # DIALOG
    # ============================

    def ask_for_segments(self) -> int | None:
        """
        Pops up a modal dialog asking the user for the number of segments.
        Returns the integer, or None if the user clicks 'Cancel'.
        """
        num_segments = simpledialog.askinteger(
            title="Split Edge",
            prompt="Enter the number of segments:",
            parent=self.canvas.winfo_toplevel(),  
            minvalue=2,        # Must be at least 2 segments to actually split it!
            maxvalue=100       # Safety limit
        )
        
        return num_segments
    
    # ============================
    # PENCILS
    # ============================

    def draw_axis(self, topleft_unts: tuple[float, float], botright_unts: tuple[float, float], offset_pxls: tuple[float, float], axis_line_width: int = 2):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        cx = w / 2
        cy = h / 2
                
        offset_x, offset_y = offset_pxls
        
        # Calculate the pixel locations of the mathematical origin (0,0)
        origin_x_px = cx - offset_x
        origin_y_px = cy - offset_y
                    
        self.canvas.delete("axis")
        
        # Unpack the engineering units at the screen edges
        x_min, y_max = topleft_unts
        x_max, y_min = botright_unts
        
        # ---------------------------------------------------------
        #  X-AXIS (Horizontal Line)
        # ---------------------------------------------------------
        # It is visible if its Y pixel position is between 0 and the canvas height
        if 0 <= origin_y_px <= h:
            self.canvas.create_line(
                0, origin_y_px,
                w, origin_y_px,
                fill="gray", tags="axis", width=axis_line_width
            )
            
            # Left edge text (anchor Northwest to push it right and down)
            self.write_coordinate(
                value=(round(x_min, 2), 0),
                at=(0, origin_y_px),
                text_offset=(5, -5), # Negative Y offset pushes it DOWN (yc - (-5) = yc + 5)
                anchor="nw",
                tags="axis"
            )
            
            # Right edge text (anchor Northeast to push it left and down)
            self.write_coordinate(
                value=(round(x_max, 2), 0),
                at=(w, origin_y_px),
                text_offset=(-5, -5),
                anchor="ne",
                tags="axis"
            )

        # ---------------------------------------------------------
        #  Y-AXIS (Vertical Line)
        # ---------------------------------------------------------
        # It is visible if its X pixel position is between 0 and the canvas width
        if 0 <= origin_x_px <= w:
            self.canvas.create_line(
                origin_x_px, 0,
                origin_x_px, h,
                fill="gray", tags="axis", width=axis_line_width
            )
            
            # Top edge text (anchor Northwest to push it right and down)
            self.write_coordinate(
                value=(0, round(y_max, 2)),
                at=(origin_x_px, 0),
                text_offset=(5, -5),
                anchor="nw",
                tags="axis"
            )
            
            # Bottom edge text (anchor Southwest to push it right and up)
            self.write_coordinate(
                value=(0, round(y_min, 2)),
                at=(origin_x_px, h),
                text_offset=(5, 5), # Positive Y offset pushes it UP
                anchor="sw",
                tags="axis"
            )

        self.canvas.tag_lower("axis")

    def draw_grid(self, offset_pxls: tuple[float, float], zoom: float, precision: int | float):
        self.canvas.delete("grid")

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        
        # Prevent division by zero errors during initialization
        if cw <= 1 or ch <= 1 or zoom <= 0: 
            return
        
        # Calculate grid spacing in pixels
        # If precision is 0, spacing is 1 unit. If -1, spacing is 10 units, etc.
        spacing_units = 10**precision
        spacing_pxls = spacing_units * zoom

        MIN_SPACING_PXLS = 10

        # If the grid lines get squished too tightly together, 
        # bump the visual spacing to the next factor of 10.
        while spacing_pxls < MIN_SPACING_PXLS:
            spacing_units *= 10
            spacing_pxls = spacing_units * zoom
    
        
        # Calculate origin point in pixels
        origin_x = (cw / 2) - offset_pxls[0]
        origin_y = (ch / 2) - offset_pxls[1]

        #  VIEWPORT CULLING: Only calculate lines that fall inside the screen bounds
        # We find the integer "index" of the grid line just off-screen to the left/top
        # and iterate until the index just off-screen to the right/bottom.
        
        start_i_x = int(-origin_x / spacing_pxls) - 1
        end_i_x   = int((cw - origin_x) / spacing_pxls) + 1
        
        start_i_y = int(-origin_y / spacing_pxls) - 1
        end_i_y   = int((ch - origin_y) / spacing_pxls) + 1

        # Draw vertical lines (X-axis)
        for i in range(start_i_x, end_i_x + 1):
            x = origin_x + (i * spacing_pxls)
            self.canvas.create_line(x, 0, x, ch, fill="#303030", tags="grid")

        # Draw horizontal lines (Y-axis)
        for i in range(start_i_y, end_i_y + 1):
            y = origin_y + (i * spacing_pxls)
            self.canvas.create_line(0, y, cw, y, fill="#303030", tags="grid")

        self.canvas.tag_lower("grid") # Ensure grid stays behind nodes/edges

    def draw_watermark(self):
        self.canvas.delete("watermark")
        
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()

        padding = 10

        self.canvas.create_image(
            cw - padding,
            ch - padding, 
            image=self.watermark,
            anchor="se",
            tags="watermark"
        )

        self.canvas.tag_raise("watermark")

    def draw_nodes(self, points:Dict[int, tuple[float, float]], active_node_ids:List[int], r:float=4.0):
        # delete previously drawn points
        self.canvas.delete("point")

        for id, (xc, yc) in points.items():
            self.canvas.create_oval(
                xc - r, yc - r,
                xc + r, yc + r,
                fill="cyan" if id not in active_node_ids else "red",
                outline="",
                tags="point"
            )

    def draw_edges(self, lines: dict, curves: dict, preview_line: list[float], preview_curve: list[tuple]):
        LIGHTRED = "#e25252"
        BLUEISH = "#357ffd"
        self.canvas.delete("edge")
        
        # Draw straight edges
        for boundary, line_list in lines.items():
            # Determine color based on boundary group name
            color = BLUEISH if boundary == "external" else LIGHTRED
            
            # Draw every line inside this specific boundary group
            for x1, y1, x2, y2 in line_list:
                self.canvas.create_line(
                    x1, y1, x2, y2, 
                    fill=color, width=2, tags="edge"
                )

        if preview_line:
            self.canvas.create_line(
                *preview_line,
                fill="lightgray", width=2, tags="edge",
                dash=(4,4)
            )
            
        # Draw curved edges
        for boundary, curve_list in curves.items():
            color = BLUEISH if boundary == "external" else LIGHTRED
            
            # Draw every curve inside this specific boundary group
            for curve_points in curve_list:
                flat_coords = [coord for point in curve_points for coord in point]
                
                self.canvas.create_line(
                    *flat_coords, 
                    fill=color, width=2, smooth=False, tags="edge"
                )

        if preview_curve:
            flat_coords = [coord for point in preview_curve for coord in point]
            self.canvas.create_line(
               *flat_coords,
               fill="lightgray", width=2, smooth=False, tags="edge",
               dash=(4,4)
            )

    def draw_mesh(self, nodes_pxl: list[tuple[float, float]], triangles:list[tuple[int, int,int]]):
        """Draws the generated FEM mesh triangles."""
        self.canvas.delete("mesh")
        
        for n1, n2, n3 in triangles:
            # Grab the pixel coordinates for the 3 corners of the triangle
            x1, y1 = nodes_pxl[n1]
            x2, y2 = nodes_pxl[n2]
            x3, y3 = nodes_pxl[n3]

            self.canvas.create_polygon(
                x1, y1, x2, y2, x3, y3,
                outline="#555555",  # A nice dark gray wireframe
                fill="",            # Transparent inside
                width=1,
                tags="mesh"
            )

        # Push the mesh to the back so it doesn't cover your main drawing lines!
        self.canvas.tag_lower("mesh")
        self.canvas.tag_lower("grid") 

    def draw_hover_box(self, xc: float, yc: float, text: str):
        """Draws a floating tooltip box near the cursor with dynamic information."""
        self.canvas.delete("hover_info")
        
        # Draw the text first (offset slightly from the cursor)
        text_id = self.canvas.create_text(
            xc + 15, yc + 15,  
            text=text,
            anchor="nw",
            fill="white",
            font=("Consolas", 10),
            tags="hover_info"
        )
        
        # Get the bounding box of the generated text
        bbox = self.canvas.bbox(text_id)
        if bbox:
            pad = 6
            x1, y1, x2, y2 = bbox
            
            # Draw a dark background rectangle slightly larger than the text
            self.canvas.create_rectangle(
                x1 - pad, y1 - pad, x2 + pad, y2 + pad,
                fill="#222222",
                outline="#00ff0d", 
                width=1,
                tags="hover_info_bg"
            )
            
            # Push the background behind the text, and group them together
            self.canvas.tag_lower("hover_info_bg", text_id)
            self.canvas.addtag_withtag("hover_info", "hover_info_bg")
            
            # Ensure it always renders on top of the mesh/results
            self.canvas.tag_raise("hover_info")
        
    def _draw_support_helper(self, support:str, at:Tuple[float, float], size:float = 15, fill:str = "#00ff0d", tags:str = "support"):
        """
        Draws a figure to represent a support
            support: str that contains at least one of x, y, z e.g. "xy", "xz"
            at: canvas coordinates, in pixels
            size [Optional]: defines size of drawing, in pixels
            fill [Optional]: color
            tags [Optional]: drawing's tag, for deleting when canvas updates
        """

        x0, y0 = at
        c = self.canvas
        # distance to point
        a = 0.577 * size # tan 30° * size
        # X constraint: triangle pointing right
        if "x" in support.lower():
            c.create_polygon(
                x0       , y0,
                x0 + size, y0 - a,
                x0 + size, y0 + a,
                fill=fill,
                outline=fill,
                tags=tags,
            )

        # Y constraint: triangle pointing down
        if "y" in support.lower():
            c.create_polygon(
                x0, y0,
                x0 + a, y0 + size,
                x0 - a, y0 + size,
                fill=fill,
                outline=fill,
                tags=tags,
            )

        # Z constraint: hollow circle around node
        if "z" in support.lower():
            a = size / 2
            c.create_rectangle(
                x0 - a,
                y0 - a,
                x0 + a,
                y0 + a,
                outline=fill,
                width=2,
                fill="",
                tags=tags,
            )

    def draw_supports(self, support_data: list[tuple[str, tuple[float, float]]]):
        """
        Draws all active supports on the canvas.
        support_data: A list of tuples formatted as (support_string, (pixel_x, pixel_y))
        """
        # Clear previous frame's supports
        self.canvas.delete("support")
        
        # Draw the new ones
        for support_type, pixel_coords in support_data:
            self._draw_support_helper(
                support=support_type,
                at=pixel_coords,
                size=12,            
                fill="#00ff0d",     # Toxic green just like me
                tags="support"
            )
            
        self.canvas.tag_raise("support")
   
    def _draw_force_helper(self, at: tuple[float, float], magnitude: float, moment:float , angle: float = 0.0, size: float = 30, fill: str = "#ff0000", tags: str = "force"):
        """
        Draws an arrow to represent a force.
            at: canvas coordinates (x, y) where the arrow TIP will touch, in pixels.
            magnitude: value of the force (negative flips the arrow 180°).
            angle: angle in degrees (0 = pointing right, 90 = pointing up).
            size [Optional]: length of the arrow in pixels.
            fill [Optional]: color (red is standard for forces).
            tags [Optional]: drawing's tag, for deleting when canvas updates.
        """
        x0, y0 = at
        c = self.canvas


        if magnitude != 0:
            
            draw_angle = angle
            if magnitude < 0:
                draw_angle += 180
                
            rad = draw_angle * 3.14159 / 180
            
            
            dx = size * cos(rad)
            dy = size * sin(rad)
            
            x_tail = x0 - dx
            y_tail = y0 + dy
            
            h1 = size * 0.3
            h2 = size * 0.4
            h3 = size * 0.15

            # Draw the arrow
            c.create_line(
            x_tail, y_tail,  # Start (tail)
            x0, y0,          # End (tip)
            fill=fill,
            width=2,
            arrow="last",    # Forces the arrowhead to render at (x0, y0)
            arrowshape=(h1, h2, h3),
            tags=tags
        )

        if moment != 0:
            # 240-degree sweep
            r = size * 0.6  # Radius slightly larger than the linear arrow
            steps = 15      # Number of segments for a smooth curve
            points = []

            # Math convention: bottom-right (-30 deg) over the top to bottom-left (210 deg)
            start_ang = -30
            end_ang = 210

            for i in range(steps + 1):
                t = i / steps
                
                # Determine direction based on moment sign
                if moment > 0: # Counter-Clockwise
                    ang = start_ang + t * (end_ang - start_ang)
                else:          # Clockwise
                    ang = end_ang - t * (end_ang - start_ang)

                m_rad = ang * 3.14159 / 180

                # Note: Tkinter Y is inverted (+ is down), so we subtract the Y 
                # component to make standard CCW/CW math visually correct on screen.
                mx = x0 + r * cos(m_rad)
                my = y0 - r * sin(m_rad)

                # Tkinter expects a flat list of coordinates: [x1, y1, x2, y2...]
                points.extend([mx, my])

            # Draw the curve using a connected line sequence with an arrow at the end.
            # We use a slightly smaller arrowhead so it follows the curve gracefully!
            c.create_line(
                *points,
                fill=fill,
                width=2,
                arrow="last",
                arrowshape=(size * 0.2, size * 0.25, size * 0.1),
                tags=tags
            )

    def draw_forces(self, force_data: list[tuple[tuple[float, float, float], tuple[float, float]]]):
        
        self.canvas.delete("force")

        for (magnitude, angle, moment), pixel_coords, size_pxls in force_data:
            self._draw_force_helper(
                at=pixel_coords,
                magnitude=magnitude,
                moment=moment,
                angle=angle,
                size=size_pxls,
                fill="#e5ff00",
                tags="force"
            )

        self.canvas.tag_raise("force")

    def draw_results(self, polygons_to_draw: list[tuple[tuple[float, ...], str, str]]):
        """
        Draws the pre-calculated results polygons.
        polygons_to_draw format: [((x1, y1, x2, y2, x3, y3), outline_hex, fill_hex), ...]
        """
        self.canvas.delete("results")
        self.canvas.delete("mesh") # Hide standard mesh

        for coords, outline_color, fill_color in polygons_to_draw:
            self.canvas.create_polygon(
                *coords,
                outline=outline_color, 
                fill=fill_color, 
                width=1, 
                tags="results"
            )
        
        self.canvas.tag_lower("results")
        self.canvas.tag_lower("grid")

    def write_coordinate(
            self,
            value:Tuple[float, float], 
            at:Tuple[float, float], 
            text_offset:Tuple[float, float] = (16, 16), 
            fill:str="lightgray", font=("Consolas", 10), 
            anchor:Literal['nw', 'n', 'ne', 'w', 'center', 'e', 'sw', 's', 'se']="w",
            tags:str | list[str] | tuple[str, ...] = ""
        ):
        x, y = value
        xc, yc = at
        offx, offy = text_offset
        
        self.canvas.create_text(
            xc + offx, yc - offy,
            text=f"[{x}, {y}] u",
            fill=fill,
            anchor=anchor,
            font=font,
            tags=tags,
        )   

    def draw_near_mouse(self, mouse_coords_unt:Tuple[float, float], mouse_coords_pxl:Tuple[float, float]):
        # Clean up previous text
        self.canvas.delete("coord_lbl")

        # draw actual text
        self.write_coordinate(
            mouse_coords_unt,
            mouse_coords_pxl,
            tags="coord_lbl"
        )


    # ============================
    # INITIALIZATION
    # ============================
    def start(self): self.root.run()