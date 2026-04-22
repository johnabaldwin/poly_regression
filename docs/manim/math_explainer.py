"""
Polynomial Regression — Math Explainer
Narration-ready: linear regression -> generalisation -> gradient descent.
Each section has long pauses so you can speak over it.
"""
from manim import *

BG     = "#1e1e2e"
LAB    = "#cdd6f4"
DIM    = "#585b70"
X_C    = "#89dceb"   # cyan     - input x
Y_C    = "#a6e3a1"   # green    - actual y
K_C    = "#f9e2af"   # yellow   - coefficients / predicted y-hat
ERR_C  = "#f38ba8"   # red      - error
GRAD_C = "#cba6f7"   # mauve    - gradient
ALP_C  = "#b4befe"   # lavender - alpha / step size
HL_C   = "#fab387"   # orange   - loss


SLOW = 1 / 0.7   # play at 70% speed → every duration × ~1.43


class MathExplainer(Scene):

    # ── tiny helpers ──────────────────────────────────────────────────────
    def fi(self, *m, rt=1.0):
        self.play(*[FadeIn(x) for x in m], run_time=rt * SLOW)

    def fo(self, *m, rt=0.9):
        self.play(*[FadeOut(x) for x in m], run_time=rt * SLOW)

    def wr(self, m, rt=2.0):
        self.play(Write(m), run_time=rt * SLOW)

    def p(self, t=5.0):
        self.wait(t * SLOW)

    def sec_title(self, text):
        t = Text(text, font_size=28, color=LAB, weight=BOLD)
        t.to_edge(UP, buff=0.35)
        return t

    def note(self, tex_str, fs=25):
        return Tex(tex_str, font_size=fs, color=LAB)

    def dim_note(self, tex_str, fs=22):
        return Tex(tex_str, font_size=fs, color=DIM)

    # ── construct ─────────────────────────────────────────────────────────
    def construct(self):
        self.camera.background_color = BG

        # ═══════════════════════════════════════════════════════════════════
        # TITLE
        # ═══════════════════════════════════════════════════════════════════
        title = Text("Polynomial Regression",
                     font_size=52, color=LAB, weight=BOLD)
        sub = Text("Gradient Descent: From Linear to Polynomial",
                   font_size=23, color=DIM)
        sub.next_to(title, DOWN, buff=0.45)

        self.play(FadeIn(title, shift=UP * 0.2), run_time=1.5 * SLOW)
        self.play(FadeIn(sub), run_time=1.0 * SLOW)
        self.p(6.0)
        self.fo(title, sub)
        self.p(0.4)

        # ═══════════════════════════════════════════════════════════════════
        # 1.  THE LINEAR MODEL
        # ═══════════════════════════════════════════════════════════════════
        s1 = self.sec_title("1.  The Linear Model")
        self.fi(s1, rt=0.8)
        self.p(1.5)

        intro1 = self.note(
            r"Start simple: fit a \textit{straight line} through data points "
            r"$(x_i,\; y_i)$.")
        intro1.next_to(s1, DOWN, buff=0.6)
        self.fi(intro1)
        self.p(4.5)

        # ── scatter plot (right half of frame) ────────────────────────────
        ax = Axes(
            x_range=[0, 4.2, 1], y_range=[0, 5.5, 1],
            x_length=3.6, y_length=2.8,
            axis_config={"color": DIM, "stroke_width": 1.5,
                         "include_tip": False},
        ).shift(RIGHT * 2.9 + DOWN * 1.4)

        data_pts = [(0.4, 0.9), (0.9, 1.7), (1.4, 2.2), (2.0, 3.0),
                    (2.5, 3.6), (3.0, 4.1), (3.5, 4.7)]
        scatter = VGroup(*[
            Dot(ax.c2p(x, y), radius=0.07, color=X_C)
            for x, y in data_pts
        ])
        fit_line = ax.plot(lambda x: 0.6 + 1.2 * x,
                           x_range=[0.2, 3.9], color=K_C, stroke_width=2.5)
        x_lab = ax.get_x_axis_label(MathTex("x", color=X_C, font_size=20))
        y_lab = ax.get_y_axis_label(MathTex("y", color=Y_C, font_size=20))

        self.play(Create(ax), FadeIn(x_lab), FadeIn(y_lab), run_time=1.0 * SLOW)
        self.play(LaggedStart(*[FadeIn(d) for d in scatter], lag_ratio=0.12),
                  run_time=1.3 * SLOW)
        self.p(2.0)
        self.play(Create(fit_line), run_time=1.2 * SLOW)
        self.p(3.0)

        # ── linear equation (left half) ───────────────────────────────────
        m1 = MathTex(r"\hat{y}_i", r"=", r"c_0", r"+", r"c_1", r"x_i",
                     font_size=52)
        m1[0].set_color(K_C)
        m1[2].set_color(K_C)
        m1[4].set_color(K_C)
        m1[5].set_color(X_C)
        m1.next_to(intro1, DOWN, buff=0.8).shift(LEFT * 1.6)
        self.wr(m1)
        self.p(5.5)

        # ── annotate intercept and slope ──────────────────────────────────
        br_c0 = Brace(m1[2], DOWN, color=DIM, buff=0.08)
        lb_c0 = Tex(r"intercept", font_size=19, color=K_C)
        lb_c0.next_to(br_c0, DOWN, buff=0.06)

        br_c1x = Brace(VGroup(m1[4], m1[5]), DOWN, color=DIM, buff=0.08)
        lb_c1x = Tex(r"slope $\times\, x_i$", font_size=19, color=K_C)
        lb_c1x.next_to(br_c1x, DOWN, buff=0.06)

        self.play(GrowFromCenter(br_c0), FadeIn(lb_c0), run_time=1.0 * SLOW)
        self.p(3.5)
        self.play(GrowFromCenter(br_c1x), FadeIn(lb_c1x), run_time=1.0 * SLOW)
        self.p(5.0)

        # ── highlight one residual on the scatter ─────────────────────────
        xi, yi_act = 2.5, 3.6
        yi_hat = 0.6 + 1.2 * xi
        p_act = ax.c2p(xi, yi_act)
        p_hat = ax.c2p(xi, yi_hat)
        d_act = Dot(p_act, radius=0.10, color=Y_C)
        d_hat = Dot(p_hat, radius=0.10, color=K_C)
        res   = DashedLine(p_hat, p_act, color=ERR_C, stroke_width=2.2)
        e_lbl = MathTex(r"e_i", font_size=22, color=ERR_C)
        e_lbl.next_to(res, RIGHT, buff=0.1)

        self.play(FadeIn(d_act), FadeIn(d_hat), run_time=0.7 * SLOW)
        self.play(Create(res), FadeIn(e_lbl), run_time=1.0 * SLOW)
        self.p(5.0)

        self.fo(s1, intro1, ax, scatter, fit_line, x_lab, y_lab,
                m1, br_c0, lb_c0, br_c1x, lb_c1x, d_act, d_hat, res, e_lbl)
        self.p(0.4)

        # ═══════════════════════════════════════════════════════════════════
        # 2.  PREDICTION ERROR
        # ═══════════════════════════════════════════════════════════════════
        s2 = self.sec_title("2.  Prediction Error")
        self.fi(s2, rt=0.8)
        self.p(1.5)

        n2a = self.note(
            r"For each sample $i$: we measure the error between "
            r"the actual $y_i$ and our prediction $\hat{y}_i$.")
        n2a.next_to(s2, DOWN, buff=0.6)
        self.fi(n2a)
        self.p(5.0)

        # ŷ_i = c_0 + c_1 x_i  (reminder)
        pred = MathTex(r"\hat{y}_i", r"=", r"c_0", r"+", r"c_1", r"x_i",
                       font_size=46)
        pred[0].set_color(K_C)
        pred[2].set_color(K_C); pred[4].set_color(K_C); pred[5].set_color(X_C)
        pred.next_to(n2a, DOWN, buff=0.65)
        self.wr(pred)
        self.p(5.0)

        # e_i = y_i - ŷ_i
        err_def = MathTex(r"e_i", r"=", r"y_i", r"-", r"\hat{y}_i",
                          font_size=56)
        err_def[0].set_color(ERR_C)
        err_def[2].set_color(Y_C)
        err_def[4].set_color(K_C)
        err_def.next_to(pred, DOWN, buff=0.7)
        self.wr(err_def)
        self.p(6.0)

        n2b = self.dim_note(
            r"$e_i > 0$: we undershot.\quad "
            r"$e_i < 0$: we overshot.\quad "
            r"Goal: drive all $e_i$ toward 0.")
        n2b.next_to(err_def, DOWN, buff=0.5)
        self.fi(n2b)
        self.p(6.0)

        self.fo(s2, n2a, pred, err_def, n2b)
        self.p(0.4)

        # ═══════════════════════════════════════════════════════════════════
        # 3.  LOSS FUNCTION
        # ═══════════════════════════════════════════════════════════════════
        s3 = self.sec_title("3.  The Loss Function")
        self.fi(s3, rt=0.8)
        self.p(1.5)

        n3a = self.note(
            r"We need a single number that summarises how wrong we are "
            r"across \textit{all} $N$ samples.")
        n3a.next_to(s3, DOWN, buff=0.6)
        self.fi(n3a)
        self.p(5.0)

        n3b = self.note(r"Use \textbf{Mean Squared Error} (MSE):")
        n3b.next_to(n3a, DOWN, buff=0.5)
        self.fi(n3b)
        self.p(3.0)

        # L = (1/N) sum (y_i - yhat_i)^2
        loss1 = MathTex(
            r"\mathcal{L}", r"=",
            r"\frac{1}{N}", r"\sum_{i=1}^{N}",
            r"\bigl(", r"y_i", r"-", r"\hat{y}_i", r"\bigr)^{\!2}",
            font_size=48,
        )
        loss1[0].set_color(HL_C)
        loss1[5].set_color(Y_C)
        loss1[7].set_color(K_C)
        loss1.next_to(n3b, DOWN, buff=0.7)
        self.wr(loss1, rt=2.2)
        self.p(6.0)

        # substitute e_i
        n3c = self.dim_note(r"Substitute $e_i = y_i - \hat{y}_i$:")
        n3c.next_to(loss1, DOWN, buff=0.45)
        self.fi(n3c)
        self.p(2.5)

        loss2 = MathTex(
            r"\mathcal{L}", r"=",
            r"\frac{1}{N}", r"\sum_{i=1}^{N}", r"e_i^{\,2}",
            font_size=48,
        )
        loss2[0].set_color(HL_C)
        loss2[4].set_color(ERR_C)
        loss2.move_to(loss1)

        self.play(FadeOut(loss1), FadeOut(n3c), run_time=0.6 * SLOW)
        self.wr(loss2, rt=1.8)
        self.p(6.0)

        n3d = self.dim_note(
            r"Squaring ensures errors of opposite sign don't cancel, "
            r"and penalises large errors more.")
        n3d.next_to(loss2, DOWN, buff=0.5)
        self.fi(n3d)
        self.p(6.0)

        self.fo(s3, n3a, n3b, loss2, n3d)
        self.p(0.4)

        # ═══════════════════════════════════════════════════════════════════
        # 4.  GRADIENT DESCENT — LINEAR CASE
        # ═══════════════════════════════════════════════════════════════════
        s4 = self.sec_title("4.  Gradient Descent (Linear Case)")
        self.fi(s4, rt=0.8)
        self.p(1.5)

        n4a = self.note(
            r"To minimise $\mathcal{L}$, compute how it changes "
            r"with respect to each coefficient.")
        n4a.next_to(s4, DOWN, buff=0.6)
        self.fi(n4a)
        self.p(5.0)

        # gradient for c0
        g0 = MathTex(
            r"\frac{\partial \mathcal{L}}{\partial c_0}", r"=",
            r"-\frac{2}{N}", r"\sum_{i=1}^{N}", r"e_i",
            font_size=44,
        )
        g0[0].set_color(GRAD_C)
        g0[2].set_color(GRAD_C)
        g0[4].set_color(ERR_C)
        g0.next_to(n4a, DOWN, buff=0.7)
        self.wr(g0)
        self.p(6.0)

        # label: x_i^0 = 1
        br_g0 = Brace(g0[4], DOWN, color=DIM, buff=0.07)
        lb_g0 = Tex(r"$= e_i \cdot x_i^0 = e_i \cdot 1$",
                    font_size=19, color=DIM)
        lb_g0.next_to(br_g0, DOWN, buff=0.06)
        self.play(GrowFromCenter(br_g0), FadeIn(lb_g0), run_time=1.0 * SLOW)
        self.p(4.0)
        self.fo(br_g0, lb_g0, rt=0.5)

        # gradient for c1
        g1 = MathTex(
            r"\frac{\partial \mathcal{L}}{\partial c_1}", r"=",
            r"-\frac{2}{N}", r"\sum_{i=1}^{N}", r"e_i", r"\,x_i",
            font_size=44,
        )
        g1[0].set_color(GRAD_C)
        g1[2].set_color(GRAD_C)
        g1[4].set_color(ERR_C)
        g1[5].set_color(X_C)
        g1.next_to(g0, DOWN, buff=0.6)
        self.wr(g1)
        self.p(6.0)

        # label: x_i^1 = x_i
        br_g1 = Brace(VGroup(g1[4], g1[5]), DOWN, color=DIM, buff=0.07)
        lb_g1 = Tex(r"$= e_i \cdot x_i^1$", font_size=19, color=DIM)
        lb_g1.next_to(br_g1, DOWN, buff=0.06)
        self.play(GrowFromCenter(br_g1), FadeIn(lb_g1), run_time=1.0 * SLOW)
        self.p(4.0)
        self.fo(br_g1, lb_g1, rt=0.5)

        # spot the pattern
        n4b = self.dim_note(
            r"Pattern: coefficient $c_k$ gets gradient $-\tfrac{2}{N}\sum e_i \cdot x_i^k$")
        n4b.next_to(g1, DOWN, buff=0.5)
        self.fi(n4b)
        self.play(Indicate(g1[5], color=X_C, scale_factor=1.5), run_time=1.0 * SLOW)
        self.p(6.0)

        self.fo(s4, n4a, g0, g1, n4b)
        self.p(0.4)

        # ═══════════════════════════════════════════════════════════════════
        # 5.  THE UPDATE RULE
        # ═══════════════════════════════════════════════════════════════════
        s5 = self.sec_title("5.  The Update Rule")
        self.fi(s5, rt=0.8)
        self.p(1.5)

        n5a = self.note(
            r"Nudge each coefficient \textit{against} its gradient "
            r"by a small step size $\alpha$:")
        n5a.next_to(s5, DOWN, buff=0.6)
        self.fi(n5a)
        self.p(5.0)

        # c_0 update
        u0 = MathTex(
            r"c_0", r"\;\leftarrow\;", r"c_0", r"-",
            r"\alpha", r"\cdot",
            r"\frac{\partial \mathcal{L}}{\partial c_0}",
            font_size=46,
        )
        u0[0].set_color(K_C); u0[2].set_color(K_C)
        u0[4].set_color(ALP_C); u0[6].set_color(GRAD_C)
        u0.next_to(n5a, DOWN, buff=0.7)
        self.wr(u0)
        self.p(5.0)

        # c_1 update
        u1 = MathTex(
            r"c_1", r"\;\leftarrow\;", r"c_1", r"-",
            r"\alpha", r"\cdot",
            r"\frac{\partial \mathcal{L}}{\partial c_1}",
            font_size=46,
        )
        u1[0].set_color(K_C); u1[2].set_color(K_C)
        u1[4].set_color(ALP_C); u1[6].set_color(GRAD_C)
        u1.next_to(u0, DOWN, buff=0.55)
        self.wr(u1)
        self.p(6.0)

        # alpha annotation
        br_a = Brace(u0[4], UP, color=DIM, buff=0.07)
        lb_a = Tex(r"learning rate", font_size=19, color=ALP_C)
        lb_a.next_to(br_a, UP, buff=0.06)
        self.play(GrowFromCenter(br_a), FadeIn(lb_a), run_time=1.0 * SLOW)
        self.p(4.5)
        self.fo(br_a, lb_a, rt=0.5)

        n5b = self.dim_note(
            r"Repeat over all samples for many epochs --- "
            r"each pass reduces $\mathcal{L}$ a little.")
        n5b.next_to(u1, DOWN, buff=0.55)
        self.fi(n5b)
        self.p(6.0)

        self.fo(s5, n5a, u0, u1, n5b)
        self.p(0.4)

        # ═══════════════════════════════════════════════════════════════════
        # 6.  GENERALISING TO POLYNOMIALS
        # ═══════════════════════════════════════════════════════════════════
        s6 = self.sec_title("6.  Generalising to Polynomials")
        self.fi(s6, rt=0.8)
        self.p(1.5)

        n6a = self.note(
            r"A straight line can't capture curves.  "
            r"Add higher-order terms $x^2,\, x^3,\, \ldots$")
        n6a.next_to(s6, DOWN, buff=0.6)
        self.fi(n6a)
        self.p(5.0)

        # build up term by term
        poly = MathTex(
            r"\hat{y}_i", r"=",
            r"c_0",
            r"+\; c_1 x_i",
            r"+\; c_2 x_i^2",
            r"+\; c_3 x_i^3",
            font_size=44,
        )
        poly[0].set_color(K_C)
        for idx in [2, 3, 4, 5]:
            poly[idx].set_color(K_C)
        poly.next_to(n6a, DOWN, buff=0.7)

        # reveal term by term
        self.play(Write(VGroup(poly[0], poly[1], poly[2])), run_time=1.2 * SLOW)
        self.p(2.5)
        self.play(FadeIn(poly[3], shift=RIGHT * 0.1), run_time=0.9 * SLOW)
        self.p(2.5)
        self.play(FadeIn(poly[4], shift=RIGHT * 0.1), run_time=0.9 * SLOW)
        self.p(2.5)
        self.play(FadeIn(poly[5], shift=RIGHT * 0.1), run_time=0.9 * SLOW)
        self.p(4.0)

        # compact summation form
        n6b = self.dim_note(r"Compactly, with summation notation ($K$ = polynomial degree):")
        n6b.next_to(poly, DOWN, buff=0.55)
        self.fi(n6b)
        self.p(3.5)

        poly_sum = MathTex(
            r"\hat{y}_i", r"=", r"\sum_{k=0}^{K}", r"c_k", r"\,x_i^k",
            font_size=54,
        )
        poly_sum[0].set_color(K_C)
        poly_sum[3].set_color(K_C)
        poly_sum[4].set_color(X_C)
        poly_sum.next_to(n6b, DOWN, buff=0.6)
        self.wr(poly_sum)
        self.p(6.0)

        n6c = self.dim_note(
            r"For $K{=}1$: reduces to $c_0 + c_1 x_i$ --- the linear model.  \checkmark")
        n6c.next_to(poly_sum, DOWN, buff=0.5)
        self.fi(n6c)
        self.p(5.5)

        self.fo(s6, n6a, poly, n6b, poly_sum, n6c)
        self.p(0.4)

        # ═══════════════════════════════════════════════════════════════════
        # 7.  GENERAL GRADIENT
        # ═══════════════════════════════════════════════════════════════════
        s7 = self.sec_title("7.  General Gradient Formula")
        self.fi(s7, rt=0.8)
        self.p(1.5)

        n7a = self.note(
            r"The error is still $e_i = y_i - \hat{y}_i$.  "
            r"Differentiating $\mathcal{L}$ w.r.t.\ $c_k$ pulls down an $x_i^k$ factor:")
        n7a.next_to(s7, DOWN, buff=0.6)
        self.fi(n7a)
        self.p(6.0)

        grad_gen = MathTex(
            r"\frac{\partial \mathcal{L}}{\partial c_k}", r"=",
            r"-\frac{2}{N}", r"\sum_{i=1}^{N}", r"e_i", r"\,x_i^k",
            font_size=54,
        )
        grad_gen[0].set_color(GRAD_C)
        grad_gen[2].set_color(GRAD_C)
        grad_gen[4].set_color(ERR_C)
        grad_gen[5].set_color(X_C)
        grad_gen.next_to(n7a, DOWN, buff=0.75)
        self.wr(grad_gen, rt=2.2)
        self.p(7.0)

        # verify k=0
        ck0 = self.dim_note(
            r"$k{=}0$: $\;x_i^0 = 1\;$ --- "
            r"$\partial\mathcal{L}/\partial c_0 = -(2/N)\textstyle\sum e_i$  \checkmark")
        ck0.next_to(grad_gen, DOWN, buff=0.55)
        self.fi(ck0)
        self.p(5.0)

        # verify k=1
        ck1 = self.dim_note(
            r"$k{=}1$: $\;x_i^1 = x_i\;$ --- "
            r"$\partial\mathcal{L}/\partial c_1 = -(2/N)\textstyle\sum e_i x_i$  \checkmark")
        ck1.next_to(ck0, DOWN, buff=0.32)
        self.fi(ck1)
        self.play(Indicate(grad_gen[5], color=X_C, scale_factor=1.4), run_time=1.0 * SLOW)
        self.p(6.0)

        self.fo(s7, n7a, grad_gen, ck0, ck1)
        self.p(0.4)

        # ═══════════════════════════════════════════════════════════════════
        # 8.  FULL UPDATE RULE (POLYNOMIAL)
        # ═══════════════════════════════════════════════════════════════════
        s8 = self.sec_title("8.  The Polynomial Update Rule")
        self.fi(s8, rt=0.8)
        self.p(1.5)

        n8a = self.note(
            r"The update rule is \textit{identical} in form --- "
            r"it now applies to every $c_k$, $k = 0 \ldots K$:")
        n8a.next_to(s8, DOWN, buff=0.6)
        self.fi(n8a)
        self.p(5.0)

        upd = MathTex(
            r"c_k", r"\;\leftarrow\;", r"c_k", r"-",
            r"\alpha", r"\cdot",
            r"\frac{\partial \mathcal{L}}{\partial c_k}",
            font_size=50,
        )
        upd[0].set_color(K_C); upd[2].set_color(K_C)
        upd[4].set_color(ALP_C); upd[6].set_color(GRAD_C)
        upd.next_to(n8a, DOWN, buff=0.75)
        self.wr(upd)
        self.p(6.0)

        # expand ∂L/∂c_k inline
        upd_exp = MathTex(
            r"c_k", r"\;\leftarrow\;", r"c_k",
            r"+\; \frac{2\alpha}{N}", r"\sum_{i=1}^{N}", r"e_i", r"\,x_i^k",
            font_size=50,
        )
        upd_exp[0].set_color(K_C); upd_exp[2].set_color(K_C)
        upd_exp[3].set_color(ALP_C)
        upd_exp[5].set_color(ERR_C); upd_exp[6].set_color(X_C)
        upd_exp.next_to(upd, DOWN, buff=0.65)

        n8b = self.dim_note(r"Substituting $\partial\mathcal{L}/\partial c_k$:")
        n8b.next_to(upd, DOWN, buff=0.25)
        self.fi(n8b)
        self.p(2.5)
        self.fo(n8b, rt=0.4)
        self.wr(upd_exp)
        self.p(7.0)

        n8c = self.dim_note(
            r"This is the formula the hardware computes for each "
            r"coefficient and each training epoch.")
        n8c.next_to(upd_exp, DOWN, buff=0.55)
        self.fi(n8c)
        self.p(7.0)

        self.fo(s8, n8a, upd, upd_exp, n8c)
        self.p(0.4)

        # ═══════════════════════════════════════════════════════════════════
        # 9.  SUMMARY
        # ═══════════════════════════════════════════════════════════════════
        s9 = self.sec_title("Summary")
        self.fi(s9, rt=0.8)
        self.p(1.5)

        # Five formula rows: label (left) + formula (right)
        row_data = [
            ("Model:",
             MathTex(r"\hat{y}_i \;=\; \sum_{k=0}^{K} c_k\, x_i^k",
                     font_size=36).set_color(K_C)),
            ("Error:",
             MathTex(r"e_i \;=\; y_i - \hat{y}_i",
                     font_size=36).set_color(ERR_C)),
            ("Loss:",
             MathTex(r"\mathcal{L} \;=\; \tfrac{1}{N}\sum_i e_i^2",
                     font_size=36).set_color(HL_C)),
            ("Gradient:",
             MathTex(r"\nabla_k \;=\; -\tfrac{2}{N}\sum_i e_i\, x_i^k",
                     font_size=36).set_color(GRAD_C)),
            ("Update:",
             MathTex(r"c_k \;\leftarrow\; c_k + \tfrac{2\alpha}{N}\sum_i e_i\, x_i^k",
                     font_size=36).set_color(K_C)),
        ]

        row_labels = []
        row_fmls   = []
        y0 = 1.9
        dy = 1.05
        for i, (lbl_str, fml) in enumerate(row_data):
            lbl = Tex(lbl_str, font_size=24, color=DIM)
            y = y0 - i * dy
            lbl.move_to(LEFT * 4.0 + UP * y).set_x(-4.0)
            lbl.align_to(lbl, LEFT)
            fml.move_to(UP * y).set_x(0.8)
            row_labels.append(lbl)
            row_fmls.append(fml)

        for lbl, fml in zip(row_labels, row_fmls):
            self.play(FadeIn(lbl, shift=RIGHT * 0.1),
                      Write(fml), run_time=1.3 * SLOW)
            self.p(4.0)

        self.p(6.0)

        # fade everything
        all_summary = VGroup(s9, *row_labels, *row_fmls)
        self.fo(all_summary, rt=1.5)
        self.p(0.8)
