from d4 import *


class Robot:
    def __init__(self, name, frame, resp):
        self.name, self.frame, self.world = name, frame, resp
        self.ginv = inverse(frame)
        self.states = sorted(CELL_MAP[frame](*x) for x in FREE)

    def resp(self, y, m):
        return self.world(CELL_MAP[self.ginv](*y), dir_map(self.ginv)[m])


def is_exact(src, tgt, f):
    """Transfer from src to tgt with state pullback f (tgt cells -> src cells) and method
    pushforward f^-1 on directions (src commands -> tgt commands)."""
    fi = dir_map(inverse(f))
    return all(src.resp(CELL_MAP[f](*y), m) == tgt.resp(y, fi[m]) for y in tgt.states for m in DIRS)


def learned(src, tgt):
    return next(f for f in ORDER if is_exact(src, tgt, f))


def calibrated(src, tgt):
    return compose(src.frame, inverse(tgt.frame))


def holonomy(edges):
    """edges: state-pullback elements of A->B, B->C, C->A; holonomy pullback = AB o BC o CA."""
    ab, bc, ca = edges
    return compose(ab, compose(bc, ca))
