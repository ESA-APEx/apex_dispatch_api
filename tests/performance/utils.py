from datetime import datetime, timedelta
import random


def random_temporal_extent(start_year):
    # Random start date in 2024
    start_date = datetime.strptime(f"{start_year}-01-01", "%Y-%m-%d") + timedelta(
        days=random.randint(0, 364)
    )

    duration_days = random.randint(30, 365)

    end_date = start_date + timedelta(days=duration_days)

    return [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]
