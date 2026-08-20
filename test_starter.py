import sys
sys.path.insert(0, 'bots/starter')

from fcode import Position, Environment

# Simulate what happens
from mapclass import Map

# Test Map initialization
m = Map()
m.configure(64, 64, Position(1, 1))
print(f"Map configured: {m.configured}")
print(f"Map dimensions: {m.width}x{m.height}")

# Test unscouted frontier
frontier = m.get_unscouted_near(Position(2, 2))
print(f"Frontier from (2,2): {frontier}")
