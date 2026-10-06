#!/usr/bin/env python3
"""centipede-lite: 极简蜈蚣射击小游戏。

玩法：你在底部区域移动并发射子弹，击中蜈蚣节会把它打成蘑菇并把蜈蚣
劈成两段；蜈蚣碰到蘑菇或墙壁会转向并下降一行。别被蜈蚣或跳蚤碰到。
纯标准库，无实时键盘输入：交互是"每行一个命令"的回合制，--auto 为无头演示。
"""

import argparse
import random
import sys

W, H = 30, 20
PLAYER_ZONE = 4          # 玩家可活动的底部行数
MAX_BULLETS = 4
HEAD_SCORE, SEG_SCORE, FLEA_SCORE, SHROOM_SCORE = 100, 10, 200, 1


class Game:
    def __init__(self, seed=None, mushrooms=30):
        self.rng = random.Random(seed)
        self.score = 0
        self.lives = 3
        self.wave = 1
        self.mushrooms = set()
        self.bullets = []          # [(x, y)]
        self.fleas = []            # [{'x','y','hp'}]
        self.player = [W // 2, H - 1]
        self.over = False
        self.tick_count = 0
        while len(self.mushrooms) < mushrooms:
            x = self.rng.randrange(W)
            y = self.rng.randrange(H - PLAYER_ZONE - 2)
            self.mushrooms.add((x, y))
        self.centipedes = [self._new_centipede()]

    def _new_centipede(self, length=10):
        # 头在右端，向左移动，身体向右拖尾
        return [(W - 1 - i, 0, -1) for i in range(length)]

    # ---------- 玩家 ----------
    def move_player(self, dx, dy):
        x, y = self.player
        self.player[0] = max(0, min(W - 1, x + dx))
        self.player[1] = max(H - PLAYER_ZONE, min(H - 1, y + dy))

    def shoot(self):
        if len(self.bullets) < MAX_BULLETS:
            x, y = self.player
            if y - 1 >= 0:
                self.bullets.append((x, y - 1))

    # ---------- 主循环 ----------
    def step(self, cmd=None):
        """执行一帧。cmd: l/r/u/d 移动，f 开火，None 不动。"""
        if self.over:
            return
        self.tick_count += 1
        if cmd == "l":
            self.move_player(-1, 0)
        elif cmd == "r":
            self.move_player(1, 0)
        elif cmd == "u":
            self.move_player(0, -1)
        elif cmd == "d":
            self.move_player(0, 1)
        elif cmd == "f":
            self.shoot()
        self._move_bullets()
        self._bullet_hits()
        self._move_fleas()
        self._move_centipedes()
        self._player_hits()
        if not any(self.centipedes):
            self.wave += 1
            self.centipedes = [self._new_centipede()]
        # 跳蚤偶发：玩家区蘑菇少时更容易出现（致敬原版）
        zone_shrooms = sum(1 for (x, y) in self.mushrooms if y >= H - PLAYER_ZONE)
        if self.rng.random() < (0.02 if zone_shrooms < 5 else 0.004):
            self.fleas.append({"x": self.rng.randrange(W), "y": 0, "hp": 2})

    def _move_bullets(self):
        self.bullets = [(x, y - 2) for (x, y) in self.bullets if y - 2 >= 0]

    def _bullet_hits(self):
        for b in list(self.bullets):
            bx, by = b
            # 路径检查：子弹每帧走 2 格，检查路过的两格防止穿过目标
            for cy in (by, by + 1):
                if self._try_hit(b, bx, cy):
                    break

    def _try_hit(self, b, bx, cy):
        """子弹命中判定；命中返回 True（子弹被消耗）。"""
        if (bx, cy) in self.mushrooms:
            self.mushrooms.discard((bx, cy))
            self.bullets.remove(b)
            self.score += SHROOM_SCORE
            return True
        for f in list(self.fleas):
            if (bx, cy) == (f["x"], f["y"]):
                f["hp"] -= 1
                self.mushrooms.add((bx, cy))  # 跳蚤受伤掉蘑菇
                if f["hp"] <= 0:
                    self.fleas.remove(f)
                    self.score += FLEA_SCORE
                self.bullets.remove(b)
                return True
        for ci, segs in enumerate(list(self.centipedes)):
            for i, (sx, sy, dx) in enumerate(segs):
                if (bx, cy) == (sx, sy):
                    self.bullets.remove(b)
                    self.mushrooms.add((sx, sy))  # 被击中的节变成蘑菇
                    self.score += HEAD_SCORE if i == 0 else SEG_SCORE
                    new = []
                    if segs[:i]:
                        new.append(segs[:i])
                    if segs[i + 1:]:
                        new.append(segs[i + 1:])
                    self.centipedes[ci:ci + 1] = new
                    return True
        return False

    def _move_fleas(self):
        for f in list(self.fleas):
            self.mushrooms.add((f["x"], f["y"]))  # 跳蚤留下蘑菇轨迹
            f["y"] += 1
            if f["y"] >= H:
                self.fleas.remove(f)

    def _move_centipedes(self):
        for segs in self.centipedes:
            prev = [(x, y) for (x, y, dx) in segs]
            x, y, dx = segs[0]
            nx = x + dx
            if nx < 0 or nx >= W or (nx, y) in self.mushrooms:
                dx = -dx
                segs[0] = (x, min(y + 1, H - 1), dx)  # 撞墙/蘑菇：转向并下降
            else:
                segs[0] = (nx, y, dx)
            for i in range(1, len(segs)):
                segs[i] = (prev[i - 1][0], prev[i - 1][1], segs[i][2])

    def _player_hits(self):
        px, py = self.player
        for segs in self.centipedes:
            for (sx, sy, dx) in segs:
                if (px, py) == (sx, sy):
                    return self._lose_life()
        for f in self.fleas:
            if (px, py) == (f["x"], f["y"]):
                return self._lose_life()

    def _lose_life(self):
        self.lives -= 1
        if self.lives <= 0:
            self.over = True
        else:
            self.player = [W // 2, H - 1]

    # ---------- AI ----------
    def ai_step(self):
        px, py = self.player
        target_x = None
        # 躲跳蚤
        for f in self.fleas:
            if abs(f["x"] - px) <= 1 and f["y"] >= py - 5:
                target_x = px + (3 if f["x"] <= px else -3)
                break
        # 躲玩家区的蜈蚣节
        if target_x is None:
            for c in self.centipedes:
                for (x, y, dx) in c:
                    if y >= py - 1 and abs(x - px) <= 2:
                        target_x = px + (3 if x <= px else -3)
                        break
                if target_x is not None:
                    break
        # 瞄准最低的节
        if target_x is None:
            best_y, tx = -1, None
            for c in self.centipedes:
                for (x, y, dx) in c:
                    if y < py and y > best_y:
                        best_y, tx = y, x
            target_x = tx
        if target_x is not None:
            if px < target_x:
                self.move_player(1, 0)
            elif px > target_x:
                self.move_player(-1, 0)
        if any(x == self.player[0] and y < py
               for c in self.centipedes for (x, y, dx) in c):
            self.shoot()
        elif self.tick_count % 9 == 0:
            self.shoot()
        self.step()

    # ---------- 渲染 ----------
    def render(self):
        grid = [["·"] * W for _ in range(H)]
        for (x, y) in self.mushrooms:
            grid[y][x] = "m"
        for (x, y) in self.bullets:
            grid[y][x] = "┃"
        for f in self.fleas:
            grid[f["y"]][f["x"]] = "F"
        for segs in self.centipedes:
            for i, (x, y, dx) in enumerate(segs):
                grid[y][x] = "H" if i == 0 else "o"
        px, py = self.player
        grid[py][px] = "A"
        bar = f"分数 {self.score}  生命 {self.lives}  波次 {self.wave}"
        return bar + "\n" + "\n".join("".join(r) for r in grid)


def auto_play(seed=None, frames=600, verbose=False):
    g = Game(seed=seed)
    for _ in range(frames):
        if g.over:
            break
        g.ai_step()
    if verbose:
        print(g.render())
    print(f"自动演示结束：得分 {g.score}，帧数 {g.tick_count}，"
          f"生命 {g.lives}，波次 {g.wave}，{'失败' if g.over else '存活'}")
    return g


def play_interactive(seed=None):
    g = Game(seed=seed)
    print("蜈蚣射击：a左 d右 w上 s下 f开火 q退出（每行一个命令）")
    while not g.over:
        print(g.render())
        try:
            line = input("> ").strip().lower()
        except EOFError:
            break
        if line == "q":
            break
        cmd = {"a": "l", "d": "r", "w": "u", "s": "d", "f": "f"}.get(line)
        if line and cmd is None:
            print("未知命令，用 a/d/w/s/f/q")
            continue
        g.step(cmd)
    print(g.render())
    print(f"游戏结束：得分 {g.score}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="极简蜈蚣射击游戏")
    ap.add_argument("--auto", action="store_true", help="无头自动演示")
    ap.add_argument("--frames", type=int, default=600, help="演示帧数")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--verbose", action="store_true", help="演示结束打印棋盘")
    args = ap.parse_args(argv)
    if args.auto:
        auto_play(seed=args.seed, frames=args.frames, verbose=args.verbose)
    else:
        if not sys.stdin.isatty():
            print("交互模式需要终端；非终端请用 --auto", file=sys.stderr)
            return 2
        play_interactive(seed=args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
