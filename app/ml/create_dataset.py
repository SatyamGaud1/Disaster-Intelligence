"""
Generates and formats the open benchmark forest fire weather dataset.
Features:
- temperature_c: Ambient surface temperature in degrees Celsius
- relative_humidity_pct: Air moisture percentage (0-100)
- wind_speed_kmh: Wind velocity in km/h
- rainfall_mm: Recent 24h accumulated rainfall in mm
- vegetation_ndvi: Sentinel-2 normalized difference vegetation index (0.0 to 1.0)
- fire_occurrence: Binary target label (1 = Fire/High Danger, 0 = No Fire/Safe)
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd


def generate_benchmark_dataset(output_path: Path = None, n_samples: int = 300, seed: int = 42) -> Path:
    np.random.seed(seed)
    
    # Fire conditions: hot, dry, windy, low precipitation, dry vegetation (low NDVI)
    # Non-fire conditions: mild, humid, calm, rainy, moist/green vegetation (higher NDVI)
    n_fire = int(n_samples * 0.52)
    n_safe = n_samples - n_fire
    
    temp = np.concatenate([
        np.random.normal(33.5, 4.2, n_fire),
        np.random.normal(23.5, 4.8, n_safe)
    ]).clip(14.0, 44.0)

    humidity = np.concatenate([
        np.random.normal(31.0, 9.5, n_fire),
        np.random.normal(68.0, 11.5, n_safe)
    ]).clip(12.0, 95.0)

    wind = np.concatenate([
        np.random.normal(22.0, 5.5, n_fire),
        np.random.normal(13.8, 4.5, n_safe)
    ]).clip(4.0, 45.0)

    rain = np.concatenate([
        np.random.exponential(0.25, n_fire),
        np.random.exponential(6.0, n_safe)
    ]).clip(0.0, 40.0)

    ndvi = np.concatenate([
        np.random.normal(0.23, 0.06, n_fire),
        np.random.normal(0.56, 0.10, n_safe)
    ]).clip(0.08, 0.85)

    # Physical Fire Weather Index latent equation with natural meteorological noise
    noise = np.random.normal(0.0, 0.85, n_samples)
    z = (
        0.18 * (temp - 28.0)
        - 0.10 * (humidity - 50.0)
        + 0.08 * (wind - 16.0)
        - 0.40 * rain
        - 4.5 * (ndvi - 0.40)
        + noise
    )
    prob = 1.0 / (1.0 + np.exp(-z))
    fire_label = (prob > 0.50).astype(int)

    df = pd.DataFrame({
        "temperature_c": np.round(temp, 1),
        "relative_humidity_pct": np.round(humidity, 1),
        "wind_speed_kmh": np.round(wind, 1),
        "rainfall_mm": np.round(rain, 1),
        "vegetation_ndvi": np.round(ndvi, 3),
        "fire_occurrence": fire_label
    })

    # Shuffle
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    if output_path is None:
        base_dir = Path(__file__).resolve().parent.parent.parent
        output_path = base_dir / "data" / "raw" / "forest_fire_weather_dataset.csv"
        
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


if __name__ == "__main__":
    out = generate_benchmark_dataset()
    df = pd.read_csv(out)
    print(f"Dataset generated at: {out}")
    print(f"Total rows: {len(df)}")
    print(f"Class distribution: {dict(df['fire_occurrence'].value_counts())}")
    print(df.head(3))
