from __future__ import annotations

import heapq

from .types import Coord


def astar(
    start: Coord,
    goal: Coord,
    width: int,
    height: int,
    obstacles: set[Coord],
) -> list[Coord] | None:
    if start == goal:
        return [start]

    def in_bounds(node: Coord) -> bool:
        return 0 <= node[0] < width and 0 <= node[1] < height

    def walkable(node: Coord) -> bool:
        return in_bounds(node) and node not in obstacles

    def neighbors(node: Coord) -> list[Coord]:
        x, y = node
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [n for n in candidates if walkable(n)]

    def h(a: Coord, b: Coord) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    frontier: list[tuple[int, Coord]] = []
    heapq.heappush(frontier, (0, start))
    came_from: dict[Coord, Coord | None] = {start: None}
    g_score: dict[Coord, int] = {start: 0}

    while frontier:
        _, current = heapq.heappop(frontier)

        if current == goal:
            path: list[Coord] = []
            cursor: Coord | None = current
            while cursor is not None:
                path.append(cursor)
                cursor = came_from[cursor]
            path.reverse()
            return path

        for nxt in neighbors(current):
            tentative = g_score[current] + 1
            if tentative < g_score.get(nxt, 10**9):
                came_from[nxt] = current
                g_score[nxt] = tentative
                f_score = tentative + h(nxt, goal)
                heapq.heappush(frontier, (f_score, nxt))

    return None
