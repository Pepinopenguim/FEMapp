#import "@preview/fletcher:0.5.8"
#import fletcher: diagram, node, edge
#import fletcher.shapes: diamond, hexagon
#set page(
  paper: "a4",
  margin: 2.5cm,
)

#set text(
  font: "Libertinus Serif",
  size: 12pt,
)

#set heading(
  numbering: "1.1.a",
  hanging-indent: 2cm
  )

#align(center)[
  #grid(
    columns: (auto, auto),
    image("unblogo.png", height: 5cm),
    image("cast.svg", height: 5cm)
  )

  #v(1cm)

  #text([Software CaST], size: 60pt, weight: "bold")

  A (somewhat) minimalist Software for the solution of 2D-Elastic FEM problems 

  #v(2cm)

  *Author:* Vítor Luís Costa Azevedo

  *Course:* Introdução ao Método dos Elementos Finitos

  *Professor:* DURAND, Raul

  *Date:* #datetime.today().display()
]

#pagebreak()

#outline()

#pagebreak()

= Introduction

The development of *CaST* started as a project for the subject "Introdução ao Método dos Elementos Finitos" (_Introduction to the Finite Element Method_) at the university of Brasília.

As an open source software, it aims to present a minimalist UI for defining and calculating 2D solid and elastic elements, specifically *Constant Strain Triangles (CSTs)* which name the app. Its UI is defined in pure python, through the MVC (Model-View-Controller) architecture, purely based on the library _Tkinter_, and presents a certain easiness to be expanded into more complex calculations.

Currently, the Software supports the drawing of 2D elements via lines, circles and isoparametric 2nd degree parabolas. Supports and forces may be applied in geometric nodes and edges, in which forces, when applied to edges, can be defined as "normal" (pressure like) or "global", constant or trapezoidal.

The software also supports the saving and loading of designs, and visualization, through simple heatmaps, of stress, forces and displacements on elements.

= Architecture

The MVC architecture, as described, was used in the making of the program. It was chosen, specially, because its set of rules define a workflow that avoids the creation of _Spaghetti_ code, and facilitates the adding of new features.

In the MVC architecture, each section of code has a specific purpose, and those purposes are different. Some classes may hold the data of the app, while others only define UI elements (View), while other classes control the communication between these two (Controller).

_Python_, one of the most versitile and friendly programming languages, presents itself as a great choice for the _Frontend_ of the app, specially because of its Object Oriented workflow, it simplifies a lot of the complex data being thrown around the app. The _Backend_ is defined in both Python and Julia. Specifically, Python stores the data, and julia, the creation of the linear system.

#figure(
  align(center)[
    #diagram(
      node-stroke: 1pt,
      node-corner-radius: 4pt,
      
      // VIEW (UI)
      node((0, 0), align(center)[
        *MainView* \ 
        _Tkinter UI & Canvas_ \
        Draws nodes, edges, heatmaps
      ], fill: rgb("4facf7").lighten(50%)),
      
      // CONTROLLER (LOGIC)
      node((2, 0), align(center)[
        *MainController* \ 
        _Core Logic_ \
        Handles interaction \ between canvas and data
      ], fill: rgb("f7c94f").lighten(50%)),
      
      // MODEL (STATE)
      node((2, 3), align(center)[
        *FEMModel* \ 
        _Data Structures_ \
        Stores mesh, forces, materials
      ], fill: rgb("4ff773").lighten(50%)),
      
      // JULIA SOLVER (EXTERNAL)
      node((0, 3), align(center)[
        *Julia Engine* \ 
        _solver_plane.jl_ \
        Matrix assembly & physics
      ], shape: hexagon, fill: rgb("f74f4f").lighten(50%)),
      
      // --- CONNECTIONS ---
      
      // View <- Controller
      edge((0, 0), (2, 0), "-|", [User Inputs\ & Events], bend: -15deg),
      edge((2, 0), (0, 0), "-|", [Render Data\ & Hover Boxes], bend: -15deg),
      
      // Controller <- Model
      edge((2, 0), (2, 3), "-|", [Commit Geometry\ & Forces], bend: -15deg),
      edge((2, 3), (2, 0), "-|", [App State\ & Results], bend: -15deg),
      
      // Model <- Solver
      edge((2, 3), (0, 3), "-|", [Write `temp_model_in.json` \ `subprocess.run()`], bend: -15deg),
      edge((0, 3), (2, 3), "-|", [Read `temp_model_out.json`], bend: -15deg),
    )
  ],
  caption: "Flowchart of the app"
)

= CaST Workflow

== Definition of Geometry
The first step of any FEM software is to define the geometry of the problem, not the mesh in itself, but the components that determine the format, material, and boundaries of the object.

In *CaST*, the user must firstly define *Nodes*, that store position along the space and will be connected via *Edges*. To define a node, one can either left click on the wanted position with the mouse (adjusting snap precision scrolling while holding shift) or type the coordinates manually (this, of course, ignores snap altogether).
With the nodes placed, the user must connect 2 or 3 of them with the *Edge* tool. *CaST* supports linear, parabolic (isoparametric) and circular edges. Simply clicking in the order [start, end, middle] will define an edge. To define a whole, just change the boundary option above the canvas to a new hole.

#figure(
  image("curves.png", width: 80%),
  caption: [Definition of an object with linear, parabolic and circular edges, along with a linear hole. #text("(Options menu, defined in green)", fill: green)]
)

== Adding of Supports and Forces

To define boundary conditions, user must click the respective node, if in node mode, or two nodes of a given edge, in edge mode. User may change displacement restrictions on the upper menu.

#figure(
  image("supports.png", width: 80%),
  caption: [A rectangular object defined with supports at nodes (lower nodes) and edges (upper edge)]
)

Similarly, for forces, they can be applied on nodes or edges. Edges can have "normal" (perpendicular to the element) and "global" (global coordinate system). Trapezoidal loads can be defined by differentiating start and end loads.

#figure(
  grid(
    columns:range(2).map(_ => auto),
    image("pload.png", width: 95%),
    image("dload.png", width: 95%),
  ),
  caption: [Definition of (a): Point force on node, (b): normal {left} and global trapezoidal load {right}]
)
== Material

The material consists of $E$ (Young's module), $nu$ (Poisson's ratio) and $gamma$ (Own Weight, on force per volume). On the material setting, user may also define the width of the object even though it's technically not a material property.

== Meshing Engine

In Mesh mode, a simple scale defines the expected size of an element, to be updated on the mesh engine. Smaller elements tend to lag out the software, due to it redrawing every element on every frame. 

Mesh mode also defines the analysis to be made, _Plane Stress_ and _Plane Strain_ (which changes specifically the $D$ matrix, though more analysis are possible to be added). 

#figure(
  image(
    "mesh.png", width: 80%
  ),
  caption: [Mesh define for an element to be solved in Plane Strain]
)

To solve complex geometries, the continuous physical domain must be discretized into a finite network of elements. While simple domains can be meshed manually, arbitrary geometries—especially those containing curves, parabolas, or internal holes—require specialized algorithmic generation.
 Tools like *Gmsh* (an open-source 3D finite element mesh generator) handle this discretization process. The meshing pipeline generally follows a strict topological hierarchy:
 - *Points:* The absolute bounds of the model.
 - *Curves:* Lines or arcs connecting the points to form wireframes.
 - *Surfaces:* Closed boundaries formed by the curves, defining the actual solid material domain.

The below script (@meshing) defines a pseudo-code that represents how the geometric CaST definitions are converted into useful FEM data, defining the mesh, and calculates the equivalent nodal forces and applies supports. *SolverNodes* is a dataclass that not only store its own coordinates, but support and force being applied.


#pagebreak()

#figure(

block(
  fill: rgb("#fafafa"),     
  stroke: rgb("#e0e0e0"),  
  inset: 15pt,            
  radius: 5pt,            
  width: 100%,            
  [
    #set text(size: 10pt)
    ```python
    MeshEngine(mesh_size)
      gmsh.initialize()
      
      # ---- DEFINE GEOMETRY ----
      for node in model.nodes:
        add node to gmsh
        define a tag for it
        
      for edge in model.edges:
        get its type (external or hole)
        if line:
          create straight line in gmsh between start and end node
        if parabola or circle:
          calculate intermediate points along the curve
          add these interpolated points as nodes in gmsh
          create a spline connecting start -> intermediate points -> end
          
      # ---- DEFINE BOUNDARIES & SURFACE ----
      for each boundary_group (external and holes):
        sort curves head-to-tail to form a closed, continuous loop
        create a CurveLoop in gmsh
        
      create a 2D PlaneSurface (using the external loop as the boundary, minus the hole loops)
      
      # ---- MESH GENERATION ----
      generate 2D mesh!
      
      # ---- EXTRACT MESH DATA ----
      get all generated triangles and their associated node tags
      find only the "active" nodes (ignore unused points, like the center of a circle)
      create a new 0-based index for these active nodes (so the Julia solver gets a clean array)
      
      # ---- MAP BOUNDARY CONDITIONS ----
      for each gmsh edge:
        find the actual mesh nodes generated along this specific edge
        apply edge supports to these nodes
        if edge has distributed load:
          split load across the edges mesh segments (trapezoidal integration)
          convert to X/Y directions and apply to the nodes
          
      for each base node:
        apply point supports and point loads directly to their matching gmsh node
        
      # ---- PACKAGE FOR SOLVER ----
      for each active node:
        create a SolverNode containing (x, y, support, fx, fy, moment)
        
      gmsh.finalize()
      
      return SolverNodes, Triangles
    ```
  ]
),
caption: [Representative script that converts geometric values into useful data for building the linear system.]
) <meshing>

 Once the surface is defined, the meshing engine applies algorithms (such as Delaunay triangulation or advancing front methods) to pack the surface with non-overlapping triangles. A critical feature of advanced meshing is localized refinement . The engine automatically generates smaller, denser triangles around areas of high geometric complexity (like sharp corners, holes, or applied point loads) to capture rapid stress concentrations accurately. Conversely, it leaves larger elements in uniform, unconstrained regions to reduce the total degrees of freedom, optimizing the computational speed of the linear solver.

To press the solve button on the top UI invokes the _Julia Engine_ and sends the user to the analysis of results, which will be covered in @results.

== CST Elements

The core geometric building block of the solver is the Constant Strain Triangle (CST), a 3-node, 6-degree-of-freedom element. The fundamental advantage of the CST lies in its linear displacement field. For any point inside the element, the displacements $u_x$ and $u_y$ are interpolated from the nodal displacements using linear shape functions:
 
$
  u_x = N_1 (x, y) u_x_1 + N_2 (x, y) u_x_2  + N_3 (x) u_x_3 
$

 
$
  u_y = N_1 (x, y) u_y_1 + N_2 (x, y) u_y_2  + N_3 (x) u_y_3 
$

Which implies that $u(x,y)$ is linear.
Because strain is defined as the first spatial derivative of displacement (e.g., $epsilon_x = (partial u) / (partial x)$), taking the derivative of a linear function yields a constant:
 
 $
 epsilon = "cte"
$
 
 This mathematical property guarantees that the strain—and consequently, the stress—does not vary across the element's internal domain.
 Computationally, this is a massive advantage. Defining the element stiffness matrix $K_e$ requires integrating the material properties over the element's volume:
 $
   K_e = integral_V B^T D B d V
 $

 
 
 Because the strain-displacement matrix $B$ is entirely constant for a CST, given the Jacobian $J$ is too contant, it can be pulled outside of the integral. The calculation collapses from a complex numerical integration into a direct algebraic product involving the material's elasticity matrix $D$ and the triangle's area $A$:
 
$
  K_e = B^T D B A h
$
 
 
 (where $h$ is the element thickness). This eliminates the need for expensive numerical integration techniques, like Gaussian quadrature. As a result, the assembly of the global stiffness matrix in the backend becomes incredibly fast and memory-efficient, specially with the use of julia and its _SparseArrays_ library.

 Furthermore, the geometric simplicity of the CST easily translates to the application's physical parameters and interactive UI. Body forces, such as the specific weight of a material, can be perfectly distributed as three equal nodal loads calculated directly from the area. 



= Example Results <results>

For the comparison of results of CaST and other FEM softwares, we will use the example set in the image below, from this subjects's textbook. The material has the following properties, for values in $f, u$:

$
  E = 216 dot 10 ^ 9 (f)/(u^2) \
  nu = 0.3 \
  h = 0.005 " u" \
  q = 50 dot 10 ^ 6 dot 5 dot 10 ^-3 = #{50 * 1e6 * 5 * 1e-3} f/u
$

#figure(
  image("example.png", width: 70%),
  caption: [Symmetric plate to be solved]
) <examp>

Applying symmetry, the plate in @examp is drawn in CaST.

#figure(
  image(
    "example_cast.png",
    width: 80%
  ),
  caption: [Example drawn at CaST]
)

After pressing the solve button, the following result, for average displacements, appears. Although the computational time was of about 11.22 seconds, about 6-8 seconds are exclusively due to 

#figure(
  image("res_avg.png", width: 80%),
  caption: [Results for average displacement]
)

The figure shows a heatmap of average displacements, along with a scaled representation of displacements, to be changed with the slides above. Hovering the mouse shows the information on that current element. 

#let h = 9cm
#figure(
  grid(
    columns: range(3).map(_=>auto),
    image("res_dx.png", height: h, ),
    pad([], left: 5pt),
    image("res_dy.png", height: h),
  ),
  caption: [displacement heatmaps for x and y, respectively]
) <res_d>

#figure(
  image("res_book_disp.png"),
  caption: [Solution as defined by the textbook, for displacements and x and y, respectively]
) <res_book_d>

As we can see from @res_d and @res_book_d, displacement in the y direction and the top-left corner is about $0.020 m m$ 

= Conclusion

Summarize the work, emphasizing the main contributions and findings.

Discuss future work, possible improvements, or final remarks.

#pagebreak()

= References

- Reference 1
- Reference 2
- Reference 3




