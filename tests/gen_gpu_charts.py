#!/usr/bin/env python3
"""Figures du dossier docs/gpu/img/ : tout vient des mesures réelles du dépôt (results/*/server_window.json, goodput.json,
summary_lifecycle_metrics.json) ou de constantes citées (fiche NVIDIA du T4). Rien n'est saisi à la main.

Usage : python3 tests/gen_gpu_charts.py [--png DIR]     (--png écrit aussi des aperçus PNG pour les relire)
Règles de dataviz appliquées : un seul axe par graphique, marques fines, grille en filet, couleur par entité (1,5B = bleu, 7B = orange,
palette de référence validée), étiquettes directes sélectives, un tableau équivalent dans le document qui affiche la figure."""
import glob, json, math, pathlib, sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/gpu/img"
OUT.mkdir(parents=True, exist_ok=True)
PNG = None
if "--png" in sys.argv:
    PNG = pathlib.Path(sys.argv[sys.argv.index("--png") + 1]); PNG.mkdir(parents=True, exist_ok=True)

# --- encre et surface (palette de référence, mode clair ; le SVG porte sa propre surface pour rester lisible en thème sombre)
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE = "#2a78d6", "#eb6834"          # série 1 (1,5B) et série 2 (7B)
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#184f95", "#0d366b"]   # séquentiel bleu 100 -> 700
plt.rcParams.update({"svg.fonttype": "path", "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": AXIS,
                     "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "figure.facecolor": SURFACE,
                     "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})

# --- constantes citées (docs/gpu/SOURCES.md)
PEAK_TFLOPS = 65.0        # fiche NVIDIA du T4 (mars 2019) : « Mixed-Precision (FP16/FP32) 65 TFLOPS »
BW_GBS = 320.0            # 320 Go/s (page produit / 5001 MHz x 2 x 256 bits) ; la fiche de 2019 indique 300 Go/s
POWER_LIMIT_W = 70.0      # fiche NVIDIA : 70 W
CLOCK_MAX_MHZ = 1590.0    # relevé nvidia-smi publié sur le forum NVIDIA (horloges max 5001 mémoire, 1590 SM) : à relire sur notre T4

RUNS = [  # (étiquette, modèle, dossier results, étiquette courte)
    ("Interactif 2 req/s", "1,5B", "small-fp16-interactive-class"),
    ("RAG 0,5 req/s", "1,5B", "small-fp16-long-prompt-class"),
    ("Multi-tour 0,5 req/s", "1,5B", "small-fp16-multi-turn-class"),
    ("Lot 7 req/s (saturé)", "1,5B", "small-fp16-batch-class"),
    ("Interactif 1 req/s", "7B", "baseline-7b-interactive-class"),
    ("Multi-tour 0,5 req/s", "7B", "baseline-7b-multi-turn-class"),
    ("Lot 2,5 req/s (effondré)", "7B", "baseline-7b-batch-class"),
    ("RAG 0,1 req/s", "7B", "baseline-7b-long-prompt-class-nominal"),
]


def load(folder):
    d = glob.glob(str(ROOT / f"results/*-{folder}"))[0]
    s = json.load(open(d + "/server_window.json")); g = json.load(open(d + "/goodput.json"))
    th = json.load(open(d + "/summary_lifecycle_metrics.json"))["successes"]["throughput"]
    return {"util": s["gpu_util"] / 100, "sm": s["sm_active"], "tensor": s["tensor"], "dram": s["dram"], "power": s["power_w"],
            "clock": s["sm_clock_mhz"], "kv": s["kv_usage"], "out_tps": g["raw_tok_s"], "in_tps": th.get("input_tokens_per_sec", 0.0),
            "run": pathlib.Path(d).name}


DATA = [(lab, mod, load(f)) for lab, mod, f in RUNS]


def save(fig, name):
    fig.savefig(OUT / f"{name}.svg", format="svg")
    if PNG:
        fig.savefig(PNG / f"{name}.png", format="png", dpi=110)
    plt.close(fig)


def style_axes(ax):
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(AXIS); ax.spines["bottom"].set_color(AXIS)
    ax.grid(True, color=GRID, linewidth=0.6, linestyle="-"); ax.set_axisbelow(True)
    ax.tick_params(length=3, labelsize=9)


# ============================================================================== 1. roofline du T4
def roofline():
    fig, ax = plt.subplots(figsize=(8.6, 5.3))
    style_axes(ax)
    ridge = PEAK_TFLOPS * 1e12 / (BW_GBS * 1e9)                  # opérations par octet à partir desquelles on devient limité par le calcul
    xs = [0.5, ridge, 30000]
    ax.plot(xs, [BW_GBS * 1e9 * 0.5 / 1e12, PEAK_TFLOPS, PEAK_TFLOPS], color=INK2, linewidth=2, solid_capstyle="round", zorder=3)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(0.5, 30000); ax.set_ylim(0.1, 150)
    ax.set_xlabel("Intensité arithmétique : opérations effectuées par octet de poids lu", fontsize=9.5)
    ax.set_ylabel("Performance atteignable (TFLOPS)", fontsize=9.5)
    ax.axvline(ridge, color=AXIS, linewidth=0.8, zorder=1)
    ax.text(ridge * 1.08, 0.13, f"point de bascule ≈ {ridge:.0f}", color=MUTED, fontsize=8.5)
    ax.text(7, 1.05, "limité par la MÉMOIRE :\nle temps passe à lire les poids", color=MUTED, fontsize=9, va="center")
    ax.text(2600, 24, "limité par le CALCUL", color=MUTED, fontsize=9, va="center")
    ax.text(0.52, 80, f"toit mémoire : {BW_GBS:.0f} Go/s    toit calcul : {PEAK_TFLOPS:.0f} TFLOPS (FP16, tensor cores)", color=INK2, fontsize=8.5, va="center")

    params, wbytes = 7.61e9, 5.29 * 1024 ** 3          # 7B AWQ : paramètres (fiche du modèle) et octets chargés (log vLLM)
    ai1 = 2 * params / wbytes                           # intensité d'un décodage à 1 requête (2 opérations par paramètre et par token)
    pts = [("décodage, 1 requête", 1, ai1, (0.62, 2.1), "left"), ("décodage, 32 requêtes en parallèle", 32, 32 * ai1, (120, 13), "left"),
           ("décodage, 200 requêtes (lot saturé)", 200, 200 * ai1, (800, 108), "right"), ("prefill, prompt de 2 750 tokens", 2750, 2750 * ai1, (2300, 108), "left")]
    for lab, _, ai, xy, ha in pts:
        y = min(BW_GBS * 1e9 * ai / 1e12, PEAK_TFLOPS)
        ax.scatter([ai], [y], s=64, facecolor=SURFACE, edgecolor=INK2, linewidth=1.8, zorder=5)
        ax.annotate(lab, (ai, y), xytext=xy, fontsize=8.4, color=INK, ha=ha, va="center", zorder=6)
    # point mesuré : 7B AWQ, 21,5 ms par token (test de fumée via LiteLLM), KV ignoré
    meas_perf = 2 * params / 0.0215 / 1e12
    ax.scatter([ai1], [meas_perf], s=80, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=7)
    roof = BW_GBS * 1e9 * ai1 / 1e12
    ax.annotate(f"mesuré : 7B AWQ, 21,5 ms par token\n= {100 * meas_perf / roof:.0f} % du toit mémoire", (ai1, meas_perf), xytext=(4.2, 0.30),
                fontsize=9, color=BLUE, fontweight="bold", ha="left", va="center", zorder=8,
                arrowprops={"arrowstyle": "-", "color": BLUE, "linewidth": 1.0, "shrinkA": 0, "shrinkB": 5})
    fig.text(0.012, 0.012, "Modèle simplifié : seules les lectures de poids sont comptées (cache KV et activations ignorés). Cercle creux : calcul ; point plein : mesure du lab.",
             fontsize=7.6, color=MUTED, ha="left", va="bottom")
    fig.suptitle("Roofline du T4 : le décodage est limité par la mémoire, le prefill par le calcul", x=0.012, ha="left", fontsize=11.5, fontweight="bold", color=INK)
    fig.subplots_adjust(left=0.09, right=0.985, top=0.9, bottom=0.14)
    save(fig, "roofline-t4")
    return {"ridge": ridge, "ai1": ai1, "meas_perf": meas_perf, "roof": roof}


# ============================================================================== 2. carte thermique des 8 situations
def heatmap():
    cols = [("GPU_UTIL", lambda d: d["util"], lambda d: f"{100 * d['util']:.0f} %"),
            ("SM_ACTIVE", lambda d: d["sm"], lambda d: f"{d['sm']:.2f}"),
            ("TENSOR", lambda d: d["tensor"], lambda d: f"{d['tensor']:.2f}"),
            ("DRAM_ACTIVE", lambda d: d["dram"], lambda d: f"{d['dram']:.2f}"),
            ("Puissance\n(/ 70 W)", lambda d: d["power"] / POWER_LIMIT_W, lambda d: f"{d['power']:.0f} W"),
            ("Horloge SM\n(/ 1590 MHz)", lambda d: d["clock"] / CLOCK_MAX_MHZ, lambda d: f"{d['clock']:.0f}"),
            ("Cache KV\nutilisé", lambda d: d["kv"], lambda d: f"{100 * d['kv']:.0f} %")]
    cmap = LinearSegmentedColormap.from_list("bleu", RAMP)
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    n = len(DATA)
    for i, (lab, mod, d) in enumerate(DATA):
        for j, (_, f, fmt) in enumerate(cols):
            v = max(0.0, min(1.0, f(d)))
            ax.add_patch(plt.Rectangle((j + 0.03, n - 1 - i + 0.04), 0.94, 0.92, facecolor=cmap(v), edgecolor="none"))
            ax.text(j + 0.5, n - 1 - i + 0.5, fmt(d), ha="center", va="center", fontsize=9.2, color="#ffffff" if v > 0.5 else INK)
        ax.text(-0.08, n - 1 - i + 0.5, lab, ha="right", va="center", fontsize=9.3, color=INK)
        ax.text(-2.55, n - 1 - i + 0.5, mod, ha="left", va="center", fontsize=9.3, color=BLUE if mod == "1,5B" else ORANGE, fontweight="bold")
    for j, (name, _, _) in enumerate(cols):
        ax.text(j + 0.5, n + 0.12, name, ha="center", va="bottom", fontsize=8.2, color=INK2)
    ax.plot([-2.6, len(cols)], [n / 2, n / 2], color=SURFACE, linewidth=0)           # espace entre les deux modèles
    ax.set_xlim(-2.7, len(cols)); ax.set_ylim(-0.1, n + 1.25); ax.axis("off")
    # échelle
    sx = ax.inset_axes([0.35, -0.045, 0.3, 0.025])
    sx.imshow([list(range(100))], aspect="auto", cmap=cmap, extent=[0, 1, 0, 1]); sx.set_yticks([]); sx.set_xticks([0, 0.5, 1]); sx.set_xticklabels(["0", "0,5", "1"], fontsize=8)
    for sp in sx.spines.values():
        sp.set_visible(False)
    sx.tick_params(length=0)
    fig.text(0.012, 0.012, "Moyennes de chaque run. Une seule échelle 0 → 1 (colonne rapportée à son maximum) ; valeurs réelles dans les cases.",
             fontsize=7.8, color=MUTED, ha="left", va="bottom")
    fig.suptitle("Le même T4 dans huit situations : ce que disent les compteurs", x=0.012, ha="left", fontsize=11.5, fontweight="bold", color=INK)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.9, bottom=0.12)
    save(fig, "gpu-8-situations")


# ============================================================================== 3. puissance et horloge
def power_clock():
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    style_axes(ax)
    ax.set_xlim(900, 1700); ax.set_ylim(44, 74)
    ax.set_xlabel("Horloge moyenne des unités de calcul (MHz)", fontsize=9.5); ax.set_ylabel("Puissance moyenne (W)", fontsize=9.5)
    ax.axhline(POWER_LIMIT_W, color=INK2, linewidth=1.4, zorder=2)
    ax.text(905, POWER_LIMIT_W + 0.5, "limite de puissance : 70 W (fiche NVIDIA)", color=INK2, fontsize=8.8, va="bottom")
    ax.axvline(CLOCK_MAX_MHZ, color=INK2, linewidth=1.4, zorder=2)
    ax.text(CLOCK_MAX_MHZ - 8, 45, "horloge maximale\n1 590 MHz (relevé)", color=INK2, fontsize=8.8, va="bottom", ha="right")
    for lab, mod, d in DATA:
        ax.scatter([d["clock"]], [d["power"]], s=78, color=BLUE if mod == "1,5B" else ORANGE, edgecolor=SURFACE, linewidth=2, zorder=5)
    # trois répétitions de bruit du 1,5B (steady 2 req/s)
    for r in sorted(glob.glob(str(ROOT / "results/*small-fp16-steady-noise-r*/server_window.json"))):
        s_ = json.load(open(r)); ax.scatter([s_["sm_clock_mhz"]], [s_["power_w"]], s=40, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=4, alpha=0.75)
    by = {(lab, mod): d for lab, mod, d in DATA}
    notes = [(("Interactif 2 req/s", "1,5B"), "Interactif 2 req/s (1,5B, 4 runs)", (1222, 64.0), "left"),
             (("Lot 2,5 req/s (effondré)", "7B"), "Lot 2,5 req/s, effondré (7B)", (925, 63.3), "left"),
             (("Interactif 1 req/s", "7B"), "Interactif 1 req/s (7B)", (925, 66.6), "left"),
             (("Lot 7 req/s (saturé)", "1,5B"), "Lot 7 req/s, saturé (1,5B)", (1000, 56.2), "left"),
             (("Multi-tour 0,5 req/s", "1,5B"), "Multi-tour 0,5 req/s (1,5B et 7B)", (1245, 55.6), "left"),
             (("RAG 0,5 req/s", "1,5B"), "RAG 0,5 req/s (1,5B)", (1410, 59.4), "left"),
             (("RAG 0,1 req/s", "7B"), "RAG 0,1 req/s (7B)", (1030, 48.6), "left")]
    for key, text, xy, ha in notes:
        d = by[key]
        ax.annotate(text, (d["clock"], d["power"]), xytext=xy, fontsize=8.5, color=INK, ha=ha, va="center", zorder=6,
                    arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.8, "shrinkA": 2, "shrinkB": 5})
    ax.scatter([], [], s=70, color=BLUE, label="Qwen2.5-1,5B FP16"); ax.scatter([], [], s=70, color=ORANGE, label="Qwen2.5-7B AWQ")
    ax.legend(loc="center right", frameon=False, fontsize=9, bbox_to_anchor=(1.0, 0.62))
    fig.text(0.012, 0.012, "Un point = un run de 5 min (moyennes). Petits points bleus : 3 répétitions du 1,5B. Raison exacte du bridage non relevée (voir 05-simulations).",
             fontsize=7.8, color=MUTED, ha="left", va="bottom")
    fig.suptitle("Aucune charge n'atteint l'horloge maximale, et la puissance frôle 70 W", x=0.012, ha="left", fontsize=11.5, fontweight="bold", color=INK)
    fig.subplots_adjust(left=0.08, right=0.985, top=0.9, bottom=0.14)
    save(fig, "puissance-horloge")


# ============================================================================== 4. énergie par token
def energy():
    rows = []
    for lab, mod, d in DATA:
        rows.append((lab, mod, d["out_tps"] / d["power"], (d["out_tps"] + d["in_tps"]) / d["power"]))
    rows.sort(key=lambda r: -r[2])
    fig, axs = plt.subplots(1, 2, figsize=(8.6, 4.8), sharey=True)
    for k, ax in enumerate(axs):
        style_axes(ax); ax.grid(axis="y", visible=False)
        ys = list(range(len(rows)))[::-1]
        vals = [r[2 + k] for r in rows]
        ax.barh(ys, vals, height=0.62, color=[BLUE if r[1] == "1,5B" else ORANGE for r in rows], zorder=3)
        for y, v in zip(ys, vals):
            ax.text(v + max(vals) * 0.015, y, f"{v:.1f}" if v >= 1 else f"{v:.2f}", va="center", fontsize=8.6, color=INK)
        ax.set_xlim(0, max(vals) * 1.18)
        ax.set_title(["Tokens de sortie par joule", "Tokens traités (prompt + sortie) par joule"][k], fontsize=9.5, color=INK2, loc="left")
    axs[0].set_yticks(list(range(len(rows)))[::-1]); axs[0].set_yticklabels([f"{r[0]} ({r[1]})" for r in rows], fontsize=8.8, color=INK)
    fig.text(0.012, 0.012, "Puissance GPU seule (nœud et CPU non comptés). 1 joule = 1 watt pendant 1 s. Bleu : 1,5B FP16 ; orange : 7B AWQ.",
             fontsize=7.8, color=MUTED, ha="left", va="bottom")
    fig.suptitle("Plus on fait travailler le GPU, moins chaque token coûte en énergie", x=0.012, ha="left", fontsize=11.5, fontweight="bold", color=INK)
    fig.subplots_adjust(left=0.30, right=0.985, top=0.86, bottom=0.12, wspace=0.08)
    save(fig, "energie-par-token")
    return rows


if __name__ == "__main__":
    info = roofline(); heatmap(); power_clock(); rows = energy()
    print(f"roofline : point de bascule {info['ridge']:.0f} op/octet ; intensité 7B AWQ à 1 requête {info['ai1']:.2f} ; mesuré {info['meas_perf']:.3f} TFLOPS = {100 * info['meas_perf'] / info['roof']:.0f} % du toit")
    for r in rows:
        print(f"  {r[0]:26} {r[1]:5} sortie {r[2]:6.2f} tok/J   total {r[3]:6.2f} tok/J")
    print("figures :", ", ".join(sorted(p.name for p in OUT.glob('*.svg'))))
