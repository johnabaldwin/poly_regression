"""Top-level system overview — data flow between forward pass, reverse pass,
and controller across training epochs."""

from manim import *
import numpy as np

BG    = "#1e1e2e"
MEM_F = "#1e3a2f"; MEM_S = "#a6e3a1"
BLK_F = "#25253a"; BLK_S = "#89b4fa"
X_C   = "#89dceb"
ERR_C = "#f38ba8"
K_C   = "#f9e2af"
CTL_C = "#b4befe"
LAB   = "#cdd6f4"
DIM   = "#585b70"

SLOW = 1.0   # global speed multiplier: >1 slows down, <1 speeds up


def rbox(label, w=2.2, h=0.85, F=BLK_F, S=BLK_S, fs=28):
    r = RoundedRectangle(corner_radius=0.12, width=w, height=h,
                         fill_color=F, fill_opacity=1,
                         stroke_color=S, stroke_width=2.5)
    t = Tex(rf"\textrm{{{label}}}", font_size=fs, color=LAB)
    t.move_to(r)
    return VGroup(r, t)


def arr(s, e, col, sw=2.5):
    return Arrow(s, e, buff=0.0, color=col, stroke_width=sw,
                 tip_length=0.17, max_tip_length_to_length_ratio=0.45)


def move_dot(start, end, col, r=0.12, rt=0.5):
    path = Line(start, end)
    dot  = Dot(radius=r, color=col).move_to(start)
    anim = MoveAlongPath(dot, path, run_time=rt * SLOW, rate_func=smooth)
    return dot, anim


class TopLevelFlow(MovingCameraScene):

    def construct(self):
        self.camera.background_color = BG

        # ── Grid layout ───────────────────────────────────────────────────────
        # Row 0 (y=2.0):  data_mem  |  error_mem  |  coef_mem
        # Row 1 (y=-0.5): fwd_pass  | controller  |  rev_pass
        C = [-4.5, 0.0, 4.5]
        R = [2.0, -0.5]

        title = Text("Polynomial Regression — System Overview",
                     font_size=36, color=LAB, weight=BOLD)
        title.to_edge(UP, buff=0.35)

        data_mem   = rbox("Data Memory",   w=3.0, h=1.10, F=MEM_F, S=MEM_S, fs=28)
        error_mem  = rbox("Error Memory", w=3.0, h=1.10, F=MEM_F, S=ERR_C, fs=28)
        coef_mem   = rbox("Coef. Memory", w=3.0, h=1.10, F=MEM_F, S=K_C,   fs=28)
        fwd_pass   = rbox("Forward Pass", w=3.2, h=1.10, F=BLK_F, S=BLK_S, fs=28)
        controller = rbox("Controller",   w=3.0, h=1.10, F=BLK_F, S=CTL_C, fs=28)
        rev_pass   = rbox("Reverse Pass", w=3.2, h=1.10, F=BLK_F, S=BLK_S, fs=28)

        data_mem  .move_to([C[0], R[0], 0])
        error_mem .move_to([C[1], R[0], 0])
        coef_mem  .move_to([C[2], R[0], 0])
        fwd_pass  .move_to([C[0], R[1], 0])
        controller.move_to([C[1], R[1], 0])
        rev_pass  .move_to([C[2], R[1], 0])

        # ── Primary arrows ────────────────────────────────────────────────────
        # A1  data_mem ↓ fwd_pass          (x_i, y_i samples)
        a1s = data_mem.get_edge_center(DOWN)
        a1e = fwd_pass.get_edge_center(UP)
        A1  = arr(a1s, a1e, X_C)

        # A2  fwd_pass → error_mem         (write e_i)
        a2s = fwd_pass.get_edge_center(RIGHT)
        a2e = error_mem.get_edge_center(LEFT)
        A2  = arr(a2s, a2e, ERR_C)

        # A3  error_mem → rev_pass         (read e_i)
        a3s = error_mem.get_edge_center(RIGHT)
        a3e = rev_pass.get_edge_center(LEFT)
        A3  = arr(a3s, a3e, ERR_C)

        # A4  coef_mem ↓ rev_pass (left lane, read c_k)
        a4s = coef_mem.get_edge_center(DOWN) + LEFT  * 0.32
        a4e = rev_pass.get_edge_center(UP)   + LEFT  * 0.32
        A4  = arr(a4s, a4e, K_C)

        # A5  rev_pass ↑ coef_mem (right lane, write c_k')
        a5s = rev_pass.get_edge_center(UP)   + RIGHT * 0.32
        a5e = coef_mem.get_edge_center(DOWN) + RIGHT * 0.32
        A5  = arr(a5s, a5e, K_C)

        # A6  controller → fwd_pass (upper lane, ctrl)
        a6s = controller.get_edge_center(LEFT) + UP   * 0.16
        a6e = fwd_pass.get_edge_center(RIGHT)  + UP   * 0.16
        A6  = arr(a6s, a6e, CTL_C)

        # A7  fwd_pass → controller (lower lane, status)
        a7s = fwd_pass.get_edge_center(RIGHT)  + DOWN * 0.16
        a7e = controller.get_edge_center(LEFT) + DOWN * 0.16
        A7  = arr(a7s, a7e, CTL_C)

        # A8  controller → rev_pass (upper lane, ctrl)
        a8s = controller.get_edge_center(RIGHT) + UP   * 0.16
        a8e = rev_pass.get_edge_center(LEFT)    + UP   * 0.16
        A8  = arr(a8s, a8e, CTL_C)

        # A9  rev_pass → controller (lower lane, status)
        a9s = rev_pass.get_edge_center(LEFT)    + DOWN * 0.16
        a9e = controller.get_edge_center(RIGHT) + DOWN * 0.16
        A9  = arr(a9s, a9e, CTL_C)

        # ── Secondary (shared-bus) dashed arrows ──────────────────────────────
        # D1  data_mem → rev_pass  (x_i also feeds rev_pass)
        d1s = data_mem.get_edge_center(RIGHT)
        d1e = rev_pass.get_edge_center(UP) + LEFT * 0.65
        D1  = Arrow(d1s, d1e, buff=0.0, color=X_C, stroke_width=1.4,
                    tip_length=0.13, max_tip_length_to_length_ratio=0.45)
        D1.set_opacity(0.55)

        # D2  coef_mem → fwd_pass  (c_k also feeds fwd_pass)
        d2s = coef_mem.get_edge_center(LEFT)
        d2e = fwd_pass.get_edge_center(UP) + RIGHT * 0.65
        D2  = Arrow(d2s, d2e, buff=0.0, color=K_C, stroke_width=1.4,
                    tip_length=0.13, max_tip_length_to_length_ratio=0.45)
        D2.set_opacity(0.55)

        # ── Arrow labels ──────────────────────────────────────────────────────
        def albl(tex, col=DIM, fs=22):
            return MathTex(tex, font_size=fs, color=col)

        def mid(a, b):
            return (np.array(a) + np.array(b)) / 2

        L_A1  = albl(r"x_i,\; y_i", X_C).next_to(A1, LEFT, buff=0.10)
        L_A2  = albl(r"e_i",  ERR_C).move_to(mid(a2s, a2e) + UP  * 0.28 + LEFT * 0.1)
        L_A3  = albl(r"e_i",  ERR_C).move_to(mid(a3s, a3e) + UP  * 0.28 + RIGHT * 0.1)
        L_A45 = albl(r"c_k",  K_C  ).next_to(VGroup(A4, A5), RIGHT, buff=0.10)
        L_A6  = albl(r"\mathrm{ctrl}", CTL_C).move_to(mid(a6s, a6e) + UP * 0.25)
        L_A7  = albl(r"\mathrm{status}", CTL_C).move_to(mid(a7s, a7e) + DOWN * 0.25)
        L_A8  = albl(r"\mathrm{ctrl}", CTL_C).move_to(mid(a8s, a8e) + UP * 0.25)
        L_A9  = albl(r"\mathrm{status}", CTL_C).move_to(mid(a9s, a9e) + DOWN * 0.25)
        L_D1  = albl(r"x_i", X_C).move_to(mid(d1s, d1e) + UP * 0.28)
        L_D2  = albl(r"c_k", K_C).move_to(mid(d2s, d2e) + DOWN * 0.28)
        L_D1.set_opacity(0.6); L_D2.set_opacity(0.6)

        ov_arrows = VGroup(A1, A2, A3, A4, A5, A6, A7, A8, A9, D1, D2)
        ov_labels = VGroup(L_A1, L_A2, L_A3, L_A45, L_A6, L_A7, L_A8, L_A9, L_D1, L_D2)
        overview_all = VGroup(title, data_mem, error_mem, coef_mem,
                              fwd_pass, controller, rev_pass, ov_arrows, ov_labels)

        # ── Phase 1: Overview ─────────────────────────────────────────────────
        self.play(FadeIn(title), run_time=0.7 * SLOW)
        self.play(LaggedStart(
            *[FadeIn(b, shift=UP * 0.1) for b in
              [data_mem, error_mem, coef_mem, fwd_pass, controller, rev_pass]],
            lag_ratio=0.15, run_time=2.4 * SLOW,
        ))
        self.play(
            Create(ov_arrows, lag_ratio=0.07, run_time=2.2 * SLOW),
            FadeIn(ov_labels, run_time=1.4 * SLOW),
        )
        self.wait(1.5 * SLOW)

        # ── Phase 2: Forward Pass ─────────────────────────────────────────────
        fwd_cap = Tex(
            r"\textbf{Phase 1 — Forward Pass:} "
            r"compute $\hat{y}_i = \sum_k c_k x_i^k$, store $e_i = y_i - \hat{y}_i$",
            font_size=24, color=BLK_S,
        ).to_edge(DOWN, buff=0.38)
        self.play(FadeIn(fwd_cap, shift=UP * 0.1), run_time=0.6 * SLOW)
        self.wait(0.5 * SLOW)

        # Controller triggers fwd_pass
        self.play(Indicate(controller[0], color=CTL_C, scale_factor=1.2), run_time=0.6 * SLOW)
        d, a = move_dot(a6s, a6e, CTL_C, rt=0.7)
        self.play(FadeIn(d), run_time=0.12 * SLOW)
        self.play(a)
        self.play(FadeOut(d, target_position=fwd_pass.get_center()),
                  fwd_pass[0].animate.set_stroke(color=CTL_C, width=4), run_time=0.35 * SLOW)
        self.play(fwd_pass[0].animate.set_stroke(color=BLK_S, width=2.5), run_time=0.25 * SLOW)
        self.wait(0.3 * SLOW)

        # Two samples: x/y data + coef read → fwd_pass → error_mem
        for _ in range(2):
            # x, y from data_mem
            d, a = move_dot(a1s, a1e, X_C, rt=0.75)
            self.play(FadeIn(d), run_time=0.12 * SLOW)
            self.play(a)
            self.play(FadeOut(d, target_position=fwd_pass.get_center()),
                      fwd_pass[0].animate.set_stroke(color=X_C, width=3.5), run_time=0.3 * SLOW)
            self.play(fwd_pass[0].animate.set_stroke(color=BLK_S, width=2.5), run_time=0.2 * SLOW)

            # coef from coef_mem (along D2 diagonal)
            d, a = move_dot(d2s, d2e, K_C, rt=0.85)
            self.play(FadeIn(d), run_time=0.12 * SLOW)
            self.play(a)
            self.play(FadeOut(d, target_position=fwd_pass.get_center()), run_time=0.25 * SLOW)

            # error out to error_mem
            d, a = move_dot(a2s, a2e, ERR_C, rt=0.85)
            self.play(FadeIn(d), run_time=0.12 * SLOW)
            self.play(a)
            self.play(FadeOut(d, target_position=error_mem.get_center()),
                      error_mem[0].animate.set_stroke(color=ERR_C, width=4), run_time=0.3 * SLOW)
            self.play(error_mem[0].animate.set_stroke(color=ERR_C, width=2.5), run_time=0.2 * SLOW)
            self.wait(0.2 * SLOW)

        # fwd_pass done → controller (with loss)
        d, a = move_dot(a7s, a7e, CTL_C, rt=0.75)
        self.play(FadeIn(d), run_time=0.12 * SLOW)
        self.play(a)
        loss_lbl = MathTex(r"\mathcal{L}", font_size=26, color=CTL_C)
        loss_lbl.next_to(controller, UP, buff=0.12)
        self.play(FadeOut(d, target_position=controller.get_center()),
                  FadeIn(loss_lbl, scale=0.7), run_time=0.4 * SLOW)
        self.wait(1.0 * SLOW)

        # ── Phase 3: Reverse Pass ─────────────────────────────────────────────
        rev_cap = Tex(
            r"\textbf{Phase 2 — Reverse Pass:} "
            r"$\nabla_k = \sum_i e_i x_i^k$,\quad $c_k \;\leftarrow\; c_k - \alpha\nabla_k$",
            font_size=24, color=BLK_S,
        ).to_edge(DOWN, buff=0.38)
        self.play(FadeOut(fwd_cap), FadeOut(loss_lbl),
                  FadeIn(rev_cap, shift=UP * 0.1), run_time=0.6 * SLOW)
        self.wait(0.5 * SLOW)

        # Controller triggers rev_pass
        self.play(Indicate(controller[0], color=CTL_C, scale_factor=1.2), run_time=0.6 * SLOW)
        d, a = move_dot(a8s, a8e, CTL_C, rt=0.7)
        self.play(FadeIn(d), run_time=0.12 * SLOW)
        self.play(a)
        self.play(FadeOut(d, target_position=rev_pass.get_center()),
                  rev_pass[0].animate.set_stroke(color=CTL_C, width=4), run_time=0.35 * SLOW)
        self.play(rev_pass[0].animate.set_stroke(color=BLK_S, width=2.5), run_time=0.25 * SLOW)
        self.wait(0.3 * SLOW)

        # Two k iterations: x + error + coef → rev_pass → updated coef
        for _ in range(2):
            # x from data_mem (along D1 diagonal)
            d, a = move_dot(d1s, d1e, X_C, rt=0.85)
            self.play(FadeIn(d), run_time=0.12 * SLOW)
            self.play(a)
            self.play(FadeOut(d, target_position=rev_pass.get_center()),
                      rev_pass[0].animate.set_stroke(color=X_C, width=3.5), run_time=0.3 * SLOW)
            self.play(rev_pass[0].animate.set_stroke(color=BLK_S, width=2.5), run_time=0.2 * SLOW)

            # error from error_mem
            d, a = move_dot(a3s, a3e, ERR_C, rt=0.85)
            self.play(FadeIn(d), run_time=0.12 * SLOW)
            self.play(a)
            self.play(FadeOut(d, target_position=rev_pass.get_center()), run_time=0.25 * SLOW)

            # coef read from coef_mem
            d, a = move_dot(a4s, a4e, K_C, rt=0.75)
            self.play(FadeIn(d), run_time=0.12 * SLOW)
            self.play(a)
            self.play(FadeOut(d, target_position=rev_pass.get_center()),
                      rev_pass[0].animate.set_stroke(color=K_C, width=3.5), run_time=0.3 * SLOW)
            self.play(rev_pass[0].animate.set_stroke(color=BLK_S, width=2.5), run_time=0.2 * SLOW)

            # updated coef write to coef_mem
            d, a = move_dot(a5s, a5e, K_C, rt=0.75)
            self.play(FadeIn(d), run_time=0.12 * SLOW)
            self.play(a)
            self.play(FadeOut(d, target_position=coef_mem.get_center()),
                      Indicate(coef_mem[0], color=K_C, scale_factor=1.1), run_time=0.45 * SLOW)
            self.wait(0.2 * SLOW)

        # rev_pass done → controller
        d, a = move_dot(a9s, a9e, CTL_C, rt=0.75)
        self.play(FadeIn(d), run_time=0.12 * SLOW)
        self.play(a)
        self.play(FadeOut(d, target_position=controller.get_center()), run_time=0.3 * SLOW)
        self.wait(0.7 * SLOW)

        # ── Epoch repeat caption ──────────────────────────────────────────────
        self.play(FadeOut(rev_cap), run_time=0.4 * SLOW)
        caption = Tex(
            r"Repeat for $N$ epochs: forward pass fills \texttt{error\_mem}; "
            r"reverse pass updates \texttt{coef\_mem} until convergence.",
            font_size=24, color=LAB,
        ).to_edge(DOWN, buff=0.35)
        self.play(FadeIn(caption, shift=UP * 0.1), run_time=0.6 * SLOW)
        self.wait(3.5 * SLOW)
        self.play(FadeOut(caption), run_time=0.5 * SLOW)
        self.wait(0.4 * SLOW)


class TopLevelStatic(Scene):
    """Static 1080p overview — all elements placed at once, no animation."""

    def construct(self):
        self.camera.background_color = BG

        C = [-4.5, 0.0, 4.5]
        R = [2.0, -0.5]

        title = Text("Polynomial Regression — System Overview",
                     font_size=36, color=LAB, weight=BOLD)
        title.to_edge(UP, buff=0.35)

        data_mem   = rbox("Data Memory",   w=3.0, h=1.10, F=MEM_F, S=MEM_S, fs=28)
        error_mem  = rbox("Error Memory",  w=3.0, h=1.10, F=MEM_F, S=ERR_C, fs=28)
        coef_mem   = rbox("Coef. Memory",  w=3.0, h=1.10, F=MEM_F, S=K_C,   fs=28)
        fwd_pass   = rbox("Forward Pass",  w=3.2, h=1.10, F=BLK_F, S=BLK_S, fs=28)
        controller = rbox("Controller",    w=3.0, h=1.10, F=BLK_F, S=CTL_C, fs=28)
        rev_pass   = rbox("Reverse Pass",  w=3.2, h=1.10, F=BLK_F, S=BLK_S, fs=28)

        data_mem  .move_to([C[0], R[0], 0])
        error_mem .move_to([C[1], R[0], 0])
        coef_mem  .move_to([C[2], R[0], 0])
        fwd_pass  .move_to([C[0], R[1], 0])
        controller.move_to([C[1], R[1], 0])
        rev_pass  .move_to([C[2], R[1], 0])

        a1s = data_mem.get_edge_center(DOWN)
        a1e = fwd_pass.get_edge_center(UP)
        A1  = arr(a1s, a1e, X_C)

        a2s = fwd_pass.get_edge_center(RIGHT)
        a2e = error_mem.get_edge_center(LEFT)
        A2  = arr(a2s, a2e, ERR_C)

        a3s = error_mem.get_edge_center(RIGHT)
        a3e = rev_pass.get_edge_center(LEFT)
        A3  = arr(a3s, a3e, ERR_C)

        a4s = coef_mem.get_edge_center(DOWN) + LEFT  * 0.32
        a4e = rev_pass.get_edge_center(UP)   + LEFT  * 0.32
        A4  = arr(a4s, a4e, K_C)

        a5s = rev_pass.get_edge_center(UP)   + RIGHT * 0.32
        a5e = coef_mem.get_edge_center(DOWN) + RIGHT * 0.32
        A5  = arr(a5s, a5e, K_C)

        a6s = controller.get_edge_center(LEFT) + UP   * 0.16
        a6e = fwd_pass.get_edge_center(RIGHT)  + UP   * 0.16
        A6  = arr(a6s, a6e, CTL_C)

        a7s = fwd_pass.get_edge_center(RIGHT)  + DOWN * 0.16
        a7e = controller.get_edge_center(LEFT) + DOWN * 0.16
        A7  = arr(a7s, a7e, CTL_C)

        a8s = controller.get_edge_center(RIGHT) + UP   * 0.16
        a8e = rev_pass.get_edge_center(LEFT)    + UP   * 0.16
        A8  = arr(a8s, a8e, CTL_C)

        a9s = rev_pass.get_edge_center(LEFT)    + DOWN * 0.16
        a9e = controller.get_edge_center(RIGHT) + DOWN * 0.16
        A9  = arr(a9s, a9e, CTL_C)

        d1s = data_mem.get_edge_center(RIGHT)
        d1e = rev_pass.get_edge_center(UP) + LEFT * 0.65
        D1  = Arrow(d1s, d1e, buff=0.0, color=X_C, stroke_width=1.4,
                    tip_length=0.13, max_tip_length_to_length_ratio=0.45)
        D1.set_opacity(0.55)

        d2s = coef_mem.get_edge_center(LEFT)
        d2e = fwd_pass.get_edge_center(UP) + RIGHT * 0.65
        D2  = Arrow(d2s, d2e, buff=0.0, color=K_C, stroke_width=1.4,
                    tip_length=0.13, max_tip_length_to_length_ratio=0.45)
        D2.set_opacity(0.55)

        def albl_s(tex, col=DIM, fs=22):
            return MathTex(tex, font_size=fs, color=col)

        def mid(a, b):
            return (np.array(a) + np.array(b)) / 2

        L_A1  = albl_s(r"x_i,\; y_i", X_C).next_to(A1, LEFT, buff=0.10)
        L_A2  = albl_s(r"e_i",  ERR_C).move_to(mid(a2s, a2e) + UP  * 0.28 + LEFT  * 0.10)
        L_A3  = albl_s(r"e_i",  ERR_C).move_to(mid(a3s, a3e) + UP  * 0.28 + RIGHT * 0.10)
        L_A45 = albl_s(r"c_k",  K_C  ).next_to(VGroup(A4, A5), RIGHT, buff=0.10)
        L_A6  = albl_s(r"\mathrm{ctrl}",   CTL_C).move_to(mid(a6s, a6e) + UP   * 0.25)
        L_A7  = albl_s(r"\mathrm{status}", CTL_C).move_to(mid(a7s, a7e) + DOWN * 0.25)
        L_A8  = albl_s(r"\mathrm{ctrl}",   CTL_C).move_to(mid(a8s, a8e) + UP   * 0.25)
        L_A9  = albl_s(r"\mathrm{status}", CTL_C).move_to(mid(a9s, a9e) + DOWN * 0.25)
        L_D1  = albl_s(r"x_i", X_C).move_to(mid(d1s, d1e) + UP   * 0.28)
        L_D2  = albl_s(r"c_k", K_C).move_to(mid(d2s, d2e) + DOWN * 0.28)
        L_D1.set_opacity(0.6); L_D2.set_opacity(0.6)

        self.add(
            title,
            data_mem, error_mem, coef_mem,
            fwd_pass, controller, rev_pass,
            A1, A2, A3, A4, A5, A6, A7, A8, A9, D1, D2,
            L_A1, L_A2, L_A3, L_A45,
            L_A6, L_A7, L_A8, L_A9,
            L_D1, L_D2,
        )
