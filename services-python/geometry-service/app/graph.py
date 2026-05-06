"""Convert a 1-pixel-wide skeleton image into a graph of chains.

* `find_endpoints_and_junctions` returns coordinates of pixels with exactly
  one neighbour (endpoints) and three or more neighbours (junctions).
* `extract_chains` walks each chain from endpoint-to-endpoint or junction-
  to-junction returning a list of ordered point sequences.

Implementation uses a 3x3 neighbour-count convolution, which is much faster
than per-pixel loops and works well on dense engineering drawings.
"""
from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np


Point = Tuple[int, int]   # (x, y) in pixel coords
Chain = List[Point]


def neighbour_count(skel: np.ndarray) -> np.ndarray:
    bin_ = (skel > 0).astype(np.uint8)
    kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], dtype=np.uint8)
    cnt = cv2.filter2D(bin_, ddepth=cv2.CV_8U, kernel=kernel, borderType=cv2.BORDER_CONSTANT)
    cnt[bin_ == 0] = 0
    return cnt


def find_endpoints_and_junctions(skel: np.ndarray) -> tuple[set[Point], set[Point]]:
    cnt = neighbour_count(skel)
    ys, xs = np.where(cnt == 1)
    endpoints = set(zip(xs.tolist(), ys.tolist()))
    ys, xs = np.where(cnt >= 3)
    junctions = set(zip(xs.tolist(), ys.tolist()))
    return endpoints, junctions


def extract_chains(skel: np.ndarray) -> List[Chain]:
    """Walk every connected sequence of skeleton pixels between
    endpoints/junctions. The resulting chains may share endpoints (junctions)
    but each pixel belongs to at most two chains."""
    if skel.dtype != np.uint8:
        skel = skel.astype(np.uint8)
    endpoints, junctions = find_endpoints_and_junctions(skel)
    visited = np.zeros_like(skel, dtype=bool)
    chains: List[Chain] = []

    h, w = skel.shape[:2]

    def neighbours(p: Point) -> List[Point]:
        x, y = p
        out: List[Point] = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and skel[ny, nx]:
                    out.append((nx, ny))
        return out

    starts = list(endpoints) + list(junctions)
    for start in starts:
        for nb in neighbours(start):
            if visited[nb[1], nb[0]]:
                continue
            chain = _walk(start, nb, neighbours, junctions, endpoints, visited)
            if len(chain) >= 4:
                chains.append(chain)

    # Pick up isolated closed loops (no endpoints/junctions).
    ys, xs = np.where((skel > 0) & (~visited))
    pts = list(zip(xs.tolist(), ys.tolist()))
    for p in pts:
        if visited[p[1], p[0]]:
            continue
        loop = _walk_loop(p, neighbours, visited)
        if len(loop) >= 8:
            chains.append(loop)

    return chains


def _walk(
    prev: Point,
    cur: Point,
    neighbours,
    junctions: set[Point],
    endpoints: set[Point],
    visited: np.ndarray,
) -> Chain:
    chain: Chain = [prev, cur]
    visited[cur[1], cur[0]] = True
    while True:
        if cur in junctions or cur in endpoints and len(chain) > 2:
            return chain
        nbs = [n for n in neighbours(cur) if not visited[n[1], n[0]] and n != prev]
        if not nbs:
            return chain
        prev, cur = cur, nbs[0]
        visited[cur[1], cur[0]] = True
        chain.append(cur)
        if cur in junctions or cur in endpoints:
            return chain


def _walk_loop(start: Point, neighbours, visited: np.ndarray) -> Chain:
    chain: Chain = [start]
    visited[start[1], start[0]] = True
    prev, cur = None, start
    while True:
        nbs = [n for n in neighbours(cur) if not visited[n[1], n[0]]]
        if not nbs:
            return chain
        prev, cur = cur, nbs[0]
        visited[cur[1], cur[0]] = True
        chain.append(cur)
        if cur == start:
            return chain
