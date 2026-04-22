"""
Forward pass animated data-flow.

Transition structure:
  1. Overview scene — all blocks, x dot enters fp_power
  2. Camera zooms into fp_power → cross-fade to black
  3. Fresh fp_power interior scene — x iterates into x⁰…x³
  4. Cross-fade to black → camera at fp_power zoom position → zoom out to overview
  5. x^k / coef dots flow into FMA accum; polynomial builds in accumulate reg
  6. ŷ meets y at FMA error_calc → error written to memory
"""

from manim import *

BG     = "#1e1e2e"
MEM_F  = "#1e3a2f";  MEM_S  = "#a6e3a1"
FMA_F  = "#1e1e40";  FMA_S  = "#cba6f7"
REG_F  = "#25253a";  REG_S  = "#fab387"
BLK_F  = "#25253a";  BLK_S  = "#89b4fa"
X_C    = "#89dceb"   # cyan   – x data
Y_C    = "#a6e3a1"   # green  – y data
K_C    = "#f9e2af"   # yellow – coef / accumulated term
POW_C  = "#cba6f7"   # mauve  – power values
ERR_C  = "#f38ba8"   # red    – error
LAB    = "#cdd6f4"
DIM    = "#585b70"

SLOW = 1.0   # global speed multiplier: >1 slows down, <1 speeds up


# ── Helpers ────────────────────────────────────────────────────────────────────

def rbox(label, w=2.2, h=0.85, F=BLK_F, S=BLK_S, fs=17):
    r = RoundedRectangle(corner_radius=0.12, width=w, height=h,
                         fill_color=F, fill_opacity=1,
                         stroke_color=S, stroke_width=2.5)
    t = Tex(rf"\textrm{{{label}}}", font_size=fs, color=LAB)
    t.move_to(r)
    return VGroup(r, t)


def fmabox(name, sub, w=3.2, h=0.90):
    r = RoundedRectangle(corner_radius=0.12, width=w, height=h,
                         fill_color=FMA_F, fill_opacity=1,
                         stroke_color=FMA_S, stroke_width=2.5)
    t1 = Tex(rf"\textrm{{{name}}}", font_size=16, color=LAB).move_to(r.get_center() + UP   * 0.19)
    t2 = MathTex(sub, font_size=14, color=FMA_S).move_to(r.get_center() + DOWN * 0.14)
    return VGroup(r, t1, t2)


def earrow(src, dst, sd=RIGHT, ed=LEFT, col=LAB, sw=2.5):
    return Arrow(src.get_edge_center(sd), dst.get_edge_center(ed),
                 buff=0.0, color=col, stroke_width=sw,
                 tip_length=0.17, max_tip_length_to_length_ratio=0.45)


def move_dot(start, end, col, r=0.12, rt=0.65):
    path = Line(start, end)
    dot  = Dot(radius=r, color=col).move_to(start)
    anim = MoveAlongPath(dot, path, run_time=rt * SLOW, rate_func=smooth)
    return dot, anim


# ── Scene ──────────────────────────────────────────────────────────────────────

class ForwardPassFlow(MovingCameraScene):

    def construct(self):
        self.camera.background_color = BG
        self.camera.frame.save_state()

        # ══════════════════════════════════════════════════════════════════════
        # OVERVIEW LAYOUT
        # ══════════════════════════════════════════════════════════════════════
        # C[1]→C[3] tightened: was 3.3, now 1.8 (reduces middle gap by 1.5 units)
        # C[4] shifted in: was 6.2, now 4.9 (keeps err_mem clear of frame edge)
        C = [-5.5, -2.8, None, 1.8, 5.2]
        R = [2.4, 0.5, -0.5, -2.4]

        data_mem  = rbox("Data Memory",     w=2.0, h=1.3,  F=MEM_F, S=MEM_S, fs=16)
        fp_pow    = rbox("Power Unit",     w=2.1, h=0.85, F=BLK_F, S=BLK_S, fs=16)
        coef_mem  = rbox("Coef. Memory",   w=2.0, h=0.85, F=MEM_F, S=MEM_S, fs=16)
        fma_accum = fmabox("Poly. Accumulate", r"x^k \cdot c_k + \mathrm{accum}", w=3.1)
        accum_reg = rbox("Accumulator",    w=2.7, h=0.75, F=BLK_F, S=REG_S, fs=15)
        fma_err   = fmabox("Error Calc.",  r"y - \hat{y}", w=3.1)
        err_mem   = rbox("Error Memory",   w=2.0, h=0.85, F=MEM_F, S=MEM_S, fs=16)

        # coef_mem floats at the top, above fma_accum; all other blocks use R grid
        data_mem .move_to([C[0], R[2],  0])
        fp_pow   .move_to([C[1], R[1],  0])
        coef_mem .move_to([C[1], R[0],  0])   # top of diagram, same column as FMA stack
        fma_accum.move_to([C[3], R[1]+1.0,  0])
        accum_reg.move_to([C[3], R[2],  0])
        accum_reg[1].move_to(accum_reg[0].get_top() + DOWN * 0.18)
        fma_err  .move_to([C[3], R[3],  0])
        err_mem  .move_to([C[4], R[3],  0])

        ov_arrows = VGroup(
            earrow(data_mem,  fp_pow,    sd=RIGHT, ed=LEFT),
            earrow(fp_pow,    fma_accum, sd=RIGHT, ed=LEFT),
            # coef_mem is at top; arrow enters fma_accum from the left
            earrow(coef_mem,  fma_accum, sd=RIGHT,  ed=LEFT),
            earrow(fma_accum, accum_reg, sd=DOWN,  ed=UP),
            earrow(fma_err,   err_mem,   sd=RIGHT, ed=LEFT),
            # feedback loops around the RIGHT side of the FMA stack
            CurvedArrow(
                accum_reg.get_edge_center(RIGHT),
                fma_accum.get_edge_center(RIGHT),
                angle=TAU/3, color=REG_S, stroke_width=2, tip_length=0.14,
            ),
            Arrow(data_mem.get_edge_center(RIGHT), fma_err.get_edge_center(LEFT),
                  buff=0.0, color=Y_C, stroke_width=2,
                  tip_length=0.15, max_tip_length_to_length_ratio=0.45),
            earrow(accum_reg, fma_err, sd=DOWN, ed=UP),
        )

        # Labels placed above each arrow's midpoint (or beside for vertical/near arrows)
        def _mid(p1, p2): return (p1 + p2) / 2

        # "x": above midpoint of data_mem→fp_pow (diagonal)
        x_mid   = _mid(data_mem.get_edge_center(RIGHT), fp_pow.get_edge_center(LEFT))
        # "xᵏ": above midpoint of fp_pow→fma_accum (horizontal)
        xk_mid  = _mid(fp_pow.get_edge_center(RIGHT), fma_accum.get_edge_center(LEFT))
        # "coef[k]": nearer the source (coef_mem), 25% along the arrow, clear of the arrowhead
        coef_mid = _mid(coef_mem.get_edge_center(DOWN),
                        _mid(coef_mem.get_edge_center(DOWN), fma_accum.get_edge_center(LEFT)))
        # "ŷ": right of accum_reg→fma_err midpoint (vertical arrow)
        yh_mid  = _mid(accum_reg.get_edge_center(DOWN), fma_err.get_edge_center(UP))
        # "error": above fma_err's right edge (gap to err_mem is narrow)
        err_mid = fma_err.get_edge_center(RIGHT) + RIGHT * 0.3
        # "y": left of data_mem bottom so it clears the diagonal y-arrow
        y_pt    = data_mem.get_edge_center(RIGHT) + DOWN * 0.4 + RIGHT * 0.6

        ov_labels = VGroup(
            MathTex(r"x",          font_size=16, color=X_C  ).move_to(x_mid    + UP    * 0.22),
            MathTex(r"y",          font_size=16, color=Y_C  ).move_to(y_pt                    ),
            MathTex(r"c_k",        font_size=15, color=K_C  ).move_to(coef_mid + RIGHT  * 0.55 + UP * 0.15),
            MathTex(r"x^k",        font_size=16, color=POW_C).move_to(xk_mid   + UP     * 0.22),
            MathTex(r"\hat{y}",    font_size=16, color=K_C  ).move_to(yh_mid   + RIGHT  * 0.38),
            MathTex(r"\mathrm{error}", font_size=15, color=ERR_C).move_to(err_mid + UP  * 0.2),
        )
        title = Text("Forward Pass — Data Flow", font_size=26, color=LAB).to_edge(UP, buff=0.25)

        overview_all = VGroup(
            title, data_mem, fp_pow, coef_mem, fma_accum,
            accum_reg, fma_err, err_mem, ov_arrows, ov_labels,
        )

        # ── Phase 1: Overview appears ──────────────────────────────────────────
        self.play(FadeIn(title), run_time=0.5 * SLOW)
        self.play(
            LaggedStart(*[FadeIn(b, shift=UP*0.1) for b in
                [data_mem, fp_pow, coef_mem, fma_accum, accum_reg, fma_err, err_mem]],
                lag_ratio=0.12, run_time=1.8 * SLOW),
        )
        self.play(
            Create(ov_arrows, lag_ratio=0.06, run_time=1.4 * SLOW),
            FadeIn(ov_labels, run_time=0.8 * SLOW),
        )
        self.wait(0.4 * SLOW)

        # ── Phase 2: x dot travels from data_mem into fp_power ─────────────────
        xd, xanim = move_dot(data_mem.get_edge_center(RIGHT),
                             fp_pow.get_edge_center(LEFT), X_C, rt=0.75)
        self.play(FadeIn(xd), run_time=0.1 * SLOW)
        self.play(xanim)
        self.play(
            FadeOut(xd, target_position=fp_pow.get_center()),
            fp_pow[0].animate.set_stroke(color=X_C, width=4),
            run_time=0.3 * SLOW,
        )
        self.play(fp_pow[0].animate.set_stroke(color=BLK_S, width=2.5), run_time=0.2 * SLOW)
        self.wait(0.2 * SLOW)

        # ══════════════════════════════════════════════════════════════════════
        # ZOOM-IN TRANSITION  →  fp_power interior
        # ══════════════════════════════════════════════════════════════════════

        # Camera zooms into fp_power
        self.play(
            self.camera.frame.animate
                .move_to(fp_pow.get_center())
                .set_width(3.8),
            run_time=1.0 * SLOW, rate_func=smooth,
        )
        # Fade out all overview elements while zoomed in
        self.play(FadeOut(overview_all), run_time=0.4 * SLOW)

        # Snap camera back to default (nothing visible)
        self.camera.frame.restore()

        # ══════════════════════════════════════════════════════════════════════
        # fp_power INTERIOR SCENE  (centred on default camera)
        # ══════════════════════════════════════════════════════════════════════

        # Title bar
        int_title = Text("fp_power", font_size=32, color=BLK_S, weight=BOLD)
        int_title.to_edge(UP, buff=0.4)
        int_sub   = Tex(r"Given $x$, iteratively compute $x^0,\; x^1,\; x^2,\; x^3$",
                        font_size=18, color=DIM)
        int_sub.next_to(int_title, DOWN, buff=0.15)

        # ── x input box ───────────────────────────────────────────────────────
        x_box = rbox("x", w=1.0, h=0.75, F=MEM_F, S=X_C, fs=22)
        x_box.move_to(LEFT * 5.5 + UP * 0.3)
        x_in_lbl = Text("from\nmemory", font_size=12, color=DIM)
        x_in_lbl.next_to(x_box, DOWN, buff=0.1)

        # ── Four step boxes ────────────────────────────────────────────────────
        #   k=0: output 1  (no multiply needed)
        #   k=1: output x  (no multiply needed)
        #   k=2: prev × x = x²
        #   k=3: prev × x = x³
        step_defs = [
            (r"x^0",  r"= 1",                "direct",   POW_C),
            (r"x^1",  r"= x",                "direct",   POW_C),
            (r"x^2",  r"= x^1 \times x",     "FMA",      POW_C),
            (r"x^3",  r"= x^2 \times x",     "FMA",      POW_C),
        ]
        step_xs = [-2.8, -0.8, 1.2, 3.2]
        step_y  = 0.3

        step_boxes  = []
        step_subs   = []
        step_badges = []   # output value indicators

        for i, (sup, eq, how, col) in enumerate(step_defs):
            # Main box
            br = RoundedRectangle(corner_radius=0.14, width=1.7, height=1.1,
                                  fill_color=BLK_F, fill_opacity=1,
                                  stroke_color=col, stroke_width=2)
            bt = MathTex(sup, font_size=22, color=col).move_to(br.get_center() + UP*0.15)
            bs = MathTex(eq,  font_size=15, color=LAB).move_to(br.get_center() + DOWN*0.22)
            box = VGroup(br, bt, bs).move_to([step_xs[i], step_y, 0])
            step_boxes.append(box)
            # "direct" / "FMA" tag
            tag = Text(how, font_size=10, color=DIM).next_to(box, DOWN, buff=0.08).shift(RIGHT * 0.28)
            step_subs.append(tag)

        # ×x connectors between consecutive step boxes
        mul_connectors = []
        for i in range(3):
            a = Arrow(step_boxes[i].get_edge_center(RIGHT),
                      step_boxes[i+1].get_edge_center(LEFT),
                      buff=0.06, color=DIM, stroke_width=2, tip_length=0.15)
            t = MathTex(r"\times x", font_size=15, color=DIM).next_to(a, UP, buff=0.06)
            mul_connectors.append(VGroup(a, t))

        # Output flow arrows below each box + value label
        out_y = step_y - 1.55
        out_arrows = []
        out_vals   = []
        for i, (sup, _, _, col) in enumerate(step_defs):
            oa = Arrow([step_xs[i], step_y - 0.55, 0],
                       [step_xs[i], out_y + 0.25, 0],
                       buff=0.0, color=col, stroke_width=2, tip_length=0.14)
            ov = Tex(rf"output: ${sup}$", font_size=17, color=col)
            ov.move_to([step_xs[i], out_y, 0])
            out_arrows.append(oa)
            out_vals.append(ov)

        # x arrow from x_box to first usable step
        x_to_steps = Arrow(
            x_box.get_edge_center(RIGHT),
            [step_xs[0] - 0.9, step_y, 0],
            buff=0.0, color=X_C, stroke_width=2.5, tip_length=0.17,
        )
        # horizontal feed line from x_box to underpin mul_connectors
        x_feed = DashedLine(
            [step_xs[0], step_y + 0.85, 0],
            [step_xs[3], step_y + 0.85, 0],
            color=X_C, stroke_width=1.5, dash_length=0.14, dashed_ratio=0.5,
        )
        x_feed_lbl = Tex(r"$x$ available at each step", font_size=14, color=X_C)
        x_feed_lbl.next_to(x_feed, UP, buff=0.07)

        # ── Fade in title and x input ──────────────────────────────────────────
        self.play(
            FadeIn(int_title, shift=DOWN*0.15),
            FadeIn(int_sub,   shift=DOWN*0.1),
            run_time=0.6 * SLOW,
        )
        self.play(FadeIn(x_box), FadeIn(x_in_lbl), Create(x_to_steps), run_time=0.5 * SLOW)
        self.play(Create(x_feed), FadeIn(x_feed_lbl), run_time=0.4 * SLOW)
        self.wait(0.2 * SLOW)

        # ── Animate each step appearing and emitting its value ─────────────────
        for i in range(4):
            # Step box fades in with a highlight
            self.play(FadeIn(step_boxes[i], shift=UP*0.1), run_time=0.42 * SLOW)
            self.play(FadeIn(step_subs[i]), run_time=0.2 * SLOW)
            if i < 3:
                self.play(FadeIn(mul_connectors[i]), run_time=0.3 * SLOW)
            # Output: arrow then value
            self.play(
                GrowArrow(out_arrows[i]),
                step_boxes[i][0].animate.set_stroke(color=X_C, width=4),
                run_time=0.35 * SLOW,
            )
            self.play(
                FadeIn(out_vals[i], scale=0.6),
                step_boxes[i][0].animate.set_stroke(color=POW_C, width=2),
                run_time=0.3 * SLOW,
            )

        self.wait(0.6 * SLOW)

        interior_grp = VGroup(
            int_title, int_sub, x_box, x_in_lbl, x_to_steps,
            x_feed, x_feed_lbl,
            *step_boxes, *step_subs, *mul_connectors, *out_arrows, *out_vals,
        )

        # ══════════════════════════════════════════════════════════════════════
        # ZOOM-OUT TRANSITION  ←  back to overview
        # ══════════════════════════════════════════════════════════════════════

        # Fade out interior
        self.play(FadeOut(interior_grp), run_time=0.4 * SLOW)

        # Re-add overview and position camera at fp_power zoom
        self.add(overview_all)
        self.camera.frame.move_to(fp_pow.get_center()).set_width(3.8)

        # Zoom back out to full overview
        self.play(
            self.camera.frame.animate.restore(),
            run_time=1.3 * SLOW, rate_func=smooth,
        )
        self.wait(0.4 * SLOW)

        # ══════════════════════════════════════════════════════════════════════
        # ACCUMULATE ŷ TERM BY TERM
        # ══════════════════════════════════════════════════════════════════════
        poly_strs = [
            r"c_0",
            r"c_0 + c_1 x",
            r"c_0 + c_1 x + c_2 x^2",
            r"\hat{y} = c_0 + c_1 x + c_2 x^2 + c_3 x^3",
        ]
        pow_strs  = [r"x^0", r"x^1", r"x^2", r"x^3"]
        coef_strs = [r"c_0", r"c_1", r"c_2", r"c_3"]

        cur_poly_lbl = None

        for i in range(4):
            xk_dot = Dot(radius=0.12, color=POW_C).move_to(fp_pow.get_edge_center(RIGHT))
            ck_dot = Dot(radius=0.10, color=K_C  ).move_to(coef_mem.get_edge_center(RIGHT))

            emit_lbl = MathTex(pow_strs[i],  font_size=16, color=POW_C).next_to(fp_pow,   RIGHT, buff=0.1)
            coef_lbl = MathTex(coef_strs[i], font_size=16, color=K_C  ).next_to(coef_mem, RIGHT, buff=0.1)

            self.play(FadeIn(xk_dot), FadeIn(ck_dot),
                      FadeIn(emit_lbl), FadeIn(coef_lbl), run_time=0.15 * SLOW)
            self.play(
                MoveAlongPath(xk_dot, Line(fp_pow.get_edge_center(RIGHT),
                                           fma_accum.get_edge_center(LEFT)),
                              run_time=0.6 * SLOW, rate_func=smooth),
                MoveAlongPath(ck_dot, Line(coef_mem.get_edge_center(RIGHT),
                                           fma_accum.get_edge_center(LEFT)),
                              run_time=0.6 * SLOW, rate_func=smooth),
            )
            self.play(
                fma_accum[0].animate.set_stroke(color=K_C, width=4),
                FadeOut(xk_dot, target_position=fma_accum.get_center()),
                FadeOut(ck_dot, target_position=fma_accum.get_center()),
                FadeOut(emit_lbl), FadeOut(coef_lbl),
                run_time=0.25 * SLOW,
            )
            self.play(fma_accum[0].animate.set_stroke(color=FMA_S, width=2.5), run_time=0.15 * SLOW)

            res_dot, res_anim = move_dot(fma_accum.get_edge_center(DOWN),
                                         accum_reg.get_edge_center(UP), K_C, rt=0.55)
            self.play(FadeIn(res_dot), run_time=0.1 * SLOW)
            self.play(res_anim)

            new_lbl = MathTex(poly_strs[i], font_size=15, color=K_C)
            new_lbl.move_to(accum_reg.get_center() + DOWN * 0.12)
            max_w = accum_reg.width * 0.88
            if new_lbl.width > max_w:
                new_lbl.scale_to_fit_width(max_w)
            if cur_poly_lbl is not None:
                self.remove(cur_poly_lbl)
            self.play(
                FadeOut(res_dot, target_position=accum_reg.get_center()),
                accum_reg[0].animate.set_stroke(color=K_C, width=3.5),
                FadeIn(new_lbl, scale=0.7),
                run_time=0.35 * SLOW,
            )
            self.play(accum_reg[0].animate.set_stroke(color=REG_S, width=2), run_time=0.2 * SLOW)
            cur_poly_lbl = new_lbl

            if i < 3:
                fb = CubicBezier(
                    accum_reg.get_edge_center(RIGHT),
                    accum_reg.get_edge_center(RIGHT) + RIGHT * 1.0,
                    fma_accum.get_edge_center(RIGHT)  + RIGHT * 1.0,
                    fma_accum.get_edge_center(RIGHT),
                )
                fb_dot = Dot(radius=0.09, color=REG_S).move_to(accum_reg.get_edge_center(RIGHT))
                self.play(FadeIn(fb_dot), run_time=0.1 * SLOW)
                self.play(MoveAlongPath(fb_dot, fb, run_time=0.5 * SLOW, rate_func=smooth))
                self.play(FadeOut(fb_dot, target_position=fma_accum.get_center()), run_time=0.15 * SLOW)

        self.play(Indicate(cur_poly_lbl, color=K_C, scale_factor=1.15), run_time=0.5 * SLOW)
        self.wait(0.3 * SLOW)

        # ══════════════════════════════════════════════════════════════════════
        # ERROR = y − ŷ
        # ══════════════════════════════════════════════════════════════════════

        # ŷ travels down to fma_err
        yhat_dot, yhat_anim = move_dot(accum_reg.get_edge_center(DOWN),
                                        fma_err.get_edge_center(UP), K_C, rt=0.6)
        self.play(FadeOut(cur_poly_lbl), FadeIn(yhat_dot))
        self.play(yhat_anim)

        # y travels from data_mem to fma_err
        yd, yanim = move_dot(data_mem.get_edge_center(DOWN),
                             fma_err.get_edge_center(LEFT), Y_C, rt=0.75)
        self.play(FadeIn(yd), yanim)

        y_lbl  = Tex(r"$y$  (original)",       font_size=15, color=Y_C).next_to(fma_err.get_edge_center(LEFT) - 0.5, DOWN * 0.2, buff=0.2)
        yh_lbl = Tex(r"$\hat{y}$  (computed)", font_size=15, color=K_C).next_to(fma_err.get_edge_center(UP) + 0.2, RIGHT, buff=0.12)
        self.play(FadeIn(y_lbl), FadeIn(yh_lbl), run_time=0.3 * SLOW)
        self.wait(0.3 * SLOW)

        self.play(
            fma_err[0].animate.set_stroke(color=ERR_C, width=4),
            FadeOut(yd, target_position=fma_err.get_center()),
            FadeOut(yhat_dot, target_position=fma_err.get_center()),
            FadeOut(y_lbl), FadeOut(yh_lbl),
            run_time=0.35 * SLOW,
        )
        self.play(fma_err[0].animate.set_stroke(color=FMA_S, width=2.5), run_time=0.2 * SLOW)

        err_dot, err_anim = move_dot(fma_err.get_edge_center(RIGHT),
                                      err_mem.get_edge_center(LEFT), ERR_C, rt=0.6)
        self.play(FadeIn(err_dot), run_time=0.15 * SLOW)
        self.play(err_anim)
        self.play(
            FadeOut(err_dot, target_position=err_mem.get_center()),
            Indicate(err_mem[0], color=ERR_C, scale_factor=1.1),
            run_time=0.35 * SLOW,
        )

        caption = Tex(
            r"$\mathrm{error} = y - \hat{y}$  stored for each sample\\",
            r"Reverse pass uses these errors to update coefficients.",
            font_size=19, color=LAB,
        ).to_edge(DOWN, buff=0.22)
        self.play(FadeIn(caption, shift=UP*0.1), run_time=0.6 * SLOW)
        self.wait(2.0 * SLOW)
        self.play(FadeOut(caption), run_time=0.4 * SLOW)
        self.wait(0.3 * SLOW)
