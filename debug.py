from model import *
from mesh import *
from curve import CurveHelper
import json
from dataclasses import asdict

m = FEMModel()

m.load_from_json(json.load(open("test.json", "r", encoding="utf-8")))

mesh = MeshEngine(m, CurveHelper)

snodes, tri = mesh.generate_mesh(1)

print(type(snodes)); exit()

for k, v in snodes.items():
    if any({v.fx, v.fy, v.m, v.support}):
        print(k, asdict(v))