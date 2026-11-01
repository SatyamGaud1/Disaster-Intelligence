"""
Generates and formats the open benchmark agricultural drought dataset.
Features:
- ndvi_anomaly: Sentinel-2 NDVI drop relative to historical seasonal baseline (-0.45 to +0.10)
- ndwi_moisture: Sentinel-2 NDWI canopy liquid moisture index (-0.35 to +0.30)
- vci_percent: Vegetation Condition Index historical percentile (0.0 to 100.0%)
- precipitation_deficit_pct: 90-day seasonal rainfall deficit percentage (0.0 to 100.0%)
- soil_temperature_c: Soil root-zone temperature in degrees Celsius (18.0 to 46.0°C)
- drought_occurrence: Binary target label (1 = Severe Agricultural Drought, 0 = Healthy/Normal Crop)
"""

from pathlib import Path
import numpy as np
import pandas as pd


def generate_drought_benchmark_dataset(output_path: Path = None, n_samples: int = 300, seed: int = 42) -> Path:
    np.random.seed(seed)

    n_drought = int(n_samples * 0.50)
    n_safe = n_samples - n_drought

    # Drought conditions: severe negative NDVI anomaly, negative NDWI, low VCI, high rainfall deficit, high soil temperature
    # Safe conditions: neutral/positive NDVI, positive NDWI, high VCI, low rainfall deficit, cool/normal soil temperature
    ndvi_anom = np.concatenate([
        np.random.normal(-0.32, 0.06, n_drought),
        np.random.normal(0.02, 0.05, n_safe)
    ]).clip(-0.45, 0.15)

    ndwi_moist = np.concatenate([
        np.random.normal(-0.25, 0.05, n_drought),
        np.random.normal(0.18, 0.06, n_safe)
    ]).clip(-0.35, 0.35)

    vci = np.concatenate([
        np.random.normal(16.0, 5.0, n_drought),
        np.random.normal(68.0, 12.0, n_safe)
    ]).clip(5.0, 95.0)

    deficit = np.concatenate([
        np.random.normal(72.0, 12.0, n_drought),
        np.random.normal(22.0, 10.0, n_safe)
    ]).clip(0.0, 98.0)

    soil_temp = np.concatenate([
        np.random.normal(38.5, 3.5, n_drought),
        np.random.normal(26.0, 4.0, n_safe)
    ]).clip(18.0, 46.0)

    # Physical Agricultural Crop Stress latent equation with natural noise
    noise = np.random.normal(0.0, 0.75, n_samples)
    z = (
        - 8.5 * ndvi_anom
        - 7.2 * ndwi_moist
        - 0.065 * (vci - 40.0)
        + 0.045 * (deficit - 45.0)
        + 0.150 * (soil_temp - 30.0)
        + noise
    )
    prob = 1.0 / (1.0 + np.exp(-z))
    drought_label = (prob > 0.50).astype(int)

    df = pd.DataFrame({
        "ndvi_anomaly": np.round(ndvi_anom, 3),
        "ndwi_moisture": np.round(ndwi_moist, 3),
        "vci_percent": np.round(vci, 1),
        "precipitation_deficit_pct": np.round(deficit, 1),
        "soil_temperature_c": np.round(soil_temp, 1),
        "drought_occurrence": drought_label
    })

    # Shuffle
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    if output_path is None:
        base_dir = Path(__file__).resolve().parent.parent.parent
        output_path = base_dir / "data" / "raw" / "drought_agricultural_dataset.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


if __name__ == "__main__":
    out = generate_drought_benchmark_dataset()
    df = pd.read_csv(out)
    print(f"Drought dataset generated at: {out}")
    print(f"Total rows: {len(df)}")
    print(f"Class distribution: {dict(df['drought_occurrence'].value_counts())}")
    print(df.head(3))

