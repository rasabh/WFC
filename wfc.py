"""
Grid Def Component
Defining : Cell Class and Grid and Entropy and Tiles Classes
"""
import Rhino.Geometry as rg
import random
from collections import deque
import ast

#tiles rules (TR INPUT)___________________________________________________
#we have a dictionary of ID(index) and Rules of each tile
tiles_rules = {}
#"enumerate" seperates index and every value of a list
for i, tile_sockets_gh in enumerate(TR):
    tile_sockets = ast.literal_eval(tile_sockets_gh)
    tiles_rules[i] = tile_sockets

#defining Tile Class
class Tile:
    def __init__(self, id, sockets, geometry_data = None):
        self.id = id
        self.sockets = sockets # [top, right, bottom, left]
        self.geometry_data = geometry_data # e.g., a Brep, a list of lines, etc.
    
    def get_socket(self, direction): #0: top, 1: right, 2: bottom, 3: left
        return self.sockets[direction]


def check_match(socket1, socket2):
    return socket1 == socket2

#defining Cell Class
class Cell:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.collapsed = False
        #at first every cell has all of options
        self.options = list(tiles_rules.keys())

    def entropy(self):
        if self.collapsed:
            return 0
        if len(self.options) == 0:
            return -1   #in case of contradiction
        return len(self.options)

#initial Setup___________________________________________________
x_size = x_size  #input
y_size = y_size  #input
num_tiles = len(tiles_rules)
all_tiles = []
for tile_id, sockets in tiles_rules.items():
    all_tiles.append(Tile(tile_id, sockets))

#constructing 2D grid___________________________________________________
grid = []
for y in range(y_size):
    row = []
    for x in range(x_size):
        row.append(Cell(x, y))
    grid.append(row)


#step 01: first Collapse________________________________________
def get_min_entropy_cell(grid, x_size, y_size):
    min_entropy = float('inf')
    candidates = []
    for row in grid:
        for cell in row:
            if not cell.collapsed:
                e = cell.entropy()
                if e <= 0:      #in case of contradiction
                    continue
                if e < min_entropy:
                    min_entropy = e
                    candidates = [cell]
                elif e == min_entropy:
                    candidates.append(cell)
    
    return random.choice(candidates) if candidates else None

def collapse(cell):
    if not cell.options:
        return False #contradiction 
    chosen = random.choice(cell.options)
    cell.options = [chosen]
    cell.collapsed = True

    return True


#Propagate______________________________________________________
OPPOSITE = {'right': 'left', 'left': 'right', 'up': 'down', 'down': 'up'}
DIR_INDEX = {'up': 0, 'right': 1, 'down': 2, 'left': 3}

def get_neighbors(grid, cell, x_size, y_size):
    neighbors = []
    x, y = cell.x, cell.y
    if x > 0:               neighbors.append((grid[y][x-1], 'left'))   # added as a tuple like: (<Cell object>, 'left')
    if x < x_size - 1:      neighbors.append((grid[y][x+1], 'right'))
    if y > 0:               neighbors.append((grid[y-1][x], 'down'))
    if y < y_size - 1:      neighbors.append((grid[y+1][x], 'up'))
    return neighbors

def propagate(grid, start_cell, x_size, y_size):
    queue = deque([start_cell])

    while  queue:
        cell = queue.popleft()    #it's a better way of doing pop(0)
        
        for neighbor, direction in get_neighbors(grid, cell, x_size, y_size):
            if neighbor. collapsed:   
                continue                #if a neighbor is collapsed we skip it
            
            my_dir_idx = DIR_INDEX[direction]
            opp_dir_idx = DIR_INDEX[OPPOSITE[direction]]

            #این سلول در این سمت چه نوع سوکت‌هایی قبول می‌کنه؟
            #از بین گزینه‌های سلول فعلی، همه سوکت‌هایی که در این جهت دارن رو جمع می‌کنیم.
            valid_sockets = set(
                all_tiles[opt].sockets[my_dir_idx] for opt in cell.options
            )
            #«همسایه فقط می‌تونه کاشی‌هایی باشه که بهم وصل می‌شن.»
            new_options = [
                opt for opt in neighbor.options
                if all_tiles[opt].sockets[opp_dir_idx] in valid_sockets
            ]

            if len(new_options) < len(neighbor.options):
                neighbor.options = new_options
                if len(new_options) == 0:
                    print(f"Contradiction at neighbor X: {neighbor.x}, Y: {neighbor.y}")
                    print(f"Direction from cell ({cell.x}, {cell.y}) to neighbor: {direction}")
                    print(f"Valid sockets required by cell: {valid_sockets}")
                    return False
                queue.append(neighbor)
                
    return True

#Main Loop_________________________________________________________
max_attempts = 50

def build_fresh_grid(x_size, y_size):
    grid = []
    for y in range(y_size):
        row = []
        for x in range(x_size):
            row.append(Cell(x, y))
        grid.append(row)
    return grid

final_grid = None

for attempt in range(max_attempts):
    grid = build_fresh_grid(x_size, y_size)
    contradiction = False
    max_iterations = x_size * y_size
    iterations = 0

    while iterations < max_iterations:
        target = get_min_entropy_cell(grid, x_size, y_size)
        if target is None:
            break

        success = collapse(target)
        if not success:
            print(f"[Attempt {attempt+1}] Collapse failed at ({target.x},{target.y})")
            contradiction = True
            break

        chosen_tile_id = target.options[0]
        print(f"[Attempt {attempt+1}] Collapsed ({target.x},{target.y}) → Tile {chosen_tile_id}")

        prop_success = propagate(grid, target, x_size, y_size)
        if not prop_success:
            print(f"[Attempt {attempt+1}] Contradiction in propagate!")
            contradiction = True
            break

        iterations += 1

    if not contradiction:
        final_grid = grid
        print(f"✓ Solved in attempt {attempt+1}")
        break
    else:
        print(f"✗ Attempt {attempt+1} failed — retrying...")

if final_grid is None:
    print("!!! Could not solve after", max_attempts, "attempts.")
    final_grid = grid

#Drawing 2D grid___________________________________________________
rectangles = []
entropy_text = []
dot_centers = []
title_ids_text = []

for y in range(y_size):
    for x in range(x_size):
        cell = final_grid[y][x]
        origin = rg.Point3d(x, y, 0)
        dot_centers.append(origin + rg.Vector3d(0.5, 0.5, 0))
        rectangles.append(rg.Rectangle3d(rg.Plane(origin, rg.Vector3d.ZAxis), 1.0, 1.0))
        entropy_text.append(str(cell.entropy()))

        if cell.collapsed:
            title_ids_text.append(str(cell.options[0]))
        else:
            title_ids_text.append("_")

#output___________________________________________________
cells = rectangles
entropy = entropy_text
dot_centers = dot_centers
tile_ids = title_ids_text

#debug____________________________________________________
collapsed_count = sum(1 for row in grid for cell in row if cell.collapsed)
one_option_count = sum(1 for row in grid for cell in row if len(cell.options) == 1)
zero_option_count = sum(1 for row in grid for cell in row if len(cell.options) == 0)

print(f"Collapsed: {collapsed_count}")
print(f"One option (not collapsed): {one_option_count}")
print(f"Zero options (contradiction): {zero_option_count}")