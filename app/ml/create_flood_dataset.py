"""
Generates and formats the open benchmark flood hydrological dataset.
Features:
- precipitation_24h_mm: NASA GPM 24-hour accumulated rainfall in mm
- soil_moisture_pct: Antecedent soil saturation moisture percentage (0 - 100%)
- radar_backscatter_drop_db: Sentinel-1 C-Band SAR backscatter drop in dB (open water specular reflection)
- elevation_m: Surface elevation above sea level in meters (SRTM / Copernicus DEM)
- river_proximity_km: Distance to nearest active river basin or waterway in km
- flood_occurrence: Binary target label (1 = Flood Inundation Danger, 0 = Normal / Safe)
"""

from pathlib import Path
import numpy as np
import pandas as pd


def generate_flood_benchmark_dataset(output_path: Path = None, n_samples: int = 300, seed: int = 42) -> Path:
    np.random.seed(seed)

    n_flood = int(n_samples * 0.50)
    n_safe = n_samples - n_flood

    # Flood conditions: torrential precipitation, saturated soil, steep SAR backscatter drop, low elevation, close to river
    # Non-flood conditions: light/moderate rain, dry/normal soil, minimal radar drop, higher elevation, farther from river
    rain = np.concatenate([
        np.random.normal(165.0, 35.0, n_flood),
        np.random.normal(28.0, 18.0, n_safe)
    ]).clip(0.0, 260.0)

    soil_moist = np.concatenate([
        np.random.normal(82.0, 9.0, n_flood),
        np.random.normal(42.0, 14.0, n_safe)
    ]).clip(10.0, 98.0)

    sar_drop = np.concatenate([
        np.random.normal(11.5, 2.5, n_flood),
        np.random.normal(3.2, 1.8, n_safe)
    ]).clip(0.5, 18.0)

    elevation = np.concatenate([
        np.random.exponential(35.0, n_flood),
        np.random.exponential(180.0, n_safe)
    ]).clip(5.0, 600.0)

    river_dist = np.concatenate([
        np.random.exponential(1.2, n_flood),
        np.random.exponential(8.5, n_safe)
    ]).clip(0.1, 30.0)

    # Physical Hydrological Inundation latent equation with natural environmental noise
    noise = np.random.normal(0.0, 0.75, n_samples)
    z = (
        0.035 * (rain - 80.0)
        + 0.050 * (soil_moist - 60.0)
        + 0.280 * (sar_drop - 6.5)
        - 0.015 * (elevation - 100.0)
        - 0.220 * (river_dist - 3.0)
        + noise
    )
    prob = 1.0 / (1.0 + np.exp(-z))
    flood_label = (prob > 0.50).astype(int)

    df = pd.DataFrame({
        "precipitation_24h_mm": np.round(rain, 1),
        "soil_moisture_pct": np.round(soil_moist, 1),
        "radar_backscatter_drop_db": np.round(sar_drop, 1),
        "elevation_m": np.round(elevation, 1),
        "river_proximity_km": np.round(river_dist, 2),
        "flood_occurrence": flood_label
    })

    # Shuffle
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    if output_path is None:
        base_dir = Path(__file__).resolve().parent.parent.parent
        output_path = base_dir / "data" / "raw" / "flood_hydrological_dataset.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


if __name__ == "__main__":
    out = generate_flood_benchmark_dataset()
    df = pd.read_csv(out)
    print(f"Flood dataset generated at: {out}")
    print(f"Total rows: {len(df)}")
    print(f"Class distribution: {dict(df['flood_occurrence'].value_counts())}")
    print(df.head(3))

