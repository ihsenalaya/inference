#!/usr/bin/env python3
"""Figures de la séance GPU (docs/gpu/07-resultats-seance.md), tirées des runs réels : escalier de charge (S2) et prefill pur contre decode pur (S4).
Usage : python3 tests/gen_gpu_session_charts.py [--png DIR]. Mêmes règles de dataviz que tests/gen_gpu_charts.py (un axe par graphique, marques fines, couleur par entité)."""
import glob, json, pathlib, sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_gpu_charts as g  # noqa: E402  (constantes, styles, sauvegarde)

ROOT = g.ROOT


def run(name):
    d = glob.glob(str(ROOT / f"results/*-{name}"))
    if not d:
        return None
    d = d[0]
    s = json.load(open(d + "/server_window.json"))
    th = json.load(open(d + "/summary_lifecycle_metrics.json"))["successes"]
    s["out_tps"] = th["throughput"]["output_tokens_per_sec"]
    s["tpot_p50"] = th["latency"]["time_per_output_token"]["median"]
    s["ttft_p50"] = th["latency"]["time_to_first_token"]["median"]
    return s


def escalier():
    rates = [0.5, 1.5, 2.5]
    rows = [(r, run(f"gpu-health-steady-direct-escalier-r{r}")) for r in rates]
    rows = [(r, s) for r, s in rows if s]
    if len(rows) < 2:
        print("escalier : pas assez de paliers")
        return
    x = [r for r, _ in rows]
    fig, axs = plt.subplots(2, 3, figsize=(8.6, 5.6), sharex=True)
    panels = [
        ("Tokens de sortie servis par seconde", [("tokens/s", [s["out_tps"] for _, s in rows], g.BLUE)], None, None),
        ("Temps par token, médiane (ms)", [("TPOT p50", [1000 * s["tpot_p50"] for _, s in rows], g.BLUE)], None, None),
        ("Puissance (W)", [("puissance", [s["power_w"] for _, s in rows], g.BLUE)], g.POWER_LIMIT_W, "limite 70 W"),
        ("Horloge des unités de calcul (MHz)", [("horloge", [s["sm_clock_mhz"] for _, s in rows], g.BLUE)], g.CLOCK_MAX_MHZ, "maximum 1 590"),
        ("Activité (0 à 1)", [("SM_ACTIVE", [s["sm_active"] for _, s in rows], g.BLUE), ("DRAM ÷ 0,8", [s["dram"] / 0.8 for _, s in rows], g.ORANGE),
                              ("TENSOR", [s["tensor"] for _, s in rows], g.INK2)], None, None),
        ("Part du temps au plafond (0 à 1)", [("bit 0x4 actif", [s.get("sw_power_cap_part") or 0 for _, s in rows], g.BLUE)], None, None),
    ]
    for ax, (title, series, limit, limit_label) in zip(axs.flat, panels):
        g.style_axes(ax)
        for lab, ys, col in series:
            ax.plot(x, ys, color=col, linewidth=2, marker="o", markersize=6, markeredgecolor=g.SURFACE, markeredgewidth=1.5, label=lab, zorder=4)
        if limit:
            ax.axhline(limit, color=g.INK2, linewidth=1.2, zorder=2)
            ax.text(x[0], limit, " " + limit_label, color=g.INK2, fontsize=8, va="bottom")
        ax.set_title(title, fontsize=9, color=g.INK2, loc="left")
        if len(series) > 1:
            ax.legend(frameon=False, fontsize=8, loc="best")
    for ax in axs[1]:
        ax.set_xlabel("Débit demandé (requêtes/s)", fontsize=9)
    axs[1][2].set_ylim(-0.05, 1.05); axs[1][1].set_ylim(0, 1.05)
    fig.text(0.012, 0.012, "7B AWQ, 1 T4, directement sur vLLM, un run par palier (30 s d'échauffement exclu, 150 s de mesure). Moyennes sur la fenêtre.", fontsize=7.8, color=g.MUTED)
    fig.suptitle("Escalier de charge : le plafond de puissance arrive avant la saturation", x=0.012, ha="left", fontsize=11.5, fontweight="bold", color=g.INK)
    fig.subplots_adjust(left=0.07, right=0.985, top=0.88, bottom=0.12, wspace=0.28, hspace=0.38)
    g.save(fig, "escalier-gpu")
    return rows


def prefill_decode():
    pre, dec = run("gpu-health-prefill-only-s4"), run("gpu-health-decode-only-direct-s4")
    if not (pre and dec):
        print("S4 : runs manquants")
        return
    labels = ["SM_ACTIVE", "TENSOR", "DRAM_ACTIVE ÷ 0,8", "Puissance ÷ 70 W", "Horloge ÷ 1590", "Plafond de puissance\n(part du temps)"]
    f = lambda s: [s["sm_active"], s["tensor"], s["dram"] / 0.8, s["power_w"] / g.POWER_LIMIT_W, s["sm_clock_mhz"] / g.CLOCK_MAX_MHZ, s.get("sw_power_cap_part") or 0]
    a, b = f(dec), f(pre)
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    g.style_axes(ax); ax.grid(axis="x", visible=False)
    w = 0.36
    xs = list(range(len(labels)))
    ax.bar([i - w / 2 for i in xs], a, w, color=g.BLUE, label="Decode pur (prompts courts, longues réponses)", zorder=3)
    ax.bar([i + w / 2 for i in xs], b, w, color=g.ORANGE, label="Prefill pur (prompts longs, 1 à 4 tokens)", zorder=3)
    for i in xs:
        ax.text(i - w / 2, a[i] + 0.015, f"{a[i]:.2f}", ha="center", fontsize=8.4, color=g.INK)
        ax.text(i + w / 2, b[i] + 0.015, f"{b[i]:.2f}", ha="center", fontsize=8.4, color=g.INK)
    ax.set_xticks(xs); ax.set_xticklabels(labels, fontsize=8.6, color=g.INK)
    ax.set_ylim(0, 1.38); ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0]); ax.set_ylabel("Valeur (0 à 1)", fontsize=9)
    ax.legend(frameon=False, fontsize=8.8, loc="upper left")
    fig.text(0.012, 0.012, "7B AWQ sur 1 T4 ; decode pur : 0,3 req/s, prefill pur : 0,1 req/s ; moyennes sur 270 s, creux compris (le prefill pur n'occupe le GPU que 33 % du temps) ; un run chacun.", fontsize=7.8, color=g.MUTED)
    fig.suptitle(f"Decode pur contre prefill pur : la mémoire travaille {dec['dram'] / pre['dram']:.0f} fois plus en decode", x=0.012, ha="left", fontsize=11.5, fontweight="bold", color=g.INK)
    fig.subplots_adjust(left=0.07, right=0.985, top=0.88, bottom=0.17)
    g.save(fig, "prefill-contre-decode")


S5_CONFIGS = [  # (étiquette, dossier results sans la date, couleur)
    ("70 W\ndéfaut", "gpu-health-steady-direct-escalier-r1.5"),
    ("65 W", "gpu-health-steady-direct-s5-pl65"),
    ("60 W", "gpu-health-steady-direct-s5-pl60"),
    ("900\nMHz", "gpu-health-steady-direct-s5-lgc900"),
    ("750\nMHz", "gpu-health-steady-direct-s5-lgc750"),
]


def s5_rows():
    rows = []
    for lab, name in S5_CONFIGS:
        s = run(name)
        if s:
            rows.append((lab, s))
    return rows


def s5():
    rows = s5_rows()
    if len(rows) < 3:
        print("S5 : runs manquants")
        return
    labels = [l for l, _ in rows]
    xs = list(range(len(rows)))
    panels = [
        ("Tokens de sortie par seconde", [s["out_tps"] for _, s in rows], "{:.0f}"),
        ("Puissance moyenne (W)", [s["power_w"] for _, s in rows], "{:.0f}"),
        ("Tokens de sortie par joule", [s["out_tps"] / s["power_w"] for _, s in rows], "{:.2f}"),
        ("Premier token, médiane (s)", [s["ttft_p50"] for _, s in rows], "{:.1f}"),
    ]
    fig, axs = plt.subplots(1, 4, figsize=(9.6, 3.9))
    for ax, (title, ys, fmt) in zip(axs, panels):
        g.style_axes(ax); ax.grid(axis="x", visible=False)
        cols = [g.BLUE if i else g.INK2 for i in xs]
        ax.bar(xs, ys, 0.62, color=cols, zorder=3)
        for i, y in zip(xs, ys):
            ax.text(i, y + max(ys) * 0.02, fmt.format(y), ha="center", fontsize=8.2, color=g.INK)
        ax.set_xticks(xs); ax.set_xticklabels(labels, fontsize=7.4, color=g.INK)
        ax.set_ylim(0, max(ys) * 1.18)
        ax.set_title(title, fontsize=9, color=g.INK2, loc="left")
    fig.text(0.012, 0.01, "7B AWQ, 1 T4, 1,5 req/s demandés (au bord de la capacité), directement sur vLLM ; un run chacun (150 s de mesure).\n60 W et 65 W : limite de puissance (nvidia-smi -pl) ; 900 et 750 MHz : horloge verrouillée (nvidia-smi -lgc) ; barre grise : référence 70 W.", fontsize=7.6, color=g.MUTED)
    best = max(rows, key=lambda r: r[1]["out_tps"] / r[1]["power_w"])[0].replace("\n", " ")
    fig.suptitle(f"Meilleur rendement énergétique à {best}, au prix d'un premier token plus lent", x=0.012, ha="left", fontsize=11.2, fontweight="bold", color=g.INK)
    fig.subplots_adjust(left=0.04, right=0.99, top=0.82, bottom=0.24, wspace=0.22)
    g.save(fig, "puissance-horloge-s5")


if __name__ == "__main__":
    escalier(); prefill_decode(); s5()
    print("figures :", ", ".join(sorted(p.name for p in g.OUT.glob("*.svg"))))
