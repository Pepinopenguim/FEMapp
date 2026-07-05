from dataclasses import dataclass, field, asdict
import enum
from typing import Dict, Optional, Literal, Any
from math import hypot, atan2, degrees
from src.curve import CurveHelper
import json

@dataclass
class Node:
    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        """Returns the node's coordinates as a tuple."""
        return (self.x, self.y)
    
    def as_json(self) -> dict[str, float]: return asdict(self)


@dataclass
class Edge:
    type: str          # "linear", "parabola", or "circle"
    start_node: int
    end_node: int
    mid_node: Optional[int] = None # Used for parabola/circle
    boundary_group: str = "external"

    def list_node_ids(self) -> list[int]:
        """Returns a list of nodes (as ids) that define the edge"""
        return [self.start_node, self.end_node] + ([self.mid_node,] if self.mid_node is not None else [])
    
    def as_json(self) -> dict[str, str | int | None]: return asdict(self)

@dataclass
class Support:
    # Maps ID -> Support String (e.g., {1: "xy", 4: "z"})
    nodes: Dict[int, str] = field(default_factory=dict)
    edges: Dict[int, str] = field(default_factory=dict)

    def __bool__(self):
        return bool(self.nodes) or bool(self.edges)
    
    def as_json(self) -> Dict[str, Dict[int, str]]: return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Support":
        # Cast keys back to int
        nodes = {int(k): v for k, v in data.get("nodes", {}).items()}
        edges = {int(k): v for k, v in data.get("edges", {}).items()}
        return cls(nodes=nodes, edges=edges)
    
@dataclass
class Material:
    E:float
    nu:float
    gamma:float

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.E, self.nu, self.gamma)

    def __bool__(self):
        return any([bool(i) for i in [self.E, self.nu]])

    def as_json(self): return asdict(self)

@dataclass
class PointLoad:
    fx: float = 0.0
    fy: float = 0.0
    m: float = 0.0

    def __bool__(self) -> bool:
        return any([bool(i) for i in (self.fx, self.fy, self.m)])
    
    def as_tuple(self) -> tuple[float, float, float]:
        return (self.fx, self.fy, self.m)
    
    def as_polar(self) -> tuple[float, float]:
        magn = hypot(self.fx, self.fy)
        angle = degrees(atan2(self.fy, self.fx))

        return magn, angle

    def as_json(self) -> dict[str, float]:
        # Simple dict return since all fields are floats
        return asdict(self)

@dataclass
class DistributedLoad:
    magnitude: float # This acts as magnitude_start
    moment: float
    direction_type: Literal["normal", "global"] = "normal" 
    global_angle: float = 0.0 
    magnitude_end: float | None = None 


    def as_json(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class ForceManager:
    nodes: Dict[int, PointLoad] = field(default_factory=dict)
    edges: Dict[int, DistributedLoad] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return {
            "nodes": {i: n.as_json() for i, n in self.nodes.items()},
            "edges": {i: n.as_json() for i, n in self.edges.items()},
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ForceManager":
        nodes = {int(k): PointLoad(**v) for k, v in data.get("nodes", {}).items()}
        edges = {int(k): DistributedLoad(**v) for k, v in data.get("edges", {}).items()}
        return cls(nodes=nodes, edges=edges)

@dataclass
class SolverNode:
    x: float
    y: float
    support: str | None = None          # e.g., "xy", "x", None
    fx: float = 0.0
    fy: float = 0.0
    m: float = 0.0

    def as_json(self) -> dict[str, float | str | None]:
        return asdict(self)

@dataclass
class Mesh:
    solver_nodes: dict[int, SolverNode]
    triangles: list[tuple[int, int, int]]

    def __bool__(self) -> bool:
        return bool(self.solver_nodes) or bool(self.triangles)

    def as_json(self) -> dict[str, Any]:
        return asdict(self)

class FEMModel:

    def __init__(self):
        self.nodes:Dict[int, Node] = {}
        self.edges:Dict[int, Edge] = {}
        self.mesh:Mesh = Mesh({}, [])
        self.supports:Support = Support()
        self.forces:ForceManager = ForceManager()
        self.material:Material = Material(0.0, 0.0, 0.0)
        self.results: dict[str, Any] = {}

        # for deletion memory
        self._node_counter = 0
        self._edge_counter = 0

    def set_material(self, E:float, nu:float, gamma:float):
        if E < 1e-6:
            raise ValueError("Cannot define a material with Young equal to zero nor negative!")

        if nu > .5 or nu < -1:
            raise ValueError("Poisson's ratio cannot be bigger than 0.5 or lesser than -1!")

        self.material = Material(E, nu, gamma)


    def add_node(self, x:float, y:float) -> int:
        self._node_counter += 1

        self.nodes[self._node_counter] = Node(x, y)

        return self._node_counter
    
    def delete_node(self, node_id: int | None = None) -> bool:
        if node_id is None: 
            if not self.nodes: return False
            node_id = max(self.nodes.keys())

        if node_id not in self.nodes: return False

        self.nodes.pop(node_id)

        # delete supports associated with node
        if node_id in self.supports.nodes:
            self.supports.nodes.pop(node_id)

        # delete edges connected to active node
        for edge_id, edge in list(self.edges.items()):
            if node_id in edge.list_node_ids():
                self.delete_edge(edge_id)

        # delete forces applied to active node
        if node_id in self.forces.nodes:
            self.forces.nodes.pop(node_id)

        self.clear_mesh()

        return True
    
    def move_node(self, target_node:int, x, y):
        """
        Update coords of a specific node
        """
        if target_node not in self.nodes:
            # there should be no case where an unexisting node is moved
            # raise error to catch potential problems
            raise Exception("No node to move")
        
        self.nodes[target_node].x = x
        self.nodes[target_node].y = y


    def add_edge(self, type:str, start_node_id:int, end_node_id:int, mid_node_id:int|None = None, boundary_group:str = "external") -> int:
        
        self._edge_counter += 1

        new_edge = Edge(
            type, 
            start_node_id,
            end_node_id,
            mid_node_id,
            boundary_group=boundary_group
        )

        self.edges[self._edge_counter] = new_edge

        return self._edge_counter
    
    def delete_edge(self, target: int | tuple[int, int] | None = None) -> bool:
        if target is None: 
            if not self.edges:
                return False
            target = max(self.edges.keys())
        
        if not isinstance(target, int):
            target = self.get_edge_id_by_nodes(*target)

        if target in self.edges:
            # delete supports in edge
            if target in self.supports.edges:
                self.supports.edges.pop(target)
            
            # delete forces in edge
            if target in self.forces.edges:
                self.forces.edges.pop(target)

            self.edges.pop(target)

            self.clear_mesh()

            return True
        return False
    
    def split_edge(self, target: tuple[int, int], num_segments: int) -> bool:
        # get edge
        edge_id = self.get_edge_id_by_nodes(*target)

        if edge_id not in self.edges or self.edge_has_force(target) or self.edge_has_support(target):
            return False

        original_edge = self.edges[edge_id]
        start_node = self.nodes[original_edge.start_node]
        end_node = self.nodes[original_edge.end_node]
        edge_type = original_edge.type

        # 1. Calculate Intermediate Coordinates
        # If it's a curve, we need 2x the segments to get the mid_nodes
        math_segments = num_segments * 2 if edge_type != "linear" else num_segments
        
        internal_points = []
        
        if edge_type == "linear":
            dx = (end_node.x - start_node.x) / math_segments
            dy = (end_node.y - start_node.y) / math_segments
            for i in range(1, math_segments):
                internal_points.append((start_node.x + i * dx, start_node.y + i * dy))
        else:
            assert isinstance(original_edge.mid_node, int)
            mid_node = self.nodes[original_edge.mid_node]
            
            if edge_type == "parabola":
                pts, _ = CurveHelper.calculate_parabola_points(
                    start_node.as_tuple(), end_node.as_tuple(), mid_node.as_tuple(), segments=math_segments
                )
            elif edge_type == "circle":
                pts, _ = CurveHelper.calculate_circle_points(
                    start_node.as_tuple(), end_node.as_tuple(), mid_node.as_tuple(), segments=math_segments
                )
            
            # Strip the original start and end coordinates
            internal_points = pts[1:-1]

        # 2. Generate New Nodes
        new_node_ids = []
        for x, y in internal_points:
            new_node_ids.append(self.add_node(x, y))
            
        # Combine into one full sequential chain: [Start] + [New Nodes] + [End]
        full_chain = [original_edge.start_node] + new_node_ids + [original_edge.end_node]

        # 3. Create the Sub-Edges
        if edge_type == "linear":
            for i in range(num_segments):
                self.add_edge(
                    start_node_id=full_chain[i],
                    end_node_id=full_chain[i+1],
                    type="linear",
                    boundary_group=original_edge.boundary_group
                )
        else:
            # For curves, we jump by 2. 
            # Segment 1: start=0, mid=1, end=2
            # Segment 2: start=2, mid=3, end=4
            for i in range(num_segments):
                idx = i * 2 
                self.add_edge(
                    start_node_id=full_chain[idx],
                    end_node_id=full_chain[idx+2],
                    mid_node_id=full_chain[idx+1],
                    type=edge_type,
                    boundary_group=original_edge.boundary_group
                )

        # 4. Cleanup
        if edge_type != "linear" and original_edge.mid_node:
            if original_edge.mid_node in self.nodes:
                self.delete_node(original_edge.mid_node) # also deletes original edge
        else:
            self.delete_edge(edge_id)

        return True

    def is_point_inside_CST(self, x:float, y:float) -> None | int:
        """
        Loops through CST's in results, if found, returns that CST
        """
        if not self.mesh or not self.mesh.triangles:
            return None

        # Helper to calculate the 2D cross product
        def sign(p1x, p1y, p2x, p2y, p3x, p3y):
            return (p1x - p3x) * (p2y - p3y) - (p2x - p3x) * (p1y - p3y)
        
        nodes = self.mesh.solver_nodes

        for i, (n1, n2, n3) in enumerate(self.mesh.triangles):
            # Fetch coordinates
            x1, y1 = nodes[n1].x, nodes[n1].y
            x2, y2 = nodes[n2].x, nodes[n2].y
            x3, y3 = nodes[n3].x, nodes[n3].y

            # Check the point against all three edges
            d1 = sign(x, y, x1, y1, x2, y2)
            d2 = sign(x, y, x2, y2, x3, y3)
            d3 = sign(x, y, x3, y3, x1, y1)

            has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
            has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)

            # If the point is strictly on one side of all edges, it's inside
            if not (has_neg and has_pos):
                return i  # Return the index of the matched triangle

        return None

    def get_edge_id_by_nodes(self, n1_id: int, n2_id: int) -> int | None:
        """Helper method: Finds an edge ID that shares the two given nodes."""
        for edge_id, edge in self.edges.items():
            edge_nodes = edge.list_node_ids()
            if n1_id in edge_nodes and n2_id in edge_nodes:
                return edge_id
        return None

    def add_support(self, target:int|tuple[int, int], support:str) -> bool:
        """
        Alters self.supports
            nodes: if int, adds support to a that specific node
                    else, adds to edge that composes that node
            support: str may obtain "x" "y" "z", not exclusively
        """
        from_node = isinstance(target, int)
        
        if not (
            bool(support) and set(support) <= {"x", "y", "z"} and len(support) == len(set(support))
        ): 
            raise ValueError("A support string may only be composed of x, y and z!")
        
        if from_node:
            if target not in self.nodes: return False # node does not exist
            
            self.supports.nodes[target] = support
            return True
        
        if any(node not in self.nodes for node in target): return False
        
        edge_id = self.get_edge_id_by_nodes(*target)

        if edge_id:
            self.supports.edges[edge_id] = support
            return True
        return False
        
    def delete_support(self, target:int|tuple[int, int]|None) -> bool:
        """
        Alters self.supports, by removing a given item
            nodes: if int, remover support of a that specific node
                    else, removes from the edge that composes that node
        """
        if target is None: return False

        from_node = isinstance(target, int)
        
        if from_node:
            if target not in self.nodes or not self.node_has_support(target): return False  # node/support does not exist 
            
            self.supports.nodes.pop(target)
            return True
        
        if any(node not in self.nodes for node in target): return False
        
        edge_id = self.get_edge_id_by_nodes(*target)

        if edge_id and edge_id in self.supports.edges:
            self.supports.edges.pop(edge_id)
            return True
        return False
    
    def node_has_support(self, node_id:int) -> bool:
        return node_id in self.supports.nodes 

    def edge_has_support(self, node_ids:tuple[int, int]) -> bool:
        edge_id = self.get_edge_id_by_nodes(*node_ids)
        return edge_id in self.supports.edges
    
    def add_point_load(self, node_id: int, fx: float = 0.0, fy: float = 0.0, m: float = 0.0) -> bool:
        """
        Adds a point load to a node.
        """
        if node_id not in self.nodes:
            return False
        
        point_load = PointLoad(fx=fx, fy=fy, m=m)

        if not point_load: return False

        self.forces.nodes[node_id] = point_load
        return True

    def add_distributed_load(
        self,
        node_ids: tuple[int, int],
        magnitude: float,
        moment:float,
        direction_type: str = "normal",
        global_angle: float = 0.0,
        magnitude_end: float | None = None
    ):
        """
        Adds a distributed load to an edge.
        """

        if any(node not in self.nodes for node in node_ids):
            raise ValueError("Clicked node not defined!")

        edge_id = self.get_edge_id_by_nodes(*node_ids)

        if edge_id is None:
            raise ValueError("No edge is connected by these nodes!")

        def validate_direction(value: str) -> Literal['normal', 'global']:
            if value not in ('normal', 'global'):
                raise ValueError(f"direction_type must be 'normal' or 'global', got {value}")
            return value  
        
        self.forces.edges[edge_id] = DistributedLoad(
            magnitude=magnitude,
            moment=moment,
            direction_type=validate_direction(direction_type),
            global_angle=global_angle,
            magnitude_end=magnitude_end,
        )

    
    def node_has_point_load(self, node_id:int) -> bool:
        return node_id in self.forces.nodes
    
    def edge_has_distributed_load(self, node_ids:tuple[int, int]) -> bool:
        edge_id = self.get_edge_id_by_nodes(*node_ids)
        return edge_id in self.forces.edges
    
    def delete_force(self, target: int | tuple[int, int] | None) -> bool:
        """
        Removes a force from a node or edge.
        """
        if target is None:
            return False

        from_node = isinstance(target, int)

        if from_node:
            if target not in self.nodes or target not in self.forces.nodes:
                return False

            self.forces.nodes.pop(target)
            return True

        if any(node not in self.nodes for node in target):
            return False

        edge_id = self.get_edge_id_by_nodes(*target)

        if edge_id and edge_id in self.forces.edges:
            self.forces.edges.pop(edge_id)
            return True

        return False

    def node_has_force(self, node_id: int) -> bool:
        return node_id in self.forces.nodes

    def edge_has_force(self, node_ids: tuple[int, int]) -> bool:
        edge_id = self.get_edge_id_by_nodes(*node_ids)
        return edge_id in self.forces.edges

    def create_mesh(self, solver_nodes:dict[int, SolverNode], triangles:list[tuple[int, int, int]]):
        """
        Stores the generated mesh data.
        Overwrites previous mesh
        """
        self.mesh.solver_nodes = solver_nodes
        self.mesh.triangles = triangles

    def clear_mesh(self):
        
        self.mesh = Mesh({}, [])
        self.results = {}

    def as_json(self) -> dict[str, Any]:
        """Returns the entire model state as a dictionary."""
        return {
            "nodes": {str(k): v.as_json() for k, v in self.nodes.items()},
            "edges": {str(k): v.as_json() for k, v in self.edges.items()},
            "material": self.material.as_json(),
            #"mesh": self.mesh.as_json(), --> disabled for being kinda useless
            "supports": self.supports.as_json(),
            "forces": self.forces.as_json(),
            "counters": {"nodes": self._node_counter, "edges": self._edge_counter}
        }

    def load_from_json(self, data: dict[str, Any]):
        """Rebuilds the model state from a dictionary."""
        
        # Rebuild nodes/edges
        self.nodes = {int(k): Node(**v) for k, v in data.get("nodes", {}).items()}
        self.edges = {int(k): Edge(**v) for k, v in data.get("edges", {}).items()}
        
        # Rebuild sub-objects using their dedicated builders
        self.supports = Support.from_dict(data.get("supports", {}))
        self.forces = ForceManager.from_dict(data.get("forces", {}))

        self.material = Material(**data.get("material"))
        
        # Restore counters
        counters = data.get("counters", {"nodes": 0, "edges": 0})
        self._node_counter = counters.get("nodes", 0)
        self._edge_counter = counters.get("edges", 0)

    def solve_mesh(self, model_type: Literal["Beam", "Plane Strain", "Plane Stress"]) -> float:
        import subprocess
        import os
        from time import time
        
        before = time()
        
        if not self.mesh:
            raise Exception("Warning: No mesh exists. Cannot run solver.")

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        input_file = os.path.join(base_dir, "temp_model_in.json")
        output_file = os.path.join(base_dir, "temp_model_out.json")

        solver_payload = {
            "mesh": self.mesh.as_json(),
            "material": self.material.as_json()
        }

        with open(input_file, "w") as f:
            json.dump(solver_payload, f)
        
        script_name = "solver_beam.jl" if model_type == "Beam" else "solver_plane.jl"
        
        # Paths
        project_dir = os.path.join(base_dir, "solver")
        script_path = os.path.join(project_dir, script_name)
        

        try:
            # guarantee enviroment is instantiated
            subprocess.run(
                [
                    "julia", 
                    f"--project={project_dir}", 
                    "-e", 
                    "using Pkg; Pkg.instantiate()"
                ],
                capture_output=True,
                check=True
            )

            result = subprocess.run(
                [
                    "julia", 
                    f"--project={project_dir}", 
                    script_path, 
                    input_file, 
                    output_file,
                    model_type 
                ],
                capture_output=True,
                text=True,
                check=True
            )

            if result.stdout:
                print("Julia Output:\n", result.stdout)
            
            # Clean up input file
            if os.path.exists(input_file):
                os.remove(input_file)
            
            # Read results, clean up output file
            if os.path.exists(output_file):
                with open(output_file, "r") as f:
                    results = json.load(f)
                    self.results = results
                
                os.remove(output_file) 
                return time() - before
            else:
                self.results = {}
                return time() - before
                    
        except subprocess.CalledProcessError as e:
            print(f"Julia Solver Failed:\n{e.stderr}")
            self.results = {}
            raise Exception(f"Solver Error: {e.stderr}")
