import gmsh
from typing import Dict, List, Tuple, Type, Any
from model import FEMModel, SolverNode
from curve import CurveHelper
from dataclasses import dataclass
from math import sin, cos, radians, hypot


@dataclass
class Mesh:
    # The MeshEngine returns this single, clean object
    nodes: dict[int, SolverNode]        # Mapped by Mesh Node ID
    triangles: list[tuple[int, int, int]]

class MeshEngine:
    def __init__(self, model: FEMModel, math_helper: Type[CurveHelper]):
        """
        math_helper stores the curve formulas
        """
        self.model = model
        self.math = math_helper 

    def _sort_curves_into_loop(self, curve_data: list[dict]) -> list:
        """
        Topological sorter. Gmsh requires curves to be chained end-to-end.
        curve_data is a list of dicts: {'tag': int, 'start': int, 'end': int}
        """
        if not curve_data:
            return []

        sorted_tags = []
        current = curve_data.pop(0)
        sorted_tags.append(current['tag'])
        current_end = current['end']

        while curve_data:
            found_next = False
            for i, candidate in enumerate(curve_data):
                if candidate['start'] == current_end:
                    # Curve is naturally oriented
                    sorted_tags.append(candidate['tag'])
                    current_end = candidate['end']
                    curve_data.pop(i)
                    found_next = True
                    break
                elif candidate['end'] == current_end:
                    
                    sorted_tags.append(-candidate['tag']) # Gmsh uses negative tags to reverse them! 
                    current_end = candidate['start']
                    curve_data.pop(i)
                    found_next = True
                    break
            
            if not found_next:
                raise ValueError("Boundary is not a closed loop! Please check your drawing.")
                
        return sorted_tags

    def _compute_supports_and_forces(self, gmsh_node_tags: dict[int, int], edge_curve_tags:dict[int, int]) -> tuple[dict[int, str], dict[int, Any]]:
        node_tag_supports = {}
        node_tag_forces = {}

        # retrieve support and force data
        # ============================================
        # ----------------- EDGE LOOP ----------------
        # ============================================
        for eid, c_tag in edge_curve_tags.items():
            # get mesh nodes for specific curve
            node_tags, _, _ = gmsh.model.mesh.getNodes(dim=1, tag=c_tag)
            
            # --------------------------------------------
            # SUPPORTS ===================================
            # --------------------------------------------
            # get edge from app model
            if eid in self.model.supports.edges:
                # if has support...
                support_string = self.model.supports.edges[eid]
                for node_tag in node_tags:
                    if node_tag in node_tag_supports:
                        existing_support = node_tag_supports[node_tag]
                        node_tag_supports[node_tag] = "".join(set(existing_support + support_string))
                    else:
                        node_tag_supports[node_tag] = support_string

            # --------------------------------------------
            # FORCES =====================================
            # --------------------------------------------
            if eid in self.model.forces.edges:
                distload = self.model.forces.edges[eid]

                # Setup base magnitudes
                q_start = distload.magnitude
                q_end = distload.magnitude_end if distload.magnitude_end is not None else q_start
                moment = distload.moment
                
                if distload.direction_type == "global":
                    angle = radians(distload.global_angle)
                    global_ux, global_uy = cos(angle), sin(angle)

                # Get the 1D line elements generated on this curve
                elem_types, elem_tags, elem_node_tags = gmsh.model.mesh.getElements(dim=1, tag=c_tag)
                
                if len(elem_types) > 0:
                    node_array = elem_node_tags[0] 
                    
                    # First Pass: Calculate total mesh length to find interpolation factors
                    total_length = 0.0
                    segment_lengths = []
                    for i in range(0, len(node_array), 2):
                        c1, _, _, _ = gmsh.model.mesh.getNode(node_array[i])
                        c2, _, _, _ = gmsh.model.mesh.getNode(node_array[i+1])
                        Le = hypot(c2[0] - c1[0], c2[1] - c1[1])
                        segment_lengths.append(Le)
                        total_length += Le
                        
                    if total_length < 1e-9: # avoid div by zero
                        continue

                    # Second Pass: Apply generalized trapezoidal FEM integration
                    current_s = 0.0 
                    
                    for i, Le in enumerate(segment_lengths):
                        n1_tag = node_array[i * 2]
                        n2_tag = node_array[i * 2 + 1]
                        
                        # Interpolate the magnitude at the start and end of THIS element
                        t1 = current_s / total_length
                        t2 = (current_s + Le) / total_length
                        q1 = q_start + t1 * (q_end - q_start)
                        q2 = q_start + t2 * (q_end - q_start)
                        
                        # The universal FEM equivalent nodal force integral
                        F_mag_1 = (Le / 6.0) * (2 * q1 + q2)
                        F_mag_2 = (Le / 6.0) * (q1 + 2 * q2)
                        
                        m_nodal = (moment * Le) / 2
                        # >>> DIRECTION LOGIC <<<
                        if distload.direction_type == "global":
                            ux, uy = global_ux, global_uy
                        else:
                            # NORMAL DIRECTION LOGIC
                            # Get physical coordinates to find the perpendicular of THIS segment
                            c1, _, _, _ = gmsh.model.mesh.getNode(n1_tag)
                            c2, _, _, _ = gmsh.model.mesh.getNode(n2_tag)
                            dx = c2[0] - c1[0]
                            dy = c2[1] - c1[1]
                            
                            # Standard 2D Normal (Rotated 90 degrees CCW). 
                            # **********************************************************
                            # TODO - REVIEW IF ROTATION IS CORRECT
                            # **********************************************************
                            ux = -dy / Le
                            uy = dx / Le
                        
                        # Resolve into global X and Y components
                        fx1, fy1 = F_mag_1 * ux, F_mag_1 * uy
                        fx2, fy2 = F_mag_2 * ux, F_mag_2 * uy
                        
                        # Apply to nodes safely
                        for n_tag, fx, fy in [(n1_tag, fx1, fy1), (n2_tag, fx2, fy2)]:
                            if n_tag in node_tag_forces:
                                cur_fx, cur_fy, cur_m = node_tag_forces[n_tag]
                                node_tag_forces[n_tag] = (cur_fx + fx, cur_fy + fy, cur_m + m_nodal)
                            else:
                                node_tag_forces[n_tag] = (fx, fy, m_nodal)
                        
                        # Step forward for the next element
                        current_s += Le

        # ==================================================
        # SUPPORTS AT POINTS -------------------------------
        # ==================================================
        for nid, support_string in self.model.supports.nodes.items():
            geo_tag = gmsh_node_tags[nid]

            mesh_node_tags, _, _ = gmsh.model.mesh.getNodes(dim=0, tag=geo_tag)

            if len(mesh_node_tags) > 0:
                n_tag = mesh_node_tags[0]

                if n_tag in node_tag_supports:
                    existing_support = node_tag_supports[n_tag]
                    node_tag_supports[n_tag] = "".join(set(existing_support + support_string))
                else:
                    node_tag_supports[n_tag] = support_string
        
        # ==================================================
        # FORCES AT POINTS ---------------------------------
        # ==================================================
        for nid, point_load in self.model.forces.nodes.items():
            geo_tag = gmsh_node_tags[nid]

            fx, fy, moment = point_load.as_tuple()
            
            mesh_node_tags, _, _ = gmsh.model.mesh.getNodes(dim=0, tag=geo_tag)

            if len(mesh_node_tags) > 0:
                n_tag = mesh_node_tags[0]

                if n_tag in node_tag_forces:
                    cur_fx, cur_fy, cur_m = node_tag_forces[n_tag]
                    node_tag_forces[n_tag] = (cur_fx + fx, cur_fy + fy, cur_m + moment)
                else:
                    node_tag_forces[n_tag] = (fx, fy, moment)
            

        return node_tag_supports, node_tag_forces

    def generate_mesh(self, mesh_size: float = 5.0) -> tuple[dict[int, SolverNode], List[Tuple[int, int, int]]]:
        """
        Generates the mesh.
        Returns:
            - A list of nodes: [(x, y), (x, y), ...]
            - A list of triangles (by node index): [(n1, n2, n3), ...]
            - A list of supports (by node index and type)
            - A list of forces (by node index and type)
        """
        gmsh.initialize()
        gmsh.option.setNumber("General.Terminal", 0) # Suppress terminal spam
        gmsh.model.add("fem_app_mesh")

        #  Add the Base Nodes to Gmsh
        gmsh_node_tags = {}
        for nid, node in self.model.nodes.items():
            # addPoint(x, y, z, meshSize, tag)
            tag = gmsh.model.geo.addPoint(node.x, node.y, 0.0, mesh_size)
            gmsh_node_tags[nid] = tag

        #  Add Edges and Group by Boundary
        # Dictionary to store curves: group_name -> [{'tag': int, 'start': int, 'end': int}]
        boundary_groups = {} 
        # Dictionary to relate edges to gmsh curves: eid -> ctag
        edge_curve_tags = {}

        for eid, edge in self.model.edges.items():
            group = edge.boundary_group.lower()
            boundary_groups.setdefault(group, [])

            tag_start = gmsh_node_tags[edge.start_node]
            tag_end = gmsh_node_tags[edge.end_node]

            if edge.type == "linear":
                c_tag = gmsh.model.geo.addLine(tag_start, tag_end)
                
            else:
                # Discretize curved edges for high-quality Subnodes
                n_start = self.model.nodes[edge.start_node]
                n_end = self.model.nodes[edge.end_node]
                n_mid = self.model.nodes[edge.mid_node] if edge.mid_node is not None else None

                if edge.type == "parabola":
                    assert n_mid is not None
                    pts, _ = self.math.calculate_parabola_points(n_start.as_tuple(), n_end.as_tuple(), n_mid.as_tuple(), segments=10)
                elif edge.type == "circle":
                    assert n_mid is not None
                    pts, _ = self.math.calculate_circle_points(n_start.as_tuple(), n_end.as_tuple(), n_mid.as_tuple(), segments=10)

                # Add the internal subnodes to Gmsh (skip index 0 and -1 as they are the start/end base nodes)
                internal_tags = []
                for px, py in pts[1:-1]:
                    ptag = gmsh.model.geo.addPoint(px, py, 0.0, mesh_size)
                    internal_tags.append(ptag)

                # Wrap a Spline through the Start -> Subnodes -> End
                c_tag = gmsh.model.geo.addSpline([tag_start] + internal_tags + [tag_end])

            edge_curve_tags[eid] = c_tag 
                
            # Save the curve data so we can topologically sort it later
            boundary_groups[group].append({
                'tag': c_tag, 
                'start': edge.start_node, 
                'end': edge.end_node
            })

        #  Create Curve Loops
        loop_tags = []
        external_loop = None

        for group, curves in boundary_groups.items():
            sorted_tags = self._sort_curves_into_loop(curves)
            loop_tag = gmsh.model.geo.addCurveLoop(sorted_tags)
            
            if group == "external":
                external_loop = loop_tag
            else:
                loop_tags.append(loop_tag)

        if external_loop is None:
            gmsh.finalize()
            raise ValueError("No 'External' boundary group found to mesh inside of!")

        #  Define the 2D Surface (First loop is external, subsequent are holes)
        gmsh.model.geo.addPlaneSurface([external_loop] + loop_tags, tag=1)

        #  Generate the Mesh
        gmsh.model.geo.synchronize()
        gmsh.model.mesh.generate(2) # Generate 2D mesh

        #  Extract the Data to native Python formats
        node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
        # Gmsh returns a flat array [x1, y1, z1, x2, y2, z2...]. We slice it to get pairs.
        mesh_nodes = [(node_coords[i], node_coords[i+1]) for i in range(0, len(node_coords), 3)]
                    
        # Map Gmsh's internal Node IDs to a 0-based array index for our triangles
        tag_to_index = {tag: i for i, tag in enumerate(node_tags)}

        # define supports and forces for each node_tag
        node_tag_supports, node_tag_forces = self._compute_supports_and_forces(gmsh_node_tags, edge_curve_tags)
        # for supports and forces, map to newly created indexes
        
        supports = {}
        for tag, v in node_tag_supports.items():
            if tag in tag_to_index:
                supports[tag_to_index[tag]] = v
        forces = {}
        for tag, v in node_tag_forces.items():
            if tag in tag_to_index:
                forces[tag_to_index[tag]] = v

        # Extract Triangles (Edge Type 2 in Gmsh is a 3-node triangle)
        elem_types, elem_tags, elem_node_tags = gmsh.model.mesh.getElements(dim=2)
        
        triangles = []
        if 2 in elem_types: # If triangles were generated
            idx = list(elem_types).index(2)
            flat_triangle_nodes = elem_node_tags[idx]
            
            # Group into sets of 3 and map to array indices
            for i in range(0, len(flat_triangle_nodes), 3):
                n1 = tag_to_index[flat_triangle_nodes[i]]
                n2 = tag_to_index[flat_triangle_nodes[i+1]]
                n3 = tag_to_index[flat_triangle_nodes[i+2]]
                triangles.append((n1, n2, n3))

        solver_nodes = {}
        for i, (x, y) in enumerate(mesh_nodes):
            
            # Default to no constraints / no loads
            support_str = supports.get(i, None)
            fx, fy, m = forces.get(i, (0.0, 0.0, 0.0)) # Unpack but ignore the Moment!

            solver_nodes[i] = SolverNode(
                x=x, 
                y=y, 
                support=support_str, 
                fx=fx, 
                fy=fy,
                m=m
            )


        gmsh.finalize()
        return solver_nodes, triangles