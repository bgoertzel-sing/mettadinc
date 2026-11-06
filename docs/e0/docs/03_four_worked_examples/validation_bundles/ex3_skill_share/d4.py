"""Example 3: skill transfer between robots whose cameras see a 5x5 bay in different frames.

Cells (r, c), r = row from the top, c = column from the left, 0..4.  The dihedral group D4 acts
on cells and on the four image directions.  Element order (used for canonical choices):
id, r90, r180, r270, mv (mirror left-right), mh (mirror up-down), md (transpose), ma (anti-transpose).
"""
from fractions import Fraction as F
N = 5
CELLS = [(r, c) for r in range(N) for c in range(N)]
DIRS = ["up", "right", "down", "left"]
STEP = {"up": (-1, 0), "right": (0, 1), "down": (1, 0), "left": (0, -1)}
GOAL = (2, 2)
PILLARS = {(1, 0), (3, 0), (1, 4), (3, 4)}
FREE = [x for x in CELLS if x not in PILLARS]

CELL_MAP = {
    "id":   lambda r, c: (r, c),
    "r90":  lambda r, c: (c, 4 - r),        # clockwise quarter turn on the screen
    "r180": lambda r, c: (4 - r, 4 - c),
    "r270": lambda r, c: (4 - c, r),
    "mv":   lambda r, c: (r, 4 - c),        # mirror in the vertical axis (left <-> right)
    "mh":   lambda r, c: (4 - r, c),        # mirror in the horizontal axis (up <-> down)
    "md":   lambda r, c: (c, r),            # transpose
    "ma":   lambda r, c: (4 - c, 4 - r),    # anti-transpose
}
ORDER = list(CELL_MAP)


def dir_map(g):
    """The induced action on directions: the direction of the image of a unit step."""
    f = CELL_MAP[g]
    out = {}
    for d, (dr, dc) in STEP.items():
        a, b = f(2, 2), f(2 + dr, 2 + dc)
        v = (b[0] - a[0], b[1] - a[1])
        out[d] = next(k for k, s in STEP.items() if s == v)
    return out


def cell_perm(g):
    return {x: CELL_MAP[g](*x) for x in CELLS}


def as_pair(g):
    return (cell_perm(g), dir_map(g))


def compose(g, h):
    """g after h, as an element name."""
    pg, ph = cell_perm(g), cell_perm(h)
    comp = {x: pg[ph[x]] for x in CELLS}
    return next(k for k in ORDER if cell_perm(k) == comp)


def inverse(g):
    return next(k for k in ORDER if compose(g, k) == "id")


def step(x, d):
    y = (x[0] + STEP[d][0], x[1] + STEP[d][1])
    if not (0 <= y[0] < N and 0 <= y[1] < N) or y in PILLARS:
        return x
    return y


def dist(x):
    return abs(x[0] - GOAL[0]) + abs(x[1] - GOAL[1])


def progress(x, d):
    y = step(x, d)
    if dist(y) < dist(x):
        return F(1)
    if dist(y) == dist(x):
        return F(1, 2)
    return F(0)


def docking(x, d):
    """Progress, except that arriving at the goal from any side but the north earns 1/2."""
    y = step(x, d)
    if y == GOAL and x != GOAL and d != "down":
        return F(1, 2)
    return progress(x, d)


def symmetry_group(resp, cells=FREE):
    return [g for g in ORDER if all(resp(CELL_MAP[g](*x), dir_map(g)[d]) == resp(x, d) for x in cells for d in DIRS)]
