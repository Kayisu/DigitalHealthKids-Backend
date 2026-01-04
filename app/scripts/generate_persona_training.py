import argparse
import csv
import pathlib
import random

PERSONAS = {
    "Gece Kuşu": dict(night=(65, 8), total=(180, 25), gaming=(0.20, 0.06), social=(0.25, 0.07), weekend=(1.05, 0.10)),
    "Sıkı Oyuncu": dict(night=(28, 6), total=(170, 30), gaming=(0.55, 0.08), social=(0.18, 0.05), weekend=(1.05, 0.08)),
    "Sosyal Medya Tutkunu": dict(night=(26, 6), total=(165, 25), gaming=(0.18, 0.05), social=(0.55, 0.08), weekend=(1.02, 0.08)),
    "Hafta Sonu Odaklı": dict(night=(20, 6), total=(155, 20), gaming=(0.30, 0.06), social=(0.25, 0.05), weekend=(1.42, 0.12)),
    "Dengeli Kullanıcı": dict(night=(16, 5), total=(120, 20), gaming=(0.22, 0.05), social=(0.22, 0.05), weekend=(1.00, 0.05)),
}


def sample_value(mean: float, std: float, floor: float = 0.0, ceil: float | None = None) -> float:
    val = random.normalvariate(mean, std)
    if ceil is not None:
        val = min(ceil, val)
    return max(floor, val)


def generate_rows(per_class: int) -> list[tuple[str, float, float, float, float, float]]:
    rows: list[tuple[str, float, float, float, float, float]] = []
    for label, cfg in PERSONAS.items():
        for _ in range(per_class):
            night = sample_value(*cfg["night"], floor=0)
            total = sample_value(*cfg["total"], floor=30)
            gaming = sample_value(*cfg["gaming"], floor=0, ceil=0.95)
            social = sample_value(*cfg["social"], floor=0, ceil=0.95)
            weekend = sample_value(*cfg["weekend"], floor=0.5)
            rows.append((label, night, total, gaming, social, weekend))
    return rows


def write_csv(path: pathlib.Path, rows: list[tuple[str, float, float, float, float, float]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["label", "night_avg", "total_avg", "gaming_ratio", "social_ratio", "weekend_ratio"])
        for r in rows:
            w.writerow([
                r[0],
                f"{r[1]:.2f}",
                f"{r[2]:.2f}",
                f"{r[3]:.3f}",
                f"{r[4]:.3f}",
                f"{r[5]:.3f}",
            ])


def main():
    parser = argparse.ArgumentParser(description="Generate persona training CSV")
    parser.add_argument("--per-class", type=int, default=1000, help="Row count per class")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("app/assets/persona_training.csv"), help="Output CSV path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)
    rows = generate_rows(args.per_class)
    write_csv(args.out, rows)
    print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
