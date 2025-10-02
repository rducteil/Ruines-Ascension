from core.data_loader import load_attacks, load_enemy_blueprints
atk = load_attacks()
mobs = load_enemy_blueprints(atk)
print("attacks:", len(atk), "enemies:", len(mobs))
print("sample enemy:", next(iter(mobs.values())).name)
from core.data_loader import load_encounter_tables
enc = load_encounter_tables()
print("zones:", list(enc.keys()))
print("RUINS normals:", enc["RUINS"]["normal"])
from core.data_loader import load_items
items = load_items()
print("items factories:", len(items), "sample:", next(iter(items.keys())))
from core.data_loader import load_equipment_banks
W,A,R = load_equipment_banks()
print("W/A/R:", len(W), len(A), len(R))
print("weapon sample:", getattr(W[0],'name',None), "tier", getattr(W[0],'tier',None))


