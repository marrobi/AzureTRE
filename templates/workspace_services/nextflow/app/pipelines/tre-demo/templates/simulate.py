#!/usr/bin/env python3
import csv
import hashlib
import random

sample = "${sample}"
steps = int("${params.steps}")
rng = random.Random(int(hashlib.sha256(sample.encode()).hexdigest()[:8], 16))

value = 0.0
with open(sample + ".csv", "w", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["sample", "step", "value"])
    for step in range(steps):
        value += rng.gauss(0, 1)
        writer.writerow([sample, step, round(value, 4)])
