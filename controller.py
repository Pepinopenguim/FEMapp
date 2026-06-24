from typing import Tuple
from view import MainView
from model import FEMModel, Edge
from math import hypot, degrees, atan2
import numpy as np
from mesh import MeshEngine
from curve import CurveHelper

class MainController:

    # ============================================
    # INITIALIZATION AND SETUP
    # ============================================
    def __init__(self, model:FEMModel, view:MainView):

        self.model = model
        self.view = view

        # define app states
        self.mode = "node"
        self.sub_mode = "linear"

        self.precision = 0
        
        # defines canvas zoom, 
        self.zoom = 50 # pxl/unt
        
        self.canvas_offset_xc = self.view.canvas.winfo_width() / 2
        self.canvas_offset_yc = self.view.canvas.winfo_height() / 2

        self.pan_offset_x , self.pan_offset_y = 0, 0

        self.active_points = []
        self.active_node_ids: list[int] = []

        self.preview_line = []
        self.preview_curve = []

        self.active_boundary = "external"

        self.cur_editing_coord = "x"
        self.coord_buffer = {
            "x":str(),
            "y":str(),
        }

        self._bind_view_events()

        self.math = CurveHelper


        # log of initialization
        self.log("Ready. Click anywhere to place a node.")

    def _bind_view_events(self):
        # canvas bindings
        self.view.bind_canvas_click(self.on_click_canvas)
        self.view.bind_canvas_update(self.on_canvas_update)

        # mouse bindings
        self.view.bind_mouse_scroll(self.on_mouse_scroll)
        self.view.bind_mouse_move(self.on_mouse_move)

        # app bindings
        self.view.bind_key_press(self.on_key_press)
        self.view.bind_enter_press(self.on_enter_press)
        self.view.bind_space_press(self.zoom_extents)

        # Pan
        self.view.bind_panning(self.on_pan)

        # Widgets
        self.view.bind_mesh_change(self.run_meshing)
        self.view.bind_boundary_change(self.set_hole_group)

        # button bindings
        self.view.add_hole_btn.config(command=self.create_new_hole_group)
        self.view.bind_mode_change(self.on_mode_change)

    # ============================================
    # MATH & COORDINATE UTILITIES
    # ============================================

    def convert_pxls_to_unt(self, xc: float, yc: float) -> tuple[float, float]:
        """Converts screen pixels to engineering units."""
        x = (xc - self.canvas_offset_xc) / self.zoom + self.pan_offset_x
        y = (self.canvas_offset_yc - yc) / self.zoom + self.pan_offset_y
        return (x, y)

    def convert_unt_to_pxls(self, x: float, y: float) -> tuple[float, float]:
        """Converts engineering units to screen pixels."""
        xc = (x - self.pan_offset_x) * self.zoom + self.canvas_offset_xc 
        yc = self.canvas_offset_yc - (y - self.pan_offset_y) * self.zoom
        return (xc, yc)

    def zoom_extents(self):
        """Adjusts zoom and pan to fit all created nodes perfectly in the canvas."""
        if not self.model.nodes:
            self.log("No nodes to frame!")
            return

        # Find the Bounding Box in engineering units
        xs = [n.x for n in self.model.nodes.values()]
        ys = [n.y for n in self.model.nodes.values()]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # Center the camera
        self.pan_offset_x = (min_x + max_x) / 2.0
        self.pan_offset_y = (min_y + max_y) / 2.0

        # Calculate the new Zoom
        model_w = max_x - min_x
        model_h = max_y - min_y

        cw = self.view.canvas.winfo_width()
        ch = self.view.canvas.winfo_height()

        # use 80% of the screen so points don't touch the absolute edge
        usable_cw = cw * 0.8
        usable_ch = ch * 0.8

        # Prevent division by zero if there is only 1 node, or a perfectly straight horizontal/vertical line
        zoom_x = (usable_cw / model_w) if model_w > 1e-6 else float('inf')
        zoom_y = (usable_ch / model_h) if model_h > 1e-6 else float('inf')

        # The new zoom must be the smaller of the two to ensure both dimensions fit
        new_zoom = min(zoom_x, zoom_y)

        # If it's infinity (meaning there's exactly 1 node), just default to zoom 50
        self.zoom = new_zoom if new_zoom != float('inf') else 50.0

        self.log("Zoom Extents applied.")
        self.on_canvas_update()

    def apply_precision(self, num):
        s = 10**self.precision
        return round(num / s) * s
    
    def get_closest_node_id(self, x_unt:float, y_unt:float) -> int | None:
        # 10 pixels of tolerance, converted to engineering units
        tolerance_unt = 10 / self.zoom 
        
        closest_id = None
        min_dist = float('inf')
        
        for nid, node in self.model.nodes.items():
            dist = hypot(node.x - x_unt, node.y - y_unt)
            if dist < tolerance_unt and dist < min_dist:
                min_dist = dist
                closest_id = nid
                
        return closest_id


    # ============================================
    # VIEW RENDER PIPELINE
    # ============================================
    def on_mode_change(self, new_mode:str, new_submode:str | None):
        self._stop_drawing() # Clear active lines
        self.mode = new_mode
        
        if new_mode == "edge" and new_submode:

            # check if it's possible to create such node
            if ( (new_submode == "linear" and len(self.model.nodes) < 2) or (len(self.model.nodes) < 3)):
                self.log("Number of nodes not sufficient", "warn")
                # if its impossible to create an edge, force mode into node
                self.mode, self.sub_mode = "node", None
                return
            
            self.view.clear_misc_from_canvas()
            self.sub_mode = new_submode
            self.view.mode_text_var.set(f"✏️ Edge ({new_submode.capitalize()})")
            self.log("Edge mode: Select first node.")
        
        elif new_mode == "node":
            self.view.mode_text_var.set("✏️ Node")
            self.log("Node Mode: Click anywhere to place a node.")

        elif new_mode in {"support", "force"} and new_submode:
            self.view.mode_text_var.set(f"{new_mode.capitalize()} ({new_submode.capitalize()})")
            self.sub_mode = new_submode
            self.log(f"{new_mode.capitalize()} Mode: Select {new_submode.capitalize()} to apply support!")
        
        elif new_mode == "mesh":
            if len(self.model.nodes) < 3:
                self.log("Not enough nodes to define Mesh!", "warn")
                return
            elif len(self.model.edges) < 2:
                self.log("Not enough edges to define Mesh!", "warn")
                return
            elif not self.model.supports:
                self.log("Please define supports before applying Mesh!", "warn")
                return
            
            self.view.mode_text_var.set("Mesh")
            self.log("Move slider to update mesh!")

        elif new_mode == "utils":            
            if new_submode == "move":
                self.log("Click Node you want to move")
            elif new_submode == "split":
                self.log("Click first node of edge you want to split")
            
            self.sub_mode = new_submode

        self.view.set_toolbar_visibility(self.mode, self.sub_mode)
    
    def log(self, value:str, kind:str = "normal"):
        """
        Updates user on what's recently happened
        """
        self.view.update_status_message(value, kind)
        print(value)
    
    def _draw_nodes(self):
        """
        Helper that draws nodes stored in models
        """
        points = dict()
        for node_id, node in self.model.nodes.items():
            points[node_id] = self.convert_unt_to_pxls(node.x, node.y)
        self.view.draw_nodes(points, active_node_ids=self.active_node_ids)

    def _draw_edges(self):
        """
        Helper that draws edges stored in models
        """
        # Maps boundary name to a LIST of edges
        lines_to_draw = {}  
        curves_to_draw = {} 

        for edge_id, edge in self.model.edges.items():
            n_start = self.model.nodes[edge.start_node]
            n_end = self.model.nodes[edge.end_node]
            edge_boundary = edge.boundary_group 
            
            p_start = self.convert_unt_to_pxls(n_start.x, n_start.y)
            p_end = self.convert_unt_to_pxls(n_end.x, n_end.y)
            
            if edge.type == "linear":
                # Ensure the list exists for this boundary, then append the coordinates
                lines_to_draw.setdefault(edge_boundary, []).append((*p_start, *p_end))
                
            elif edge.type == "parabola" and edge.mid_node:
                n_mid = self.model.nodes[edge.mid_node]
                curve_unts, _ = self.math.calculate_parabola_points(n_start.as_tuple(), n_end.as_tuple(), n_mid.as_tuple())
                curve_pxls = [self.convert_unt_to_pxls(x, y) for x, y in curve_unts]
                
                curves_to_draw.setdefault(edge_boundary, []).append(curve_pxls)
                
            elif edge.type == "circle" and edge.mid_node:
                n_mid = self.model.nodes[edge.mid_node]
                curve_unts, _ = self.math.calculate_circle_points(n_start.as_tuple(), n_end.as_tuple(), n_mid.as_tuple())
                curve_pxls = [self.convert_unt_to_pxls(x, y) for x, y in curve_unts]
                
                curves_to_draw.setdefault(edge_boundary, []).append(curve_pxls)
                
        self.view.draw_edges(lines_to_draw, curves_to_draw, self.preview_line, self.preview_curve)

    def _draw_supports(self):
        """Calculates pixel coordinates for all supports and sends them to the View."""
        support_data_to_draw = []

        # Process Node Supports (Just 1 point per node)
        for node_id, support_type in self.model.supports.nodes.items():
            node = self.model.nodes[node_id]
            px, py = self.convert_unt_to_pxls(node.x, node.y)
            support_data_to_draw.append((support_type, (px, py)))

        # Process Edge Supports (Distribute multiple points along the edge)
        for edge_id, support_type in self.model.supports.edges.items():
            edge = self.model.edges[edge_id]
            n_start = self.model.nodes[edge.start_node]
            n_end = self.model.nodes[edge.end_node]
            points_unt = []
            
            # DYNAMIC ICON SPACING LOGIC
            if edge.type == "linear" or edge.mid_node is None:
                length_unt = hypot(n_end.x - n_start.x, n_end.y - n_start.y)
            else:
                n_mid = self.model.nodes[edge.mid_node]
                length_unt = (
                    hypot(n_mid.x - n_start.x, n_mid.y - n_start.y) + 
                    hypot(n_end.x - n_mid.x, n_end.y - n_mid.y)
                )

            length_pxls = length_unt * self.zoom

            # Define how many pixels between each support icon
            target_spacing_pxls = 50.0 

            # Calculate num_icons (Always guarantee at least 2
            num_icons = max(2, int(length_pxls / target_spacing_pxls))

            if edge.type == "linear":
                # Linear interpolation
                for i in range(num_icons + 1):
                    t = i / num_icons
                    x = n_start.x + t * (n_end.x - n_start.x)
                    y = n_start.y + t * (n_end.y - n_start.y)
                    points_unt.append((x, y))
            else:
                assert edge.mid_node is not None
                n_mid = self.model.nodes[edge.mid_node]
                # Reuse your existing math helpers!
                if edge.type == "parabola":
                    points_unt, _ = self.math.calculate_parabola_points(n_start.as_tuple(), n_end.as_tuple(), n_mid.as_tuple(), segments=num_icons)
                elif edge.type == "circle":
                    points_unt, _ = self.math.calculate_circle_points(n_start.as_tuple(), n_end.as_tuple(), n_mid.as_tuple(), segments=num_icons)

            # Convert all calculated edge points to pixels
            for x, y in points_unt:
                px, py = self.convert_unt_to_pxls(x, y)
                support_data_to_draw.append((support_type, (px, py)))


        #  Tell the View to draw them!
        self.view.draw_supports(support_data_to_draw)

    def _draw_forces(self):
        """
        Calculates pixels coordinates and invokes viewer for forces
        """
        force_data_to_draw = []

        for node_id, point_load in self.model.forces.nodes.items():
            node = self.model.nodes[node_id]
            px, py = self.convert_unt_to_pxls(node.x, node.y)
            force_data_to_draw.append(((*point_load.as_polar(), point_load.m), (px, py)))
        
        for edge_id, dist_load in self.model.forces.edges.items():
            edge = self.model.edges[edge_id]
            n_start = self.model.nodes[edge.start_node]
            n_end = self.model.nodes[edge.end_node]
            points_unt = []
            
            # DYNAMIC ICON SPACING LOGIC
            if edge.type == "linear" or edge.mid_node is None:
                length_unt = hypot(n_end.x - n_start.x, n_end.y - n_start.y)
            else:
                n_mid = self.model.nodes[edge.mid_node]
                length_unt = (
                    hypot(n_mid.x - n_start.x, n_mid.y - n_start.y) + 
                    hypot(n_end.x - n_mid.x, n_end.y - n_mid.y)
                )

            length_pxls = length_unt * self.zoom # unt * pxl/unt

            target_spacing_pxls = 50.0

            num_icons = max(2, int(length_pxls / target_spacing_pxls))

            # get coordinate and tangent angles, then convert to normal
            points_and_angles = []

            if edge.type == "linear":
                dx = n_end.x - n_start.x
                dy = n_end.y - n_start.y
                # Tangent angle for a straight line is constant
                tangent_angle = degrees(atan2(dy, dx))
                
                for i in range(num_icons + 1):
                    t = i / num_icons
                    x = n_start.x + t * dx
                    y = n_start.y + t * dy
                    points_and_angles.append(((x, y), tangent_angle))
            else:
                assert edge.mid_node is not None
                n_mid = self.model.nodes[edge.mid_node]
                # Reuse our MathHelper to get both positions and tangents instantly
                if edge.type == "parabola":
                    pts, angs = self.math.calculate_parabola_points(n_start.as_tuple(), n_end.as_tuple(), n_mid.as_tuple(), segments=num_icons)
                elif edge.type == "circle":
                    pts, angs = self.math.calculate_circle_points(n_start.as_tuple(), n_end.as_tuple(), n_mid.as_tuple(), segments=num_icons)
                
                # Pair them up
                for pt, ang in zip(pts, angs):
                    points_and_angles.append((pt, ang))
            
            # APPLY FORCES TO CALCULATED POINTS
            
            # 1. Pre-calculate the normal offset ONLY if it's a pressure load
            normal_offset = 0
            if dist_load.direction_type == "normal":
                if edge.type != "linear" and edge.mid_node:
                    is_ccw = self.math.is_curve_ccw(n_start.as_tuple(), n_mid.as_tuple(), n_end.as_tuple())
                    normal_offset = -90 if is_ccw else 90
                else:
                    # Standard convention for straight lines
                    normal_offset = 90 

            # 2. Format the data for the View
            for (x, y), tangent_angle in points_and_angles:
                px, py = self.convert_unt_to_pxls(x, y)
                
                # Check your DistributedLoad dataclass property
                if dist_load.direction_type == "global":
                    # Gravity / Wind loads completely ignore the edge's curve
                    final_angle = dist_load.global_angle
                else:
                    # Pressure loads are strictly perpendicular to the curve tangent
                    final_angle = tangent_angle + normal_offset
                    
                # Append in the exact format the View expects
                force_data_to_draw.append(((dist_load.magnitude, final_angle, dist_load.moment), (px, py)))

        # INVOKE VIEWER
        self.view.draw_forces(force_data_to_draw)
                
    def _draw_mesh(self):
        mesh = self.model.mesh
        nodes_pxl = [self.convert_unt_to_pxls(*p) for p in mesh.nodes] if mesh.nodes else []
        self.view.draw_mesh(nodes_pxl, mesh.triangles)

    def on_canvas_update(self):
        # get canvas info
        cw = self.view.canvas.winfo_width()
        ch = self.view.canvas.winfo_height()
        # update where is the center of the canvas
        self.canvas_offset_xc = cw / 2
        self.canvas_offset_yc = ch / 2

        # clear misc edges

        # define pan offset in pixels
        pixel_shift_x = self.pan_offset_x * self.zoom
        pixel_shift_y = -self.pan_offset_y * self.zoom # Negative because Y-axis is inverted

        self.view.draw_axis(
            topleft_unts=self.convert_pxls_to_unt(0,0),
            botright_unts=self.convert_pxls_to_unt(cw, ch),
            offset_pxls=(pixel_shift_x, pixel_shift_y),
            axis_line_width=2
        )

        self.view.draw_grid(
            offset_pxls=(pixel_shift_x, pixel_shift_y),
            zoom=self.zoom,
            precision=self.precision
        )

        self._draw_edges()
        self._draw_nodes()
        self._draw_supports()
        self._draw_forces()
        self._draw_mesh()
        
    # ============================================
    # MOUSE EVENT HANDLERS
    # ============================================
    def on_pan(self, x:float, y:float, kind:str):
        match kind:
            case "start":
                # Record the starting pixel coordinates of the drag
                self._pan_start_xc = x
                self._pan_start_yc = y
                
                # Change cursor to hand (or use "fleur" for the 4-way CAD arrow)
                return

            case "drag":
                # Calculate how many pixels the mouse moved since the last frame
                dx = x - self._pan_start_xc
                dy = y - self._pan_start_yc

                # Convert pixel delta to unit delta and apply it to the pan offsets.
                # X is subtracted and Y is added to ensure the canvas "sticks" to the mouse.
                self.pan_offset_x -= dx / self.zoom
                self.pan_offset_y += dy / self.zoom

                # Update the reference coordinates for the next motion event
                self._pan_start_xc = x
                self._pan_start_yc = y

                # Redraw the grid and axis
                self.on_canvas_update()
                
                # TODO: Also call the method that redraws your nodes and edges here 
                # so they move with the grid.

                return

            case "end":
                # Restore the default cursor (an empty string resets it, or use "crosshair")

                # Restore variables
                self._pan_start_xc = 0.0
                self._pan_start_yc = 0.0

    def on_mouse_scroll(self, direction: float, modifier="none"):
        # Route the action based on the explicit modifier string
        pan_speed = 10 / self.zoom
        
        if modifier == "shift":
            # Change Precision
            self.precision -= direction 
            self.precision = max(-4, min(3, self.precision))

            self.log(f"Snap precision set to: 10E{self.precision}")
            
        elif modifier == "ctrl":
            # Change Zoom
            zoom_factor = 1.1 if direction == 1 else 0.9
            self.zoom *= zoom_factor

        elif modifier == "none":
            # y Pan
            self.pan_offset_y += (direction * pan_speed)

        elif modifier == "ctrl-shift":
            # x Pan
            self.pan_offset_x += (direction * pan_speed)            

        #  Trigger screen update
        self.on_canvas_update()

    def on_mouse_move(self, x, y):
        # as unt
        x, y = [round(self.apply_precision(i), 6) for i in self.convert_pxls_to_unt(x, y)]
        # only get coord values after precision calculation
        xc, yc = self.convert_unt_to_pxls(x, y)

        
        match self.mode:
            case "node":
                self.preview_line.clear()
                start_px = self.convert_unt_to_pxls(*self.active_points[0]) if len(self.active_points) > 0 else None
                # Draw coordinates on mouse
                self.view.draw_near_mouse(
                    mouse_coords_unt=(x, y),
                    mouse_coords_pxl=(xc, yc),
                )
                
                # draw preview line
                if start_px:
                    self.preview_line = [
                        *start_px,
                        xc, yc
                    ]
                    self.on_canvas_update()

                   
            
            case "edge":

                closest_node_id = self.get_closest_node_id(x, y)

                if len(self.active_node_ids) == 1 and self.sub_mode == "linear":
                    self.preview_line.clear()
                    if closest_node_id and closest_node_id != self.active_node_ids[0]:
                        active_node = self.model.nodes[self.active_node_ids[0]]
                        closest_node = self.model.nodes[closest_node_id]
                        self.preview_line = [
                            *self.convert_unt_to_pxls(*active_node.as_tuple()), 
                            *self.convert_unt_to_pxls(*closest_node.as_tuple())    
                        ]
                        self.on_canvas_update()


                if len(self.active_node_ids) == 2:
                    self.preview_curve.clear()
                    

                    if closest_node_id and closest_node_id not in self.active_node_ids:
                        n1, n2, n3 = [self.model.nodes[i] for i in self.active_node_ids + [closest_node_id,]]

                        if self.sub_mode == "circle":

                            points_unt, _ = self.math.calculate_circle_points(
                                n1.as_tuple(), n2.as_tuple(), n3.as_tuple()
                            )
                        
                        elif self.sub_mode == "parabola":
                            points_unt, _ = self.math.calculate_parabola_points(
                                n1.as_tuple(), n2.as_tuple(), n3.as_tuple()
                            )

                        points_pxl = [self.convert_unt_to_pxls(x, y) for x, y in points_unt]
                        self.preview_curve = points_pxl

                        self.on_canvas_update()





            case "parabola":
                # Add logic to preview the parabola using self.active_points and (mx, my)
                pass    

            case "utils":
                if self.sub_mode == "move" and len(self.active_node_ids) == 1:
                    self.view.draw_near_mouse(
                        mouse_coords_unt=(x, y),
                        mouse_coords_pxl=(xc, yc),
                    )

    def on_click_canvas(self, side:str, x, y):
        """Helper to parse click"""
        if side == "left":
            self.on_left_click_canvas(x, y)
        else:
            self.on_right_click_canvas(x, y)

    def on_left_click_canvas(self, x, y):
        x_raw, y_raw = self.convert_pxls_to_unt(x, y)
        # apply precision
        x, y = self.apply_precision(x_raw), self.apply_precision(y_raw)

        clicked_node_id = self.get_closest_node_id(x_raw, y_raw)        

        match self.mode:
            case "node":
                if clicked_node_id is not None:
                    self.log("Cannot create node: Too close to an existing node.", kind="warn")
                    return
                self.active_points.append((x, y))
                self._commit_node()


            case "edge":
                if not clicked_node_id: return 
                
                if self.active_node_ids and clicked_node_id in self.active_node_ids:
                    self.log("Node already selected!", kind="warn")
                    return
                
                self.active_node_ids.append(clicked_node_id)
                self.on_canvas_update()

                if self.sub_mode == "linear":
                    if len(self.active_node_ids) == 1:
                        self.log("Select end node.")
                    elif len(self.active_node_ids) == 2:
                        self._commit_edge()
                else: 
                    # Parabola or Circle
                    if len(self.active_node_ids) == 1:
                        self.log("Select end node.")
                    elif len(self.active_node_ids) == 2:
                        self.log("Select the mid node to define the curve.")
                    elif len(self.active_node_ids) == 3:
                        self._commit_edge()

            case "support":
                if not clicked_node_id: return
                support = self.view.get_support()
                
                if len(support) == 0:
                    self.log("Select at least one support option!", "warn")

                if self.sub_mode == "node":
                    
                    if self.model.node_has_support(clicked_node_id): 
                        self.log("Cannot create support: Node already has a support!", kind="warn")
                        return

                    # get kind of support from view

                    self._commit_support(clicked_node_id, support)

                elif self.sub_mode == "edge":
                    
                    self.active_node_ids.append(clicked_node_id)

                    if len(self.active_node_ids) == 1:
                        self.log(f"Select another node from edge to add the support to it")
                        self.on_canvas_update()

                    elif len(self.active_node_ids) == 2:
                        # check if edge exists
                        edge_id = self.model.get_edge_id_by_nodes(*self.active_node_ids)
                        
                        if not edge_id:
                            self.log("No edge connects these two nodes!", "warn")
                            self.active_node_ids.clear()
                            self.on_canvas_update()
                            return
                        
                        # check if edge has support
                        if self.model.edge_has_support((self.active_node_ids[0], self.active_node_ids[1])):
                            self.log("Edge already has defined supports for it!", "warn")
                            self.active_node_ids.clear()
                            self.on_canvas_update()
                            return
                        
                        self._commit_support((self.active_node_ids[0], self.active_node_ids[1]), support)

            case "force":
                if not clicked_node_id: return
                
                # get data on view
                is_pressure, fx, fy, m = self.view.get_force()

                if self.sub_mode == "node":
                    if self.model.node_has_point_load(clicked_node_id): 
                        self.log("Cannot create force: Node already has a force!", kind="warn")
                        return

                    self._commit_point_load(clicked_node_id, fx, fy, m)

                elif self.sub_mode == "edge":
                    
                    self.active_node_ids.append(clicked_node_id)

                    if len(self.active_node_ids) == 1:
                        self.log(f"Select another node from edge to add the force to it")
                        self.on_canvas_update()

                    elif len(self.active_node_ids) == 2:
                        # check if edge exists
                        edge_id = self.model.get_edge_id_by_nodes(*self.active_node_ids)
                        
                        if not edge_id:
                            self.log("No edge connects these two nodes!", "warn")
                            self.active_node_ids.clear()
                            self.on_canvas_update()
                            return
                        
                        if self.model.edge_has_distributed_load((self.active_node_ids[0], self.active_node_ids[1])):
                            self.log("Edge already has defined loads for it!", "warn")
                            self.active_node_ids.clear()
                            self.on_canvas_update()
                            return
                        
                        magnitude = fx if is_pressure else hypot(fx, fy)
                        global_angle = 0.0 if is_pressure else degrees(atan2(fy, fx))

                        # THE MAGNITUDE INVERSION TRICK
                        edge = self.model.edges[edge_id]
                        
                        # If the user clicked the nodes backwards relative to the 
                        # edge's internal definition, flip the pressure sign
                        if is_pressure and self.active_node_ids[0] == edge.start_node:
                            magnitude = -magnitude
                        
                        self._commit_distributed_load(
                            (self.active_node_ids[0], self.active_node_ids[1]),
                            magnitude,
                            moment=m,
                            direction_type="normal" if is_pressure else "global",
                            global_angle=global_angle
                        )
            case "utils":
                if self.sub_mode == "move":
                    
                    # STATE 0: Select the node to move
                    if not self.active_node_ids:
                        if not clicked_node_id: 
                            return # Clicked empty space, ignore
                        
                        # Select the node and stop execution for this click
                        self.active_node_ids.append(clicked_node_id)
                        self.log(f"Selected Node {clicked_node_id}. Click new location.")
                        self.on_canvas_update()
                        return 

                    # STATE 1: Choose the destination
                    elif len(self.active_node_ids) == 1:
                        target_node = self.active_node_ids[0]
                        
                        # Case A: Clicked empty space
                        if clicked_node_id is None:
                            self.model.move_node(target_node, x, y)
                            self.model.clear_mesh()
                            self.log("Node moved!")
                        
                        # Case B: Clicked a DIFFERENT node
                        elif clicked_node_id != target_node:
                            self.log("Cannot move node: Another node is already there!", "warn")
                            
                        # Case C: Clicked the SAME node
                        else:
                            self.log("Move cancelled.")

                        # In ALL three cases reset the tool
                        self.active_node_ids.clear()
                        self.on_canvas_update()
                        return
                   
                if self.sub_mode == "split":
                    if not clicked_node_id: return

                    if self.active_node_ids and clicked_node_id in self.active_node_ids:
                        self.log("Node already selected!", kind="warn")
                        return
                    
                    self.active_node_ids.append(clicked_node_id)
                    
                    # 0. Wait for another click
                    if len(self.active_node_ids) == 1:
                        self.log("Select another node from element.")
                        self.on_canvas_update()
                        return

                    elif len(self.active_node_ids) == 2:
                        self._split_element((self.active_node_ids[0], self.active_node_ids[1]))

                    
    def on_right_click_canvas(self, x, y):
        x_raw, y_raw = self.convert_pxls_to_unt(x, y)

        print(x_raw, y_raw)
        # apply precision
        x, y = self.apply_precision(x_raw), self.apply_precision(y_raw)

        clicked_node_id = self.get_closest_node_id(x_raw, y_raw)
        if not clicked_node_id: return



        # left clicking deletes stuff
        if self.mode == "node" or (self.mode in {"support", "force"} and self.sub_mode == "node"):
            self._delete_from_model(clicked_node_id)
        

        elif self.mode == "edge" or (self.mode in {"support", "force"} and self.sub_mode == "edge"):
            
            
            if self.active_node_ids and clicked_node_id in self.active_node_ids:
                self.log("Node already selected!", kind="warn")
                return
            
            self.active_node_ids.append(clicked_node_id)
            self.on_canvas_update()

            if len(self.active_node_ids) == 1:
                self.log(f"Right click another node from edge to delete its {self.mode.capitalize()}.")
            elif len(self.active_node_ids) == 2:
                nodes_to_delete = (self.active_node_ids[0], self.active_node_ids[1])
                self.active_node_ids.clear()
                self._delete_from_model(nodes_to_delete)

    # ============================================
    # KEYBOARD EVENT HANDLERS
    # ============================================
    def on_key_press(self, char:str, keysym:str):

        if char and len(char) == 1 and char.isprintable():
                if self.mode == "node" and char.isdigit() or char in ".,-":
                    if char == ",": char = "."
                    self.coord_buffer[self.cur_editing_coord] += char
                    self.view.update_coord_input(self.coord_buffer, self.cur_editing_coord)
                elif char == ";":
                    # updates text
                    self._switch_editing_coord() 
                elif char.isalpha():
                    match char:
                        case "n": self.on_mode_change("node", None)
                        case "l": self.on_mode_change("edge", "linear")
                        case "p": self.on_mode_change("edge", "parabola")
                        case "c": self.on_mode_change("edge", "circle")
                        case "s": self.on_mode_change("support", "node")


        elif not keysym:
            return
        
        match keysym:
            case "BackSpace":
                if self.coord_buffer[self.cur_editing_coord]:
                    self.coord_buffer[self.cur_editing_coord] = self.coord_buffer[self.cur_editing_coord][:-1]
                self.view.update_coord_input(self.coord_buffer, self.cur_editing_coord)

            case "Escape":
                self.log("Action cancelled. Selection cleared")
                self._stop_drawing()
                
                # clear buffers
                for key in self.coord_buffer:
                    self.coord_buffer[key] = ""

            case "Space": self.zoom_extents()
                    
            case "Tab": 
                if self.mode == "node":
                    # is typing
                    if any(len(i) > 0 for i in self.coord_buffer.values()):
                        # is typing
                        self._switch_editing_coord()
                elif self.mode in {"support", "force"}:
                    self.sub_mode = "node" if self.sub_mode == "edge" else "edge"
                assert self.sub_mode is str
                self.view.mode_text_var.set(f"{self.mode.capitalize()} ({self.sub_mode.capitalize()})")


                

            case "Delete": self._delete_from_model()

    def on_enter_press(self):
        
        try:
            # try to convert coordinates to numeric
            x, y = float(self.coord_buffer["x"]), float(self.coord_buffer["y"])
            
            # set mode as node
            self.on_mode_change("node", None)
            if self.get_closest_node_id(x, y) is not None:
                self.log("Cannot create node: Too close to an existing node. Zoom in if necessary", kind="warn")
                return
            
            self.active_points.append((x, y))

                        
            # then, commit new points
            self._commit_node()

            # fake mouse move
            xc, yc = self.convert_unt_to_pxls(x, y)
            self.on_mouse_move(xc, yc)


        except (ValueError, TypeError):
            # if at least one value is not numeric
            self.log("Invalid coordinate format. Please enter valid numbers", kind="warn")
            pass

        # restart coord_buffer
        self.cur_editing_coord = "x"
        for key in self.coord_buffer.keys(): self.coord_buffer[key] = ""
        self.view.update_coord_input(self.coord_buffer, self.cur_editing_coord)

    # ==========================================
    # STATE MANAGEMENT HELPERS
    # ==========================================
    def _switch_editing_coord(self):
        if self.cur_editing_coord == "x":
            self.cur_editing_coord = "y"
        else: 
            self.cur_editing_coord = "x"
        # update text on view
        self.view.update_coord_input(self.coord_buffer, self.cur_editing_coord)
    
    def _clear_preview_line(self, clear_item_ids:bool = True):
        # clear previour preview frame
        for item_id in self.view.preview_item_ids:
            
            self.view.canvas.delete(item_id)
        # if false, only disables line for a frame
        if clear_item_ids: self.view.preview_item_ids.clear()
        
    def _stop_drawing(self):
        self.active_points.clear()
        self.active_node_ids.clear()
        self.preview_curve.clear()
        self.preview_line.clear()
        self.on_canvas_update()

    # ==========================================
    # MODEL UTILITIES
    # ==========================================

    def set_hole_group(self, value:str):
        self.active_boundary = value
        self.log(f"Set boundary as {value}")

    def create_new_hole_group(self):
        """Adds a new Hole to the Combobox and selects it."""
        values = list(self.view.boundary_cb["values"])
        
        new_hole_name = f"Hole {len(values)}"
        values.append(new_hole_name)
        
        # Update UI
        self.view.update_boundary_values(values)
        self.active_boundary = self.view.boundary_var.get()



        self.log(f"Started new boundary: {new_hole_name}")

    # ==========================================
    # MODEL COMMIT LOGIC
    # ==========================================
      
    def _commit_node(self):
        new_x, new_y = self.active_points[-1]
        self.model.add_node(new_x, new_y)
        
        self.active_points = [(new_x, new_y)]
        self.log(f"Node created at [{new_x}, {new_y}]")
        self.remove_mesh() # to edit geometry will always restart mesh
        self.on_canvas_update()

    def _commit_edge(self):
        start_id = self.active_node_ids[0]
        end_id = self.active_node_ids[1]        
        mid_id = self.active_node_ids[2] if len(self.active_node_ids) == 3 else None
        
        assert self.sub_mode is str
        self.model.add_edge(
            type=self.sub_mode,
            start_node_id=start_id,
            end_node_id=end_id,
            mid_node_id=mid_id,
            boundary_group=self.active_boundary
        )
        
        # Reset state
        self.active_node_ids = [
            self.active_node_ids[-1 if self.sub_mode == "linear" else -2]
        ]
        
        self.log(f"{self.sub_mode.capitalize()} edge created! Select next end node to continue, or press Esc to stop.")
        self.remove_mesh() # to edit geometry will always restart mesh 
        self.on_canvas_update()

    def _commit_support(self, target:int | tuple[int, int], support:str):
        
        success = self.model.add_support(target, support)
        
        if success:
            at_ = "node" if isinstance(target, int) else "edge"
            self.log(f"Defined support ({support}) at {at_}!")
        else:
            self.log(f"Something went wrong!", "warn")

        self.active_node_ids = []

        self.on_canvas_update()

    def _commit_point_load(self, node_id:int, fx, fy, m):
        success = self.model.add_point_load(node_id, fx, fy, m)
        
        if success:
            self.log(f"Defined point force of [{fx}, {fy}] at Node!")
        else:
            self.log(f"Something went wrong!", "warn")

        self.active_node_ids = []

        self.on_canvas_update()

    def _commit_distributed_load(self, node_ids: tuple[int, int], magnitude:float, moment:float, direction_type:str = "normal", global_angle:float = 0):
        success = self.model.add_distributed_load(node_ids, magnitude, moment, direction_type, global_angle)

        if success:
            f, m = ("distributed force", f"{magnitude} > {global_angle}°") \
                if direction_type == "global" \
                else ("pressure", f"{magnitude}")
            self.log(f"Defined {f} of [{m}] at Edge!")
        else:
            self.log(f"Something went wrong!", "warn")

        self.active_node_ids = []

        self.on_canvas_update()
        
    def _delete_from_model(self, target: int | tuple[int, int] | None = None):
        if self.mode == "node":
            if isinstance(target, tuple):
                raise TypeError("target of delete_node at Model may not be a tuple!")
            self.model.delete_node(target)
        elif self.mode == "edge": self.model.delete_edge(target)
        elif self.mode == "support": self.model.delete_support(target)
        elif self.mode == "force": self.model.delete_force(target)
        elif self.mode == "mesh": self.model.clear_mesh()
        
        if self.mode in ["node", "edge", "mesh"]:
            # only above accept none
            self.log(f"{"Last" if target is None else "Selected"} {self.mode.capitalize()} deleted!")
        self.remove_mesh() # to edit geometry will always restart mesh 
        self.on_canvas_update()

    def _split_element(self, target:tuple[int, int]):
        num_segments = self.view.ask_for_segments()

        if isinstance(num_segments, int):
            success = self.model.split_edge(target, num_segments)
            if not success:
                self.log("Something went wrong. Note that only elements without supports or forces may be split.", "warn")
                return
            self.active_node_ids.clear()
            self.on_canvas_update()
    # ================================
    # SCARY STUFF
    # ================================

    def run_meshing(self, slider_value:int):

        try:
            mesher = MeshEngine(self.model, math_helper=self.math)
            self.log("Generating Mesh...")

            base_px_size = 40
            target_px_size = base_px_size * (10 ** (-slider_value / 10.0))
            actual_mesh_size = target_px_size / self.zoom

            nodes_unt, triangles = mesher.generate_mesh(mesh_size=actual_mesh_size)
            
            self.log(f"Mesh successful: {len(nodes_unt)} nodes, {len(triangles)} edges.")

            self.model.create_mesh(nodes_unt, triangles)

            self.on_canvas_update()

        except Exception as e:
            self.log(str(e), "warn")

    def remove_mesh(self):
        if self.model.mesh: self.model.clear_mesh()
        