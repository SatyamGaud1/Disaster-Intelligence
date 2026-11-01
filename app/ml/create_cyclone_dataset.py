"""
Generates and formats the open benchmark cyclone meteorological dataset based on NOAA / IBTrACS physical standards.
Features:
- central_pressure_hpa: Minimum central barometric pressure in hPa (890 - 1015 hPa, lower = more intense)
- max_sustained_wind_kmh: 1-minute maximum sustained wind speed in km/h (40 - 290 km/h)
- sea_surface_temp_c: Oceanic thermal energy / Sea Surface Temperature in °C (24.0 - 32.5 °C)
- storm_forward_speed_kmh: Storm translation / forward propagation velocity in km/h (5 - 55 km/h)
- coastal_distance_km: Proximity of cyclone center to nearest coastline in km (0 - 500 km)
- cyclone_severe_risk: Binary target label (1 = Severe Coastal / Maritime Risk, 0 = Minimal / Sub-critical Risk)
"""

from pathlib import Path
import numpy as np
import pandas as pd


def generate_cyclone_benchmark_dataset(output_path: Path = None, n_samples: int = 300, seed: int = 42) -> Path:
    np.random.seed(seed)

    n_severe = int(n_samples * 0.50)
    n_mild = n_samples - n_severe

    # Severe cyclones: deep low pressure (910 - 975 hPa), high winds (120 - 270 km/h), warm sea (>28°C), closer to coast
    # Mild/sub-critical: higher pressure (985 - 1012 hPa), moderate winds (45 - 95 km/h), cooler sea (<27.5°C), farther offshore
    pressure = np.concatenate([
        np.random.normal(950.0, 18.0, n_severe),
        np.random.normal(998.0, 10.0, n_mild)
    ]).clip(890.0, 1015.0)

    wind = np.concatenate([
        np.random.normal(165.0, 35.0, n_severe),
        np.random.normal(68.0, 18.0, n_mild)
    ]).clip(35.0, 290.0)

    sst = np.concatenate([
        np.random.normal(29.6, 1.2, n_severe),
        np.random.normal(26.4, 1.3, n_mild)
    ]).clip(24.0, 32.5)

    speed = np.concatenate([
        np.random.normal(18.0, 7.0, n_severe),
        np.random.normal(24.0, 8.0, n_mild)
    ]).clip(5.0, 55.0)

    coastal_dist = np.concatenate([
        np.random.exponential(65.0, n_severe),
        np.random.exponential(220.0, n_mild)
    ]).clip(0.0, 500.0)

    # Physical meteorological latent score with natural stochastic noise:
    # 1. Delta pressure: (1013 - pressure) gives positive intensity score
    # 2. Wind: (wind - 90)
    # 3. SST: (sst - 28.0) * 0.4
    # 4. Coastal proximity: negative coefficient with distance
    noise = np.random.normal(0.0, 0.75, n_samples)
    z = (
        0.065 * (1000.0 - pressure)
        + 0.035 * (wind - 100.0)
        + 0.450 * (sst - 28.0)
        - 0.012 * (coastal_dist - 120.0)
        - 0.025 * (speed - 20.0)
        + noise
    )
    prob = 1.0 / (1.0 + np.exp(-z))
    risk_label = (prob > 0.50).astype(int)

    df = pd.DataFrame({
        "central_pressure_hpa": np.round(pressure, 1),
        "max_sustained_wind_kmh": np.round(wind, 1),
        "sea_surface_temp_c": np.round(sst, 1),
        "storm_forward_speed_kmh": np.round(speed, 1),
        "coastal_distance_km": np.round(coastal_dist, 1),
        "cyclone_severe_risk": risk_label
    })

    # Shuffle rows deterministically
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    if output_path is None:
        base_dir = Path(__file__).resolve().parent.parent.parent
        output_path = base_dir / "data" / "raw" / "cyclone_meteorological_dataset.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


if __name__ == "__main__":
    out = generate_cyclone_benchmark_dataset()
    df = pd.read_csv(out)
    print(f"Cyclone dataset generated at: {out}")
    print(f"Total rows: {len(df)}")
    print(f"Class distribution: {dict(df['cyclone_severe_risk'].value_counts())}")
    print(df.head(3))

