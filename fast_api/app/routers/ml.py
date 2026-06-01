from math import ceil
from datetime import datetime
import pandas as pd
from fastapi import APIRouter, HTTPException,Query
import numpy as np
from pathlib import Path

router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/data")
def get_data(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=200),
):
    try:

        current_dir = Path(__file__).parent.parent.parent  # app/routers -> app
        # csv_path = current_dir / "assets" / "csv" / "melb_data.csv"
        # print(f"Current directory333: {current_dir}")
        # print(f"CSV path: {csv_path}")
        # df = pd.read_csv(csv_path)
        df = pd.read_csv(f'{current_dir}/assets/csv/melb_data.csv')
        # df = df.replace([np.inf, -np.inf], np.nan)
        # df = df.astype(object).where(pd.notna(df), None)
        # df = df.where(pd.notna(df), None)
        df = df.dropna(axis=0)
        # print(df.describe())

        total = len(df)
        start = (page - 1) * limit
        end = start + limit
        data = df.iloc[start:end].to_dict(orient="records")
        total_pages = ceil(total / limit) if total > 0 else 1
        return {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
            # "data": data,
            "avg_lot_size": df['Landsize'].mean(),
            'newest_home_age' : int(datetime.now().year) - int(df['YearBuilt'].max()),
            "columns": df.columns.tolist()
        }
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        raise HTTPException(status_code=500, detail=str(e))