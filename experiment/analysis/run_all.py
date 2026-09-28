#!/usr/bin/env python3
"""Run every analysis stage in one shot: the primary EER/TAR@FAR
results table, ROC curves, score distributions, and the supplementary
similarity bar chart.

Run (inside antifake2026 env):
    conda run -n antifake2026 python analysis/run_all.py
"""
import results_table
import roc_curves
import score_distributions
import similarity_bar_chart

if __name__ == "__main__":
    results_table.main()
    roc_curves.main()
    score_distributions.main()
    similarity_bar_chart.main()
