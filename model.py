from dataclasses import dataclass, field
from typing import Dict, Optional, Literal
from math import hypot, atan2, degrees
from curve import CurveHelper
import json

@dataclass
class Node:
    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        """Returns the node's coordinates as a tuple."""
        return (self.x, self.y)
    
    def as_json(self) -> dict[str, float]:
        return {
            "x": self.x,
            "y": self.y,
        }


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
    
    def as_json(self) -> dict[str, str | int | None]:
        return {
            "type": self.type,
            "start_node": self.start_node,
            "end_node": self.end_node,
            "mid_node": self.mid_node,
            "boundary_group": self.boundary_group,
        }

@dataclass
class Support:
    # Maps ID -> Support String (e.g., {1: "xy", 4: "z"})
    nodes: Dict[int, str] = field(default_factory=dict)
    edges: Dict[int, str] = field(default_factory=dict)

    def __bool__(self):
        return bool(self.nodes) or bool(self.edges)
    
    def as_json(self) -> Dict[str, Dict[int, str]]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
        }

@dataclass
class PointLoad:
    fx: float = 0.0
    fy: float = 0.0
    m: float = 0.0

    def __bool__(self):
        return any([bool(i) for i in (self.fx, self.fy, self.m)])

    def as_polar(self) -> tuple[float, float]:
        """Returns (magnitude, angle_in_degrees)."""
        magn = hypot(self.fx, self.fy)
        theta_rad = atan2(self.fy, self.fx)
        theta_deg = degrees(theta_rad)
        
        return (magn, theta_deg)
    
    #def as_json(self) -> :
        

@dataclass
class DistributedLoad:
    magnitude: float
    moment:float
    direction_type: Literal["normal", "global"] = "normal" 

    # Only used if direction_type is "global"
    global_angle: float = 0.0 

@dataclass
class ForceManager:
    nodes: Dict[int, PointLoad] = field(default_factory=dict)
    edges: Dict[int, DistributedLoad] = field(default_factory=dict)

@dataclass
class Mesh:
    nodes: list[tuple[float, float]]
    triangles: list[tuple[int, int, int]]

    def __bool__(self):
        return bool(self.nodes) or bool(self.triangles)

class FEMModel:

    def __init__(self):
        self.nodes:Dict[int, Node] = {}
        self.edges:Dict[int, Edge] = {}
        self.mesh:Mesh = Mesh([], [])
        self.supports:Support = Support()
        self.forces:ForceManager = ForceManager()

        # for deletion memory
        self._node_counter = 0
        self._edge_counter = 0


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
    ) -> bool:
        """
        Adds a distributed load to an edge.
        """
        if direction_type not in {"normal", "global"}:
            raise ValueError("direction_type must be 'normal' or 'global'.")

        if any(node not in self.nodes for node in node_ids):
            return False

        edge_id = self.get_edge_id_by_nodes(*node_ids)

        if edge_id is None:
            return False

        self.forces.edges[edge_id] = DistributedLoad(
            magnitude=magnitude,
            moment=moment,
            direction_type=direction_type,
            global_angle=global_angle,
        )

        return True
    
    def node_has_point_load(self, node_id:int) -> bool:
        return node_id in self.forces.nodes
    
    def edge_has_distributed_load(self, node_ids:tuple[float, float]) -> bool:
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

    def create_mesh(self, nodes:list[tuple[float, float]], triangles:list[tuple[int, int, int]]):
        """
        Stores the generated mesh data.
        Overwrites previous mesh
        """
        self.mesh.nodes = nodes
        self.mesh.triangles = triangles

    def clear_mesh(self): self.mesh = Mesh(nodes=[], triangles=[])

    def as_json(self, file_name: str):
        data = {
            "nodes": {
                str(nid): node.as_json() for nid, node in self.nodes.items()
            }
        }
        with open(file_name, "w") as fp:
            json.dump(data, fp, indent=4)



