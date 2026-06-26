using JSON

data = JSON.parsefile(ARGS[1])

E = data["material"]["E"]
nu = data["material"]["nu"]

# Extract Mesh Data
nodes = data["mesh"]["solver_nodes"]
elements = data["mesh"]["triangles"] 

println(nodes)
println(elements)