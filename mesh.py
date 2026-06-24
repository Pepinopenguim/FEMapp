import gmsh
from typing import Dict, List, Tuple, Type
from model import FEMModel
from curve import CurveHelper

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

    def generate_mesh(self, mesh_size: float = 5.0) -> Tuple[List[Tuple[float, float]], List[Tuple[int, int, int]]]:
        """
        Generates the mesh.
        Returns:
            - A list of nodes: [(x, y), (x, y), ...]
            - A list of triangles (by node index): [(n1, n2, n3), ...]
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

        for eid, elem in self.model.edges.items():
            group = elem.boundary_group.lower()
            boundary_groups.setdefault(group, [])

            tag_start = gmsh_node_tags[elem.start_node]
            tag_end = gmsh_node_tags[elem.end_node]

            if elem.type == "linear":
                c_tag = gmsh.model.geo.addLine(tag_start, tag_end)
                
            else:
                # Discretize curved edges for high-quality Subnodes
                n_start = self.model.nodes[elem.start_node]
                n_end = self.model.nodes[elem.end_node]
                n_mid = self.model.nodes[elem.mid_node] if elem.mid_node is not None else None

                if elem.type == "parabola":
                    assert n_mid is not None
                    pts, _ = self.math.calculate_parabola_points(n_start.as_tuple(), n_end.as_tuple(), n_mid.as_tuple(), segments=10)
                elif elem.type == "circle":
                    assert n_mid is not None
                    pts, _ = self.math.calculate_circle_points(n_start.as_tuple(), n_end.as_tuple(), n_mid.as_tuple(), segments=10)

                # Add the internal subnodes to Gmsh (skip index 0 and -1 as they are the start/end base nodes)
                internal_tags = []
                for px, py in pts[1:-1]:
                    ptag = gmsh.model.geo.addPoint(px, py, 0.0, mesh_size)
                    internal_tags.append(ptag)

                # Wrap a Spline through the Start -> Subnodes -> End
                c_tag = gmsh.model.geo.addSpline([tag_start] + internal_tags + [tag_end])

            # Save the curve data so we can topologically sort it later
            boundary_groups[group].append({
                'tag': c_tag, 
                'start': elem.start_node, 
                'end': elem.end_node
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

        gmsh.finalize()
        return mesh_nodes, triangles