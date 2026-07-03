module PlaneSolver

using JSON
using LinearAlgebra
using SparseArrays 

# Define Data Structures 
# ==========================================

struct Material
    E::Float64
    nu::Float64
    gamma::Float64
end

struct Node
    id::Int
    x::Float64
    y::Float64
    support::Union{String, Nothing}
    fx::Float64
    fy::Float64
end

struct Element
    n1::Int
    n2::Int
    n3::Int
end


function parse_input(filepath::String)
    data = JSON.parsefile(filepath)
    
    # Parse Material
    mat_data = data["material"]
    mat = Material(mat_data["E"], mat_data["nu"], mat_data["gamma"])
    
    nodes = Dict{Int, Node}()
    for (id_str, n_data) in data["mesh"]["solver_nodes"]
        id = parse(Int, id_str) + 1 # Shift Python's 0-index to Julia's 1-index
        nodes[id] = Node(
            id, n_data["x"], n_data["y"], 
            n_data["support"], n_data["fx"], n_data["fy"]
        )
    end
    
    # 3. Parse Elements
    elements = Element[]
    for e in data["mesh"]["triangles"]
        # Shift indices by +1 here as well
        push!(elements, Element(e[1]+1, e[2]+1, e[3]+1)) 
    end
    
    return mat, nodes, elements
end

struct PlaneStrain end
struct PlaneStress end

function get_D(model::PlaneStress, mat::Material)
    E = mat.E
    nu = mat.nu
    
    coeff = E / (1 - nu^2)
    return coeff * [
        (1 - nu)     nu          0;
        nu           (1 - nu)    0;
        0            0           (1 - nu) / 2
    ]
end

function get_D(model::PlaneStrain, mat::Material)
    E = mat.E
    nu = mat.nu
    
    coeff = E / ((1 + nu) * (1 - 2 * nu))
    return coeff * [
        (1 - nu)     nu          0;
        nu           (1 - nu)    0;
        0            0           (1 - 2 * nu) / 2
    ]
end

function Jacobian_3_node_triangle(C::Matrix{Float64})
    dNdξ = [
        -1 -1;
         1  0;
         0  1;
    ]

    return C' * dNdξ
end

function get_B_matrix_3_node_triangle(C::Matrix{Float64})
    # Shape function derivatives w.r.t. natural coordinates (xi, eta)
    dNdξ = [
        -1 -1; # dN1/dxi, dN1/deta
         1  0; # dN2/dxi, dN2/deta
         0  1  # dN3/dxi, dN3/deta
    ]

    # For linear triangles, J = C' * dNdξ
    J = Jacobian_3_node_triangle(C)
    
    # Invert the Jacobian
    J_inv = inv(J)
    
    dN_dxdy = dNdξ * J_inv
    
    # Pre-allocate the 3x6 B matrix
    B = zeros(3, 6)
    
    # Fill the B matrix
    for i in 1:3
        dNdx = dN_dxdy[i, 1]
        dNdy = dN_dxdy[i, 2]
        
        col = (i - 1) * 2 + 1
        
        B[1, col]     = dNdx
        B[2, col + 1] = dNdy
        B[3, col]     = dNdy
        B[3, col + 1] = dNdx
    end
    
    return B
end

function get_element_stiffness(
    model::Union{PlaneStrain, PlaneStress},
    elem::Element,
    nodes::Dict{Int, Node},
    material::Material,
)
    # get coordinates for n1, n2, n3
    C = [
    nodes[elem.n1].x nodes[elem.n1].y;
    nodes[elem.n2].x nodes[elem.n2].y;
    nodes[elem.n3].x nodes[elem.n3].y;
    ]

    # Calculate Area 
    A = abs(det(Jacobian_3_node_triangle(C))) / 2

    # Build the B matrix (Strain-Displacement)
    B = get_B_matrix_3_node_triangle(C)

    # define D
    D = get_D(model, material)

    # Return K_e = transpose(B) * D * B * Area
    return B' * D * B * A # (Thickness 'h' is assumed to be 1.0 for standard plane strain)

end

function get_element_stresses(
    model::Union{PlaneStrain, PlaneStress},
    U::Vector{Float64},
    elem::Element,
    material::Material,
    nodes::Dict{Int, Node},
)
    # Define coordinates
    C = [
    nodes[elem.n1].x nodes[elem.n1].y;
    nodes[elem.n2].x nodes[elem.n2].y;
    nodes[elem.n3].x nodes[elem.n3].y;
    ]

    # Define B matrix
    B = get_B_matrix_3_node_triangle(C)

    # get displacements of elem
    # Note: only valid for 3-node triangles
    node_ids = [elem.n1, elem.n2, elem.n3]
    U_e = zeros(6)
    
    for (i, nid) in enumerate(node_ids)
        idx_x = 2 * nid - 1
        idx_y = 2 * nid
        
        
        U_e[2*i - 1] = U[idx_x]
        U_e[2*i]     = U[idx_y]
    end

    # Calculate Strain: ε = B * U_e
    ε = B * U_e

    # Calculate Stress: σ = D * ε
    D = get_D(model, material)
    σ = D * ε

    return σ
end

function get_dofs_for_element(elem::Element)    
    # Node 1
    dof1_x = 2 * elem.n1 - 1
    dof1_y = 2 * elem.n1
    
    # Node 2
    dof2_x = 2 * elem.n2 - 1
    dof2_y = 2 * elem.n2
    
    # Node 3
    dof3_x = 2 * elem.n3 - 1
    dof3_y = 2 * elem.n3
    
    # Return a flat vector of length 6
    return [dof1_x, dof1_y, dof2_x, dof2_y, dof3_x, dof3_y]
end


function apply_bcs!(K::SparseMatrixCSC{Float64, Int}, F::Vector{Float64}, nodes::Dict{Int, Node})
    for (id, node) in nodes
        # If the node has a support string (e.g., "x", "y", or "xy")
        if node.support !== nothing
            dofs_to_fix = Int[]
            
            # Check for X support
            if occursin("x", lowercase(node.support))
                push!(dofs_to_fix, 2 * id - 1)
            end
            
            # Check for Y support
            if occursin("y", lowercase(node.support))
                push!(dofs_to_fix, 2 * id)
            end
            
            # Apply the mathematical boundary condition
            for dof in dofs_to_fix
                # Zero out the row and column
                K[dof, :] .= 0.0
                K[:, dof] .= 0.0
                
                # Set diagonal to 1.0
                K[dof, dof] = 1.0
                
                # Set force to 0.0
                F[dof] = 0.0
            end
        end
    end
end

function assemble_system(model::Union{PlaneStrain, PlaneStress}, mat::Material, nodes::Dict{Int, Node}, elements::Vector{Element})
    num_nodes = length(nodes)
    ndofs = 2 * num_nodes

    # Initialize mapper arrays
    I = Int[]
    J = Int[]
    V = Float64[]

    F = zeros(ndofs)

    D = get_D(model, mat)

    for elem in elements

        K_e = get_element_stiffness(model, elem, nodes, mat)

        dofs = get_dofs_for_element(elem)

        for r in 1:6
            for c in 1:6
                row_idx = dofs[r]
                col_idx = dofs[c]

                push!(I, row_idx)
                push!(J, col_idx)
                push!(V, K_e[r, c])
            end
        end
    end

    K_global = sparse(I, J, V, ndofs, ndofs)

    # NOTE
    # payload has moments on nodes, but both plane strain/stress
    # will not consider. Those values will only be used for beam models
    # Apply forces and supports
    for (id, node) in nodes
        F[2*id - 1] += node.fx
        F[2*id]     += node.fy
    end

    return K_global, F
end

function run_solver(filepath::String, model::Union{PlaneStrain, PlaneStress})
    # Parse input
    mat, nodes, elems = parse_input(filepath)

    # Assembly of stiffness matrix and force vector
    K, F = assemble_system(model, mat, nodes, elems)

    # Define copies for linear system
    K_sys, F_sys = copy(K), copy(F)
    apply_bcs!(K_sys,F_sys, nodes)

    # solve linear system
    U = K_sys \ F_sys

    return U, K, F
    
end

end # End of Module

# ==========================================
# COMMAND LINE EXECUTION ENTRY POINT
# ==========================================
# This block only runs when the script is called directly from Python/Terminal
if abspath(PROGRAM_FILE) == @__FILE__
    using .PlaneSolver
    using JSON

    try
        input_file = ARGS[1]
        output_file = ARGS[2]
        model_type_str = ARGS[3] 

        # Instantiate the correct physics model based on the string
        if model_type_str == "Plane Strain"
            physics_model = PlaneSolver.PlaneStrain()
        elseif model_type_str == "Plane Stress"
            physics_model = PlaneSolver.PlaneStress()
        else
            error("Unknown model type passed to Julia: $model_type_str")
        end

        # Trigger the solver using the dynamic model
        U, K, F = PlaneSolver.run_solver(input_file, physics_model)

        # Calculate Reactions
        R = K * U - F

        # Calculate stresses
        S = get_element_stresses()

        open(output_file, "w") do f
            JSON.print(f, Dict(
                "status" => "success", 
                "displacements" => U,
                "reactions" => R,
                "stresses" => S,
            ))
        end
        
    catch e
        println(stderr, "Julia Execution Error: ", e)
        exit(1)
    end
end