"""
Reverse pass animated data-flow.

Transition structure:
  1. Overview — all blocks, arrows, labels
  2. Per-sample gradient accumulation (shown for k=1, 3 samples):
       x dot → fp_power → x^k; error dot from error_mem;
       both → FMA error_accum → gradient reg (with feedback arc)
  3. Gradient complete → FMA coef_update:
       gradient + alpha + cur_coef arrive → updated coef → coef_mem
  4. Caption: repeat for k=0..3
"""

from manim import *

BG     = "#1e1e2e"
MEM_F  = "#1e3a2f";  MEM_S  = "#a6e3a1"
FMA_F  = "#1e1e40";  FMA_S  = "#cba6f7"
BLK_F  = "#25253a";  BLK_S  = "#89b4fa"
X_C    = "#89dceb"
ERR_C  = "#f38ba8"
K_C    = "#f9e2af"
POW_C  = "#cba6f7"
ALP_C  = "#89dceb"
GRAD_C = "#fab387"
LAB    = "#cdd6f4"
DIM    = "#585b70"

SLOW = 1.0   # global speed multiplier: >1 slows down, <1 speeds up


def rbox(label, w=2.2, h=0.85, F=BLK_F, S=BLK_S, fs=17):
    r = RoundedRectangle(corner_radius=0.12, width=w, height=h,
                         fill_color=F, fill_opacity=1,
                         stroke_color=S, stroke_width=2.5)
    t = Tex(rf"\textrm{{{label}}}", font_size=fs, color=LAB)
    t.move_to(r)
    return VGroup(r, t)


def fmabox(name, sub, w=2.6, h=0.90):
    r = RoundedRectangle(corner_radius=0.12, width=w, height=h,
                         fill_color=FMA_F, fill_opacity=1,
                         stroke_color=FMA_S, stroke_width=2.5)
    t1 = Tex(rf"\textrm{{{name}}}", font_size=15, color=LAB).move_to(r.get_center() + UP   * 0.19)
    t2 = MathTex(sub, font_size=13, color=FMA_S).move_to(r.get_center() + DOWN * 0.14)
    return VGroup(r, t1, t2)


def earrow(src, dst, sd=RIGHT, ed=LEFT, col=LAB, sw=2.5):
    return Arrow(src.get_edge_center(sd), dst.get_edge_center(ed),
                 buff=0.0, color=col, stroke_width=sw,
                 tip_length=0.17, max_tip_length_to_length_ratio=0.45)


def move_dot(start, end, col, r=0.12, rt=0.5):
    path = Line(start, end)
    dot  = Dot(radius=r, color=col).move_to(start)
    anim = MoveAlongPath(dot, path, run_time=rt * SLOW, rate_func=smooth)
    return dot, anim


class ReversePassFlow(MovingCameraScene):

    def construct(self):
        self.camera.background_color = BG
        self.camera.frame.save_state()

        # ══════════════════════════════════════════════════════════════════════
        # OVERVIEW LAYOUT
        #
        #   R[0]=2.2       [err_mem]       [alpha_box]
        #   R[1]=0.3  [data_mem] [fma_accum][fma_update][coef_mem]
        #   R[3]=-2.0 [fp_pow]   [grad_reg]
        #
        # data_mem/fp_pow share a left column; fma_accum/grad_reg share
        # a center column.  The feedback arc from grad_reg bows left into
        # the space between the two column groups — no overlap with fp_pow.
        #
        # Columns:  C[0]   C[1]   C[2]   C[3]
        # ══════════════════════════════════════════════════════════════════════
        C = [-5.0, -1.8, 2.2, 5.3]
        R = [2.2, 0.3, -1.0, -2.0]

        err_mem    = rbox("Error Memory",   w=2.0, h=0.85, F=MEM_F, S=ERR_C,  fs=15)
        data_mem   = rbox("Data Memory",   w=2.0, h=0.85, F=MEM_F, S=MEM_S,  fs=15)
        fp_pow     = rbox("Power Unit",    w=2.0, h=0.85, F=BLK_F, S=BLK_S,  fs=16)
        fma_accum  = fmabox("Gradient Accum.", r"x^k \cdot e + \mathrm{accum}", w=2.5)
        grad_reg   = rbox("Gradient Reg",  w=2.5, h=0.85, F=BLK_F, S=GRAD_C, fs=15)
        alpha_box  = rbox("",              w=1.5, h=0.75, F=BLK_F, S=ALP_C,  fs=15)
        fma_update = fmabox("Coef. Update", r"c_k - \alpha \cdot \nabla_k", w=2.5)
        coef_mem   = rbox("Coef. Memory",  w=2.0, h=0.85, F=MEM_F, S=MEM_S,  fs=15)

        # Left column: data_mem (main row) over fp_pow (bottom row)
        # Center column: err_mem (top) / fma_accum (main) / grad_reg (bottom)
        err_mem   .move_to([C[1], R[0], 0])
        data_mem  .move_to([C[0], R[0], 0])
        fp_pow    .move_to([C[0], R[1], 0])
        fma_accum .move_to([C[1], R[1], 0])
        grad_reg  .move_to([C[1], R[3], 0])
        grad_reg[1].move_to(grad_reg[0].get_top() + DOWN * 0.18)
        alpha_box .move_to([C[2], R[0], 0])
        fma_update.move_to([C[2], R[2], 0])
        coef_mem  .move_to([C[3], R[2], 0])

        # ── Replace alpha_box text with proper MathTex label ─────────────────
        alpha_box.remove(alpha_box[1])
        alpha_lbl = MathTex(r"\alpha", font_size=22, color=ALP_C)
        alpha_lbl.move_to(alpha_box[0])
        alpha_box.add(alpha_lbl)

        # ── Precompute arrow endpoints used in both overview and dot animation ─
        grad_start  = grad_reg  .get_edge_center(RIGHT)
        grad_end    = fma_update.get_edge_center(LEFT)  + DOWN * 0.2
        ck_r_start  = coef_mem  .get_edge_center(LEFT) + UP   * 0.22
        ck_r_end    = fma_update.get_edge_center(RIGHT) + UP  * 0.22
        ck_w_start  = fma_update.get_edge_center(RIGHT) + DOWN * 0.22
        ck_w_end    = coef_mem  .get_edge_center(LEFT)  + DOWN * 0.22

        # ── Arrows ────────────────────────────────────────────────────────────
        ov_arrows = VGroup(
            # err_mem → fma_accum (vertical down)
            earrow(err_mem, fma_accum, sd=DOWN, ed=UP, col=ERR_C),
            # data_mem → fp_pow (vertical down, same left column)
            earrow(data_mem, fp_pow, sd=DOWN, ed=UP, col=X_C),
            # fp_pow → fma_accum (diagonal up-right, crosses into center column)
            Arrow(fp_pow.get_edge_center(RIGHT),
                  fma_accum.get_edge_center(LEFT),
                  buff=0.0, color=POW_C, stroke_width=2,
                  tip_length=0.15, max_tip_length_to_length_ratio=0.45),
            # fma_accum → grad_reg (vertical down, same center column)
            earrow(fma_accum, grad_reg, sd=DOWN, ed=UP),
            # grad_reg feedback arc — bows left into the gap between columns;
            # fp_pow is in the same column but at a lower row, no intersection
            CurvedArrow(
                grad_reg.get_edge_center(LEFT),
                fma_accum.get_edge_center(LEFT),
                angle=-TAU / 5, color=GRAD_C, stroke_width=2, tip_length=0.14,
            ),
            # grad_reg → fma_update (diagonal up-right)
            Arrow(grad_start, grad_end,
                  buff=0.0, color=GRAD_C, stroke_width=2,
                  tip_length=0.15, max_tip_length_to_length_ratio=0.45),
            # alpha_box → fma_update (vertical down)
            earrow(alpha_box, fma_update, sd=DOWN, ed=UP, col=ALP_C),
            # coef_mem → fma_update (cur_coef read)
            Arrow(ck_r_start, ck_r_end,
                  buff=0.0, color=K_C, stroke_width=2,
                  tip_length=0.15, max_tip_length_to_length_ratio=0.45),
            # fma_update → coef_mem (updated coef write)
            Arrow(ck_w_start, ck_w_end,
                  buff=0.0, color=K_C, stroke_width=2,
                  tip_length=0.15, max_tip_length_to_length_ratio=0.45),
        )

        # ── Labels ────────────────────────────────────────────────────────────
        def _mid(p1, p2): return (p1 + p2) / 2

        x_mid   = _mid(data_mem.get_edge_center(DOWN),   fp_pow   .get_edge_center(UP))
        xk_mid  = _mid(fp_pow  .get_edge_center(RIGHT),
                       fma_accum.get_edge_center(LEFT) + DOWN * 0.2)
        e_mid   = _mid(err_mem .get_edge_center(DOWN),   fma_accum.get_edge_center(UP))
        grd_mid = _mid(grad_start, grad_end)
        alp_mid = _mid(alpha_box.get_edge_center(DOWN),  fma_update.get_edge_center(UP))

        ov_labels = VGroup(
            MathTex(r"e",        font_size=19, color=ERR_C ).next_to(e_mid,   RIGHT, buff=0.14),
            MathTex(r"x",        font_size=19, color=X_C   ).next_to(x_mid,   RIGHT, buff=0.14),
            MathTex(r"x^k",      font_size=19, color=POW_C ).move_to(xk_mid + UP * 0.28),
            MathTex(r"\nabla_k", font_size=18, color=GRAD_C).next_to(grd_mid, UP,    buff=0.14),
            MathTex(r"\alpha",   font_size=18, color=ALP_C ).next_to(alp_mid, RIGHT, buff=0.14),
            MathTex(r"c_k",      font_size=17, color=K_C   ).move_to(
                _mid(ck_r_start, ck_r_end) + UP * 0.2),
            MathTex(r"c_k'",     font_size=17, color=K_C   ).move_to(
                _mid(ck_w_start, ck_w_end) + DOWN * 0.2),
        )

        title = Text("Reverse Pass — Data Flow", font_size=26, color=LAB).to_edge(UP, buff=0.25)

        overview_all = VGroup(
            title, err_mem, data_mem, fp_pow, fma_accum,
            grad_reg, alpha_box, fma_update, coef_mem,
            ov_arrows, ov_labels,
        )

        # ── Phase 1: Overview appears ──────────────────────────────────────────
        self.play(FadeIn(title), run_time=0.5 * SLOW)
        self.play(
            LaggedStart(*[FadeIn(b, shift=UP * 0.1) for b in
                [err_mem, data_mem, fp_pow, fma_accum, grad_reg,
                 alpha_box, fma_update, coef_mem]],
                lag_ratio=0.12, run_time=1.8 * SLOW),
        )
        self.play(
            Create(ov_arrows, lag_ratio=0.06, run_time=1.4 * SLOW),
            FadeIn(ov_labels, run_time=0.8 * SLOW),
        )
        self.wait(0.5 * SLOW)

        # ── Alpha annotation: α encodes α₀ × 2/N ──────────────────────────────
        alpha_note = MathTex(
            r"\alpha \;=\; \alpha_0 \cdot \tfrac{2}{N}",
            font_size=20, color=ALP_C,
        )
        alpha_note.next_to(alpha_box, UP, buff=0.22)
        self.play(Indicate(alpha_box, color=ALP_C, scale_factor=1.25), run_time=0.5 * SLOW)
        self.play(FadeIn(alpha_note, shift=UP * 0.1), run_time=0.4 * SLOW)
        self.wait(1.0 * SLOW)
        self.play(FadeOut(alpha_note), run_time=0.35 * SLOW)
        self.wait(0.2 * SLOW)

        # ══════════════════════════════════════════════════════════════════════
        # For each k=0..3: fp_power zoom showing x^k, then full data-flow path
        # ══════════════════════════════════════════════════════════════════════
        all_step_defs = [
            (r"x^0", r"= 1",              "direct", POW_C),
            (r"x^1", r"= x",              "direct", POW_C),
            (r"x^2", r"= x^1 \times x",  "FMA",    POW_C),
            (r"x^3", r"= x^2 \times x",  "FMA",    POW_C),
        ]
        all_step_xs = [-2.8, -0.8, 1.2, 3.2]
        int_step_y  = 0.3
        int_out_y   = int_step_y - 1.55

        k_lbl = MathTex(r"k = 0 \;\Rightarrow\; x^0", font_size=18, color=POW_C)
        k_lbl.next_to(fp_pow, DOWN, buff=0.18)
        self.play(FadeIn(k_lbl, shift=UP * 0.1), run_time=0.4 * SLOW)
        overview_all.add(k_lbl)
        self.wait(0.2 * SLOW)

        for k in range(4):
            n = k + 1

            # Update k_lbl in the overview for k > 0
            if k > 0:
                new_k_lbl = MathTex(
                    rf"k = {k} \;\Rightarrow\; x^{k}",
                    font_size=18, color=POW_C,
                )
                new_k_lbl.next_to(fp_pow, DOWN, buff=0.18)
                self.play(Transform(k_lbl, new_k_lbl), run_time=0.4 * SLOW)
                self.wait(0.2 * SLOW)

            # ── x dot triggers zoom into fp_power ─────────────────────────
            xzoom, xzoom_anim = move_dot(data_mem.get_edge_center(DOWN),
                                          fp_pow.get_edge_center(UP), X_C, rt=0.4)
            self.play(FadeIn(xzoom), run_time=0.1 * SLOW)
            self.play(xzoom_anim)
            self.play(
                FadeOut(xzoom, target_position=fp_pow.get_center()),
                fp_pow[0].animate.set_stroke(color=X_C, width=4),
                run_time=0.3 * SLOW,
            )
            self.play(fp_pow[0].animate.set_stroke(color=BLK_S, width=2.5), run_time=0.2 * SLOW)
            self.wait(0.1 * SLOW)

            self.play(
                self.camera.frame.animate.move_to(fp_pow.get_center()).set_width(3.8),
                run_time=0.9 * SLOW, rate_func=smooth,
            )
            self.play(FadeOut(overview_all), run_time=0.4 * SLOW)
            self.camera.frame.restore()

            # ── fp_power interior for this k ──────────────────────────────
            int_title = Text("fp_power", font_size=32, color=BLK_S, weight=BOLD)
            int_title.to_edge(UP, buff=0.4)
            lbl_parts = r",\; ".join([rf"x^{i}" for i in range(n)])
            int_sub = Tex(
                rf"$k = {k}$: compute $" + lbl_parts + rf"$ — emit $x^{k}$",
                font_size=18, color=DIM,
            )
            int_sub.next_to(int_title, DOWN, buff=0.15)

            ix_box = rbox("x", w=1.0, h=0.75, F=MEM_F, S=X_C, fs=22)
            ix_box.move_to(LEFT * 5.5 + UP * 0.3)
            ix_in_lbl = Text("from\nmemory", font_size=12, color=DIM)
            ix_in_lbl.next_to(ix_box, DOWN, buff=0.1)

            int_x_to_steps = Arrow(
                ix_box.get_edge_center(RIGHT),
                [all_step_xs[0] - 0.95, int_step_y, 0],
                buff=0.0, color=X_C, stroke_width=2.5, tip_length=0.17,
            )

            step_boxes = []
            step_subs  = []
            for i in range(n):
                sup, eq, how, col = all_step_defs[i]
                br = RoundedRectangle(corner_radius=0.14, width=1.8, height=1.1,
                                      fill_color=BLK_F, fill_opacity=1,
                                      stroke_color=col, stroke_width=2)
                bt = MathTex(sup, font_size=22, color=col).move_to(br.get_center() + UP*0.15)
                bs = MathTex(eq,  font_size=15, color=LAB).move_to(br.get_center() + DOWN*0.22)
                box = VGroup(br, bt, bs).move_to([all_step_xs[i], int_step_y, 0])
                step_boxes.append(box)
                tag = Text(how, font_size=10, color=DIM).next_to(box, DOWN, buff=0.08).shift(RIGHT * 0.28)
                step_subs.append(tag)

            chain_arrows = []
            for i in range(n - 1):
                a = Arrow(step_boxes[i].get_edge_center(RIGHT),
                          step_boxes[i+1].get_edge_center(LEFT),
                          buff=0.06, color=DIM, stroke_width=2, tip_length=0.15)
                t = MathTex(r"\times x", font_size=15, color=DIM).next_to(a, UP, buff=0.06)
                chain_arrows.append(VGroup(a, t))

            x_feed = x_feed_lbl = None
            if n > 1:
                x_feed = DashedLine(
                    [all_step_xs[0], int_step_y + 0.85, 0],
                    [all_step_xs[n-1], int_step_y + 0.85, 0],
                    color=X_C, stroke_width=1.5, dash_length=0.14, dashed_ratio=0.5,
                )
                x_feed_lbl = Tex(r"$x$ available at each step", font_size=14, color=X_C)
                x_feed_lbl.next_to(x_feed, UP, buff=0.07)

            out_arrow = Arrow(
                [all_step_xs[k], int_step_y - 0.55, 0],
                [all_step_xs[k], int_out_y + 0.25,  0],
                buff=0.0, color=POW_C, stroke_width=2, tip_length=0.14,
            )
            out_val = Tex(rf"output: $x^{{{k}}}$", font_size=17, color=POW_C)
            out_val.move_to([all_step_xs[k], int_out_y, 0])

            self.play(FadeIn(int_title, shift=DOWN*0.15), FadeIn(int_sub, shift=DOWN*0.1), run_time=0.5 * SLOW)
            self.play(FadeIn(ix_box), FadeIn(ix_in_lbl), Create(int_x_to_steps), run_time=0.4 * SLOW)
            if n > 1:
                self.play(Create(x_feed), FadeIn(x_feed_lbl), run_time=0.4 * SLOW)
            self.wait(0.15 * SLOW)

            for i in range(n):
                self.play(FadeIn(step_boxes[i], shift=UP*0.1), run_time=0.42 * SLOW)
                self.play(FadeIn(step_subs[i]), run_time=0.2 * SLOW)
                if i < n - 1:
                    self.play(FadeIn(chain_arrows[i]), run_time=0.3 * SLOW)
                self.play(step_boxes[i][0].animate.set_stroke(color=X_C, width=4), run_time=0.25 * SLOW)
                if i == n - 1:
                    self.play(
                        GrowArrow(out_arrow),
                        step_boxes[i][0].animate.set_stroke(color=POW_C, width=2),
                        run_time=0.35 * SLOW,
                    )
                    self.play(FadeIn(out_val, scale=0.6), run_time=0.3 * SLOW)
                else:
                    self.play(step_boxes[i][0].animate.set_stroke(color=POW_C, width=2), run_time=0.2 * SLOW)

            self.wait(0.6 * SLOW)

            int_elems = [int_title, int_sub, ix_box, ix_in_lbl, int_x_to_steps,
                         *step_boxes, *step_subs, *chain_arrows, out_arrow, out_val]
            if n > 1:
                int_elems += [x_feed, x_feed_lbl]

            # ── Zoom out ──────────────────────────────────────────────────
            self.play(FadeOut(VGroup(*int_elems)), run_time=0.4 * SLOW)
            self.add(overview_all)
            self.camera.frame.move_to(fp_pow.get_center()).set_width(3.8)
            self.play(self.camera.frame.animate.restore(), run_time=0.9 * SLOW, rate_func=smooth)
            self.wait(0.3 * SLOW)

            # ── Full data-flow path for this k ────────────────────────────
            grad_strs = [
                rf"e_0 \cdot x^{k}",
                rf"\nabla_{{{k}}} = \textstyle\sum_i e_i x^{k}",
            ]
            cur_grad_lbl = None
            n_samples = 2

            for i in range(n_samples):
                # x dot: data_mem → fp_pow
                xd, xanim = move_dot(data_mem.get_edge_center(DOWN),
                                      fp_pow.get_edge_center(UP), X_C, rt=0.4)
                self.play(FadeIn(xd), run_time=0.1 * SLOW)
                self.play(xanim)
                self.play(
                    FadeOut(xd, target_position=fp_pow.get_center()),
                    fp_pow[0].animate.set_stroke(color=POW_C, width=4),
                    run_time=0.25 * SLOW,
                )
                self.play(fp_pow[0].animate.set_stroke(color=BLK_S, width=2.5), run_time=0.15 * SLOW)

                # x^k dot + error dot → fma_accum simultaneously
                xk_end = fma_accum.get_edge_center(LEFT)
                e_end  = fma_accum.get_edge_center(UP)
                xk_dot, xk_anim = move_dot(fp_pow .get_edge_center(RIGHT), xk_end, POW_C, rt=0.55)
                ed,     eanim   = move_dot(err_mem.get_edge_center(DOWN),   e_end,  ERR_C, rt=0.45)
                self.play(FadeIn(xk_dot), FadeIn(ed), run_time=0.1 * SLOW)
                self.play(xk_anim, eanim)
                self.play(
                    fma_accum[0].animate.set_stroke(color=GRAD_C, width=4),
                    FadeOut(xk_dot, target_position=fma_accum.get_center()),
                    FadeOut(ed,     target_position=fma_accum.get_center()),
                    run_time=0.25 * SLOW,
                )
                self.play(fma_accum[0].animate.set_stroke(color=FMA_S, width=2.5), run_time=0.15 * SLOW)

                # result dot: fma_accum → grad_reg
                rd, ranim = move_dot(fma_accum.get_edge_center(DOWN),
                                      grad_reg.get_edge_center(UP), GRAD_C, rt=0.4)
                self.play(FadeIn(rd), run_time=0.1 * SLOW)
                self.play(ranim)
                new_grad = MathTex(grad_strs[i], font_size=14, color=GRAD_C)
                new_grad.move_to(grad_reg.get_center() + DOWN * 0.12)
                max_w = grad_reg.width * 0.88
                if new_grad.width > max_w:
                    new_grad.scale_to_fit_width(max_w)
                if cur_grad_lbl is not None:
                    self.remove(cur_grad_lbl)
                self.play(
                    FadeOut(rd, target_position=grad_reg.get_center()),
                    grad_reg[0].animate.set_stroke(color=GRAD_C, width=3.5),
                    FadeIn(new_grad, scale=0.7),
                    run_time=0.35 * SLOW,
                )
                self.play(grad_reg[0].animate.set_stroke(color=GRAD_C, width=2), run_time=0.2 * SLOW)
                cur_grad_lbl = new_grad

                # feedback arc (not on last sample)
                if i < n_samples - 1:
                    fb_path = ArcBetweenPoints(
                        grad_reg.get_edge_center(LEFT),
                        fma_accum.get_edge_center(LEFT),
                        angle=-TAU / 5,
                    )
                    fb_dot = Dot(radius=0.09, color=GRAD_C).move_to(grad_reg.get_edge_center(LEFT))
                    self.play(FadeIn(fb_dot), run_time=0.1 * SLOW)
                    self.play(MoveAlongPath(fb_dot, fb_path, run_time=0.4 * SLOW, rate_func=smooth))
                    self.play(FadeOut(fb_dot, target_position=fma_accum.get_center()), run_time=0.15 * SLOW)

            self.play(Indicate(cur_grad_lbl, color=GRAD_C, scale_factor=1.15), run_time=0.5 * SLOW)
            self.wait(0.2 * SLOW)

            # Coefficient update: gradient + alpha + coef → fma_update → coef_mem
            gd, ganim = move_dot(grad_start, grad_end, GRAD_C, rt=0.5)
            self.play(FadeOut(cur_grad_lbl), FadeIn(gd), run_time=0.2 * SLOW)
            self.play(ganim)

            ad, aanim = move_dot(alpha_box.get_edge_center(DOWN),
                                  fma_update.get_edge_center(UP), ALP_C, rt=0.4)
            self.play(FadeIn(ad), run_time=0.1 * SLOW)
            self.play(aanim)

            cd, canim = move_dot(ck_r_start, ck_r_end, K_C, rt=0.4)
            self.play(FadeIn(cd), run_time=0.1 * SLOW)
            self.play(canim)

            self.play(
                fma_update[0].animate.set_stroke(color=K_C, width=4),
                FadeOut(gd, target_position=fma_update.get_center()),
                FadeOut(ad, target_position=fma_update.get_center()),
                FadeOut(cd, target_position=fma_update.get_center()),
                run_time=0.3 * SLOW,
            )
            self.play(fma_update[0].animate.set_stroke(color=FMA_S, width=2.5), run_time=0.2 * SLOW)

            ud, uanim = move_dot(ck_w_start, ck_w_end, K_C, rt=0.4)
            self.play(FadeIn(ud), run_time=0.1 * SLOW)
            self.play(uanim)
            self.play(
                FadeOut(ud, target_position=coef_mem.get_center()),
                Indicate(coef_mem[0], color=K_C, scale_factor=1.1),
                run_time=0.35 * SLOW,
            )
            self.wait(0.35 if k < 3 else 0.5)

        caption = Tex(
            r"Gradient $\nabla_k = \sum_i e_i \, x_i^k$ accumulated over all samples.\\",
            r"Repeat for $k = 0, 1, 2, 3$ to update every coefficient.",
            font_size=19, color=LAB,
        ).to_edge(DOWN, buff=0.22)
        self.play(FadeIn(caption, shift=UP * 0.1), run_time=0.6 * SLOW)
        self.play(FadeOut(k_lbl), run_time=0.3 * SLOW)
        self.wait(2.5 * SLOW)
        self.play(FadeOut(caption), run_time=0.4 * SLOW)
        self.wait(0.3 * SLOW)
