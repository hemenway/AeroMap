import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os

# --- DISABLE SAFETY LIMITS ---
Image.MAX_IMAGE_PIXELS = None
# -----------------------------

class GeorefApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Rapid GCP Logger (v5: LCC + Preproject/TPS/Order/Reproject)")
        self.root.geometry("1600x980")

        # --- State Variables ---
        self.image_files = []
        self.current_index = 0
        self.clicks = []
        self.click_ids = []
        self.scale_factor = 1.0
        self.current_image_path = None
        self.original_img = None
        
        # Magnifier State
        self.zoom_level = 4
        self.loupe_size = 150
        self.loupe_locked = False
        self.locked_coords = (0, 0)
        
        # --- UI Layout ---
        control_frame = tk.Frame(root, height=210, bg="#f0f0f0")
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        btn_load = tk.Button(control_frame, text="1. Load Folder", command=self.load_folder, height=3, bg="#e1e1e1")
        btn_load.pack(side=tk.LEFT, padx=10)

        # ----------------- Coordinate Inputs -----------------
        self.coord_frame = tk.Frame(control_frame)
        self.coord_frame.pack(side=tk.LEFT, padx=20, pady=5)
        
        tk.Label(self.coord_frame, text="Target Graticule (Lon / Lat)", font=("Arial", 10, "bold")).grid(row=0, columnspan=7, sticky="w")
        
        self.entries = []
        point_labels = [
            "1. Top-Left",  "2. Top-Mid",  "3. Top-Right",
            "4. Bot-Left",  "5. Bot-Mid",  "6. Bot-Right"
        ]
        defaults = [
            ("-102.0", "34.0"), ("-99.0", "34.0"), ("-96.0", "34.0"),  # Top
            ("-102.0", "32.0"), ("-99.0", "32.0"), ("-96.0", "32.0")   # Bottom
        ]

        for i in range(6):
            r = 1 if i < 3 else 2
            c_block = (i % 3) * 3
            tk.Label(self.coord_frame, text=f"{point_labels[i]}:").grid(row=r, column=c_block, padx=(10,2), sticky="e")
            e_x = tk.Entry(self.coord_frame, width=10)
            e_y = tk.Entry(self.coord_frame, width=10)
            e_x.grid(row=r, column=c_block+1)
            e_y.grid(row=r, column=c_block+2)
            if i < len(defaults):
                e_x.insert(0, defaults[i][0])
                e_y.insert(0, defaults[i][1])
            self.entries.append((e_x, e_y))

        # ----------------- Projection Settings -----------------
        proj_frame = tk.Frame(control_frame, bg="#f7f7f7", padx=10, pady=10, bd=1, relief=tk.GROOVE)
        proj_frame.pack(side=tk.LEFT, padx=12, pady=5)

        tk.Label(proj_frame, text="Map Projection (Lambert Conformal Conic)", font=("Arial", 10, "bold"), bg="#f7f7f7").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0,6))

        tk.Label(proj_frame, text="lat_1").grid(row=1, column=0, sticky="e"); self.lat1 = tk.Entry(proj_frame, width=9); self.lat1.grid(row=1, column=1); self.lat1.insert(0, "33")
        tk.Label(proj_frame, text="lat_2").grid(row=1, column=2, sticky="e"); self.lat2 = tk.Entry(proj_frame, width=9); self.lat2.grid(row=1, column=3); self.lat2.insert(0, "45")
        tk.Label(proj_frame, text="lat_0").grid(row=1, column=4, sticky="e"); self.lat0 = tk.Entry(proj_frame, width=9); self.lat0.grid(row=1, column=5); self.lat0.insert(0, "33")

        tk.Label(proj_frame, text="lon_0").grid(row=2, column=0, sticky="e"); self.lon0 = tk.Entry(proj_frame, width=9); self.lon0.grid(row=2, column=1); self.lon0.insert(0, "-96")
        tk.Label(proj_frame, text="x_0").grid(row=2, column=2, sticky="e");  self.x0   = tk.Entry(proj_frame, width=9); self.x0.grid(row=2, column=3); self.x0.insert(0, "0")
        tk.Label(proj_frame, text="y_0").grid(row=2, column=4, sticky="e");  self.y0   = tk.Entry(proj_frame, width=9); self.y0.grid(row=2, column=5); self.y0.insert(0, "0")

        tk.Label(proj_frame, text="Datum for graticule:").grid(row=3, column=0, sticky="e", pady=(6,0))
        self.datum_var = tk.StringVar(value="EPSG:4269")  # NAD83 default
        datum_menu = tk.OptionMenu(proj_frame, self.datum_var, "EPSG:4326 (WGS84)", "EPSG:4269 (NAD83)", "EPSG:4267 (NAD27)")
        datum_menu.grid(row=3, column=1, columnspan=2, sticky="w", pady=(6,0))

        self.preproject_var = tk.IntVar(value=1)
        tk.Checkbutton(proj_frame, text="Preproject GCPs to LCC (recommended)", variable=self.preproject_var, bg="#f7f7f7").grid(row=3, column=3, columnspan=3, sticky="w", pady=(6,0))

        # Warp / Reproject options
        tk.Label(proj_frame, text="Warp model:").grid(row=4, column=0, sticky="e", pady=(6,0))
        self.warp_model = tk.StringVar(value="order2")
        tk.OptionMenu(proj_frame, self.warp_model, "order1", "order2", "order3", "tps").grid(row=4, column=1, sticky="w", pady=(6,0))

        tk.Label(proj_frame, text="Resampling:").grid(row=4, column=2, sticky="e", pady=(6,0))
        self.resample = tk.StringVar(value="cubic")
        tk.OptionMenu(proj_frame, self.resample, "near", "bilinear", "cubic", "lanczos").grid(row=4, column=3, sticky="w", pady=(6,0))

        tk.Label(proj_frame, text="Refine GCPs tol,min:").grid(row=4, column=4, sticky="e", pady=(6,0))
        self.refine_tol = tk.Entry(proj_frame, width=6); self.refine_tol.grid(row=4, column=5, sticky="w", pady=(6,0)); self.refine_tol.insert(0, "")  # blank=off
        self.refine_min = tk.Entry(proj_frame, width=4); self.refine_min.grid(row=4, column=5, sticky="e", pady=(6,0)); self.refine_min.insert(0, "")

        tk.Label(proj_frame, text="Final target EPSG (optional):").grid(row=5, column=0, sticky="e", pady=(6,0))
        self.target_epsg = tk.Entry(proj_frame, width=12); self.target_epsg.grid(row=5, column=1, sticky="w", pady=(6,0)); self.target_epsg.insert(0, "")  # e.g., 3857

        # ----------------- Info -----------------
        info_frame = tk.Frame(control_frame)
        info_frame.pack(side=tk.RIGHT, padx=20)
        self.status_label = tk.Label(info_frame, text="Load a folder to start.", fg="blue", font=("Arial", 16, "bold"))
        self.status_label.pack()
        instructions = "L-Click: Record | R-Click: Undo\nShift: Lock Loupe | Arrows: Nudge"
        tk.Label(info_frame, text=instructions, fg="gray").pack()

        # ----------------- Canvas -----------------
        self.canvas_frame = tk.Frame(root, bg="gray")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.canvas_frame, bg="#333", cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bindings
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Button-3>", self.undo_click) # Windows/Linux
        self.canvas.bind("<Button-2>", self.undo_click) # Mac
        
        self.canvas.bind("<Motion>", self.update_loupe)
        self.canvas.bind("<Leave>", self.hide_loupe)
        
        self.root.bind("<Shift_L>", self.enable_lock)
        self.root.bind("<Shift_R>", self.enable_lock)
        self.root.bind("<KeyRelease-Shift_L>", self.disable_lock)
        self.root.bind("<KeyRelease-Shift_R>", self.disable_lock)
        self.root.bind("<Left>", lambda e: self.nudge_cursor(-1, 0))
        self.root.bind("<Right>", lambda e: self.nudge_cursor(1, 0))
        self.root.bind("<Up>", lambda e: self.nudge_cursor(0, -1))
        self.root.bind("<Down>", lambda e: self.nudge_cursor(0, 1))

        self.loupe_items = {}
        self.tk_loupe_img = None

    # ----------------- File & Image Handling -----------------
    def load_folder(self):
        folder_selected = filedialog.askdirectory()
        if not folder_selected: return
        
        self.image_files = [
            os.path.join(folder_selected, f)
            for f in os.listdir(folder_selected)
            if f.lower().endswith(('.tif', '.tiff'))
        ]
        self.image_files.sort()
        
        if not self.image_files:
            messagebox.showerror("Error", "No TIF files found.")
            return
            
        self.output_script = os.path.join(folder_selected, "run_georeference.sh")
        if not os.path.exists(self.output_script):
            with open(self.output_script, "w") as f:
                f.write("#!/bin/bash\nset -euo pipefail\nmkdir -p georeferenced\n\n")

        self.current_index = 0
        self.load_image()

    def load_image(self):
        if self.current_index >= len(self.image_files):
            self.status_label.config(text="All Done! Script generated.")
            self.canvas.delete("all")
            return

        self.clicks = []
        self.click_ids = []
        self.current_image_path = self.image_files[self.current_index]
        self.update_status()

        self.original_img = Image.open(self.current_image_path)
        self.orig_w, self.orig_h = self.original_img.size
        
        self.root.update()
        canvas_w = max(self.canvas.winfo_width(), 1000)
        canvas_h = max(self.canvas.winfo_height(), 800)
        
        ratio = min(canvas_w/self.orig_w, canvas_h/self.orig_h)
        self.scale_factor = ratio
        
        new_w = int(self.orig_w * ratio)
        new_h = int(self.orig_h * ratio)
        
        resized_img = self.original_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(resized_img)
        
        self.canvas.delete("all")
        self.loupe_items = {}
        
        self.x_offset = (canvas_w - new_w) // 2
        self.y_offset = (canvas_h - new_h) // 2
        
        self.canvas.create_image(self.x_offset, self.y_offset, anchor=tk.NW, image=self.tk_img, tags="main_img")

    # ----------------- Loupe / Cursor -----------------
    def nudge_cursor(self, dx, dy):
        try:
            x = self.root.winfo_pointerx() + dx
            y = self.root.winfo_pointery() + dy
            self.root.event_generate('<Motion>', warp=True, x=x, y=y)
        except:
            pass

    def enable_lock(self, event):
        if not self.loupe_locked and 'img' in self.loupe_items:
            coords = self.canvas.coords(self.loupe_items['img'])
            if coords:
                self.locked_coords = (coords[0], coords[1])
                self.loupe_locked = True
                
    def disable_lock(self, event):
        self.loupe_locked = False

    def update_loupe(self, event):
        if not self.original_img: return
        raw_x = (event.x - self.x_offset) / self.scale_factor
        raw_y = (event.y - self.y_offset) / self.scale_factor
        
        if raw_x < 0 or raw_y < 0 or raw_x > self.orig_w or raw_y > self.orig_h:
            self.hide_loupe(event); return

        src_r = (self.loupe_size / 2) / self.zoom_level
        left = max(0, raw_x - src_r); top = max(0, raw_y - src_r)
        right = min(self.orig_w, raw_x + src_r); bottom = min(self.orig_h, raw_y + src_r)
        
        try:
            crop = self.original_img.crop((left, top, right, bottom))
            zoom_img = crop.resize((self.loupe_size, self.loupe_size), Image.Resampling.NEAREST)
            self.tk_loupe_img = ImageTk.PhotoImage(zoom_img)
            if self.loupe_locked:
                lx, ly = self.locked_coords
            else:
                lx = event.x + 20; ly = event.y + 20
                if lx + self.loupe_size > self.canvas.winfo_width():
                    lx = event.x - self.loupe_size - 20
                if ly + self.loupe_size > self.canvas.winfo_height():
                    ly = event.y - self.loupe_size - 20

            if 'img' not in self.loupe_items:
                self.loupe_items['img'] = self.canvas.create_image(lx, ly, anchor=tk.NW, image=self.tk_loupe_img)
                self.loupe_items['border'] = self.canvas.create_rectangle(lx, ly, lx+self.loupe_size, ly+self.loupe_size, outline="yellow", width=2)
                cx = lx + self.loupe_size/2; cy = ly + self.loupe_size/2
                self.loupe_items['v_line'] = self.canvas.create_line(cx, ly, cx, ly+self.loupe_size, fill="red")
                self.loupe_items['h_line'] = self.canvas.create_line(lx, cy, lx+self.loupe_size, cy, fill="red")
            else:
                self.canvas.itemconfig(self.loupe_items['img'], image=self.tk_loupe_img)
                self.canvas.coords(self.loupe_items['img'], lx, ly)
                self.canvas.coords(self.loupe_items['border'], lx, ly, lx+self.loupe_size, ly+self.loupe_size)
                cx = lx + self.loupe_size/2; cy = ly + self.loupe_size/2
                self.canvas.coords(self.loupe_items['v_line'], cx, ly, cx, ly+self.loupe_size)
                self.canvas.coords(self.loupe_items['h_line'], lx, cy, lx+self.loupe_size, cy)
                for key in self.loupe_items:
                    self.canvas.tag_raise(self.loupe_items[key])
        except Exception as e:
            print(f"Zoom error: {e}")

    def hide_loupe(self, event):
        if 'img' in self.loupe_items:
            for key in self.loupe_items:
                self.canvas.delete(self.loupe_items[key])
            self.loupe_items = {}

    # ----------------- Click / Status -----------------
    def on_click(self, event):
        if not self.current_image_path: return
        click_x = (event.x - self.x_offset) / self.scale_factor
        click_y = (event.y - self.y_offset) / self.scale_factor
        if click_x < 0 or click_y < 0 or click_x > self.orig_w or click_y > self.orig_h: return

        self.clicks.append((click_x, click_y))
        r = 5
        dot_id = self.canvas.create_oval(event.x-r, event.y-r, event.x+r, event.y+r, fill="red", outline="yellow")
        self.click_ids.append(dot_id)
        self.update_status()
        self.update_loupe(event)
        if len(self.clicks) == 6:
            self.save_and_next()

    def undo_click(self, event):
        if not self.clicks: return
        self.clicks.pop()
        if self.click_ids:
            last_id = self.click_ids.pop()
            self.canvas.delete(last_id)
        self.update_status()

    def update_status(self):
        count = len(self.clicks)
        filename = os.path.basename(self.current_image_path)
        labels = [
            "1. Top-Left", "2. Top-Mid", "3. Top-Right",
            "4. Bot-Left", "5. Bot-Mid", "6. Bot-Right",
            "Done"
        ]
        if count < 6:
            next_pt = labels[count]
            self.status_label.config(text=f"{filename}\nClick: {next_pt}")
        else:
            self.status_label.config(text="Processing...")

    # ----------------- Script Generation -----------------
    def _datum_epsg_from_menu(self):
        val = self.datum_var.get()
        if "4326" in val: return "EPSG:4326"
        if "4267" in val: return "EPSG:4267"
        return "EPSG:4269"

    def _lcc_proj_string(self):
        lat1 = self.lat1.get().strip()
        lat2 = self.lat2.get().strip()
        lat0 = self.lat0.get().strip()
        lon0 = self.lon0.get().strip()
        x0   = self.x0.get().strip() or "0"
        y0   = self.y0.get().strip() or "0"
        # NAD83 is a sensible default; user can still warp to another target later.
        # Using +datum instead of explicit +ellps keeps it simple for script users.
        return f"+proj=lcc +lat_1={lat1} +lat_2={lat2} +lat_0={lat0} +lon_0={lon0} +x_0={x0} +y_0={y0} +datum=NAD83 +units=m +no_defs"

    def _warp_flags(self):
        method = self.warp_model.get()
        resamp = self.resample.get()
        flags = f"-r {resamp}"
        if method == "tps":
            flags += " -tps"
        elif method == "order1":
            flags += " -order 1"
        elif method == "order3":
            flags += " -order 3"
        else:
            flags += " -order 2"
        tol = self.refine_tol.get().strip()
        min_gcps = self.refine_min.get().strip()
        if tol and min_gcps:
            flags += f" -refine_gcps {tol} {min_gcps}"
        return flags

    def save_and_next(self):
        # Collect 6 entered geog coords (lon,lat) paired to 6 clicks (pixel,line)
        geo_coords = []
        for ex, ey in self.entries:
            geo_coords.append((ex.get().strip(), ey.get().strip()))

        # Build strings
        lcc_proj = self._lcc_proj_string()
        gcp_srs_geog = self._datum_epsg_from_menu()
        preproject = bool(self.preproject_var.get())
        warp_flags = self._warp_flags()
        target = self.target_epsg.get().strip()

        filename = os.path.basename(self.current_image_path)
        safe_name = filename.replace('"', '\\"')  # minimal safety for quotes

        # Prepare GCP lines (bash will compute projected x/y if preprojecting)
        # We'll create variables X1 Y1 ... X6 Y6 when preprojecting; otherwise use lon/lat directly.
        lines = []
        lines.append(f"echo 'Processing {safe_name}...'")
        lines.append(f"src='{safe_name}'")
        lines.append(f"tmp='georeferenced/temp_{safe_name}'")
        lines.append(f"lcc='georeferenced/lcc_{safe_name}'")

        # Write the LCC PROJ string into a shell var (careful with quotes)
        lines.append(f"LCC_PROJ=\"{lcc_proj}\"")
        lines.append(f"GEO_SRS=\"{gcp_srs_geog}\"")
        lines.append("")

        # Preproject GCPs with gdaltransform (recommended)
        gcp_vars = []
        for i in range(6):
            lon = geo_coords[i][0]
            lat = geo_coords[i][1]
            if preproject:
                # project lon/lat -> X Y in LCC
                lines.append(f"read X{i+1} Y{i+1} _ <<< $(echo \"{lon} {lat}\" | gdaltransform -s_srs \"$GEO_SRS\" -t_srs \"$LCC_PROJ\")")
                gcp_vars.append((f"${{X{i+1}}}", f"${{Y{i+1}}}"))
            else:
                # keep as lon/lat; GCP CRS stays geographic
                gcp_vars.append((lon, lat))

        # Build -gcp args paired with pixel/line
        gcp_string_parts = []
        for i in range(6):
            pix_x = f"{self.clicks[i][0]:.3f}"
            pix_y = f"{self.clicks[i][1]:.3f}"
            gx, gy = gcp_vars[i]
            gcp_string_parts.append(f"-gcp {pix_x} {pix_y} {gx} {gy}")
        gcp_string = " ".join(gcp_string_parts)

        # gdal_translate with correct GCP CRS
        if preproject:
            # GCPs are in LCC, so declare that SRS on the GCPs
            cmd_translate = f"gdal_translate -of GTiff -a_srs \"$LCC_PROJ\" {gcp_string} \"$src\" \"$tmp\""
        else:
            # GCPs are in geographic datum SRS
            cmd_translate = f"gdal_translate -of GTiff -a_srs \"$GEO_SRS\" {gcp_string} \"$src\" \"$tmp\""
        lines.append(cmd_translate)

        # gdalwarp #1: rectify
        if preproject:
            # Already in LCC GCP space → rectify into LCC (no -t_srs): output lcc_
            cmd_warp1 = f"gdalwarp {warp_flags} -dstnodata 0 -overwrite \"$tmp\" \"$lcc\""
        else:
            # GCPs in geographic → warp into LCC
            cmd_warp1 = f"gdalwarp {warp_flags} -t_srs \"$LCC_PROJ\" -dstnodata 0 -overwrite \"$tmp\" \"$lcc\""
        lines.append(cmd_warp1)
        lines.append("rm \"$tmp\"")

        # Optional reprojection to final target CRS
        if target:
            out_final = f"georeferenced/{safe_name}"
            cmd_warp2 = f"gdalwarp -r {self.resample.get()} -t_srs EPSG:{target} -dstnodata 0 -overwrite \"$lcc\" \"{out_final}\""
            lines.append(cmd_warp2)
            lines.append("rm \"$lcc\"")
        else:
            # Keep LCC as final (rename)
            out_final = f"georeferenced/{safe_name}"
            lines.append(f"mv \"$lcc\" \"{out_final}\"")

        lines.append("")  # blank line between items

        with open(self.output_script, "a") as f:
            f.write("\n".join(lines))

        print(f"Logged {filename}")
        self.current_index += 1
        self.load_image()

if __name__ == "__main__":
    root = tk.Tk()
    app = GeorefApp(root)
    root.mainloop()
