"""
Wave Function Collapse on a 2D grid for Rhino / Grasshopper.

Inputs:
    TR       : list[str]   each parseable to a sockets list [top, right, bottom, left]
    x_size   : int         grid width
    y_size   : int         grid height
    seed     : int|None    (optional) for reproducible output
    weights  : list|None   (optional) one weight per tile, enables Shannon entropy
    DEBUG    : bool         (optional) toggles console prints

Outputs:
    cells       : Rectangle3d per cell
    entropy     : option-count label per cell
    dot_centers : center point per cell
    tile_ids    : collapsed tile id per cell ('_' if not collapsed)
"""

import Rhino.Geometry as rg
import random
import math
import ast
from collections import deque

# ----------------------------- configuration -----------------------------
DEBUG = bool(globals().get('DEBUG', False))

# Sockets convention: [top, right, bottom, left]  ->  indices 0,1,2,3
DIR_INDEX = {'up': 0, 'right': 1, 'down': 2, 'left': 3}
OPPOSITE  = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}

# Set True if a shared edge is read in reverse order by the neighbour
# (directional / non-symmetric sockets). False = symmetric equality.
DIRECTIONAL_SOCKETS = False

_seed_in = globals().get('seed', None)
if _seed_in is not None:
    random.seed(_seed_in)


# ------------------------------- classes ----------------------------------
class Tile(object):
    def __init__(self, tile_id, sockets, geometry_data=None):
        self.id = tile_id
        self.sockets = sockets            # [top, right, bottom, left]
        self.geometry_data = geometry_data

    def get_socket(self, direction):
        return self.sockets[DIR_INDEX[direction]]


class Cell(object):
    def __init__(self, x, y, all_ids):
        self.x = x
        self.y = y
        self.options = list(all_ids)
        self.collapsed = False

    def entropy(self):
        if self.collapsed:
            return 0
        return len(self.options)         # 0 here means contradiction


# ------------------------- parse tiles from input -------------------------
tiles_rules = {}
all_tiles = {}
for tid, tile_str in enumerate(TR):
    sockets = ast.literal_eval(tile_str)
    tiles_rules[tid] = sockets
    all_tiles[tid] = Tile(tid, sockets)

# weights / entropy mode
_weights_in = globals().get('weights', None)
if _weights_in:
    WEIGHTS = {tid: float(_weights_in[tid]) for tid in tiles_rules}
else:
    WEIGHTS = {tid: 1.0 for tid in tiles_rules}
USE_SHANNON = any(w != 1.0 for w in WEIGHTS.values())


# ----------------------- single source of matching ------------------------
def check_match(socket_a, socket_b):
    """Edge compatibility. Change here to alter the whole rule system."""
    if DIRECTIONAL_SOCKETS:
        return socket_a == socket_b[::-1]
    return socket_a == socket_b


# ------------------------------- entropy ----------------------------------
def cell_entropy(cell):
    if cell.collapsed or not cell.options:
        return 0.0
    if not USE_SHANNON:
        return float(len(cell.options))
    total = sum(WEIGHTS[o] for o in cell.options)
    return math.log(total) - sum(
        WEIGHTS[o] * math.log(WEIGHTS[o]) for o in cell.options) / total


def lowest_entropy_cell(grid):
    best_e = None
    candidates = []
    for row in grid:
        for c in row:
            if c.collapsed or len(c.options) <= 0:
                continue
            e = cell_entropy(c)
            if best_e is None or e < best_e - 1e-9:
                best_e, candidates = e, [c]
            elif abs(e - best_e) <= 1e-9:
                candidates.append(c)
    return random.choice(candidates) if candidates else None


# ----------------------------- grid helpers -------------------------------
def build_grid(x_size, y_size):
    ids = list(tiles_rules.keys())
    return [[Cell(x, y, ids) for x in range(x_size)] for y in range(y_size)]


def is_fully_collapsed(grid):
    return all(c.collapsed for row in grid for c in row)


def snapshot(grid):
    return [[(c.collapsed, tuple(c.options)) for c in row] for row in grid]


def restore(grid, snap):
    for row, srow in zip(grid, snap):
        for c, (collapsed, opts) in zip(row, srow):
            c.collapsed = collapsed
            c.options = list(opts)


def collapse_to(cell, tile_id):
    cell.options = [tile_id]
    cell.collapsed = True


def weighted_order(options):
    """Return options in the order they should be tried."""
    opts = list(options)
    if not USE_SHANNON:
        random.shuffle(opts)
        return opts
    result, pool = [], opts
    while pool:
        total = sum(WEIGHTS[o] for o in pool)
        r, acc = random.uniform(0, total), 0.0
        for i, o in enumerate(pool):
            acc += WEIGHTS[o]
            if r <= acc:
                result.append(pool.pop(i))
                break
        else:
            result.append(pool.pop())
    return result


# ------------------------------ propagation -------------------------------
def get_neighbors(grid, cell, x_size, y_size):
    x, y, res = cell.x, cell.y, []
    if x + 1 < x_size: res.append(('right', grid[y][x + 1]))
    if x - 1 >= 0:     res.append(('left',  grid[y][x - 1]))
    if y + 1 < y_size: res.append(('up',    grid[y + 1][x]))
    if y - 1 >= 0:     res.append(('down',  grid[y - 1][x]))
    return res


def propagate(grid, start_cell, x_size, y_size):
    """Returns False on contradiction (a neighbour left with 0 options)."""
    queue = deque([start_cell])
    in_queue = {(start_cell.x, start_cell.y)}
    while queue:
        cell = queue.popleft()
        in_queue.discard((cell.x, cell.y))
        for direction, neighbor in get_neighbors(grid, cell, x_size, y_size):
            if neighbor.collapsed:
                continue
            dir_idx = DIR_INDEX[direction]
            opp_idx = DIR_INDEX[OPPOSITE[direction]]
            valid = {all_tiles[o].sockets[dir_idx] for o in cell.options}
            new_options = [
                opt for opt in neighbor.options
                if any(check_match(all_tiles[opt].sockets[opp_idx], v)
                       for v in valid)
            ]
            if len(new_options) < len(neighbor.options):
                neighbor.options = new_options
                if not new_options:
                    if DEBUG:
                        print("Contradiction at (%d,%d) via %s"
                              % (neighbor.x, neighbor.y, direction))
                    return False
                key = (neighbor.x, neighbor.y)
                if key not in in_queue:
                    queue.append(neighbor)
                    in_queue.add(key)
    return True


# --------------------------- backtracking solver --------------------------
def advance(grid, stack, x_size, y_size):
    """
    Restore to the latest decision frame that still has untried options,
    apply the next option and propagate. Pops exhausted frames.
    Returns True if a viable continuation is set up, False if exhausted.
    """
    while stack:
        frame = stack[-1]
        restore(grid, frame['snap'])
        if not frame['remaining']:
            stack.pop()
            continue
        chosen = frame['remaining'].pop(0)
        cell = grid[frame['y']][frame['x']]
        collapse_to(cell, chosen)
        if propagate(grid, cell, x_size, y_size):
            return True
        # this option failed too -> loop tries next / pops
    return False


def solve(x_size, y_size, max_steps=200000):
    grid = build_grid(x_size, y_size)
    stack = []
    steps = 0
    while True:
        steps += 1
        if steps > max_steps:
            if DEBUG:
                print("Aborted: step cap reached.")
            return grid, False

        cell = lowest_entropy_cell(grid)
        if cell is None:
            if is_fully_collapsed(grid):
                return grid, True
            # a 0-option cell exists -> backtrack
            if not advance(grid, stack, x_size, y_size):
                return grid, False
            continue

        # open a fresh decision frame and let advance() try it
        stack.append({'snap': snapshot(grid), 'x': cell.x, 'y': cell.y,
                      'remaining': weighted_order(cell.options)})
        if not advance(grid, stack, x_size, y_size):
            return grid, False


# --------------------------------- run ------------------------------------
final_grid, ok = solve(x_size, y_size)
if DEBUG:
    print("Solved." if ok else "Failed - returning best-effort grid.")

rectangles, dot_centers, entropy_text, tile_ids_text = [], [], [], []
for row in final_grid:
    for cell in row:
        origin = rg.Point3d(cell.x, cell.y, 0)
        plane = rg.Plane(origin, rg.Vector3d.ZAxis)
        rectangles.append(rg.Rectangle3d(plane, 1.0, 1.0))
        dot_centers.append(origin + rg.Vector3d(0.5, 0.5, 0))
        entropy_text.append(str(len(cell.options)))
        tile_ids_text.append(str(cell.options[0]) if cell.collapsed else "_")

cells = rectangles
entropy = entropy_text
tile_ids = tile_ids_text

if DEBUG:
    collapsed_count = sum(1 for r in final_grid for c in r if c.collapsed)
    one_option = sum(1 for r in final_grid for c in r if len(c.options) == 1)
    zero_option = sum(1 for r in final_grid for c in r if len(c.options) == 0)
    print("collapsed:", collapsed_count,
          "| one:", one_option, "| zero:", zero_option)
