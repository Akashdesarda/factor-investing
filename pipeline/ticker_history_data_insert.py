import logging
from datetime import date
from pathlib import Path

import polars as pl
from adbc_driver_postgresql import dbapi
from alive_progress import alive_it
from dotenv import dotenv_values

from investing.core.data import Interval, Period, StockData
from investing.core.db import latest_data_query, prepare_ticker_history_table
from investing.core.exception import YahooAPIError
from investing.core.models import DBTableName
from investing.core.utils import create_batches_list

logger = logging.getLogger("factor-investing")
current_path = Path(__file__).resolve().parent

config = dotenv_values(current_path.parent / ".env")
conn_string = (
    f"postgresql://{config['USER']}:{config['PASSWORD']}@localhost:5432/playground"
)

# Getting list of tickers to download
BATCH_SIZE = 20
tickers = pl.read_csv(current_path / "tickers_nse.csv").to_series().to_list()
tickers_batches = create_batches_list(tickers, BATCH_SIZE)
logger.debug(f"total batches: {len(tickers)}")

# getting latest date to run the insert job
logger.info("getting last inserted date")
with dbapi.connect(conn_string) as conn:
    date_df = pl.read_database(latest_data_query(), conn)
    if date_df.is_empty():
        logger.info("no latest date found, running for max date")
        USE_MAX = True
    else:
        USE_MAX = False
        last_run_date = date_df.select("date").item(0, 0)
        logger.info(f"last run date: {last_run_date}")

# running batch job
total_batches = len(tickers_batches)
for current_batch in alive_it(
    tickers_batches,
    force_tty=True,
    receipt_text=True,
):
    logger.debug(f"tickers of current batch: {current_batch}")
    sd = StockData(current_batch)

    # Downloading tickers based on last run date
    if USE_MAX:
        logger.info("downloading entire historical data of all given tickers")
        result = sd.get_ticker_history(period=Period.MAX, interval=Interval.ONE_DAY)
    else:
        TODAY = date.today()
        logger.info(f"downloading from {last_run_date} to {TODAY}")
        result = sd.get_ticker_history(
            start=last_run_date, end=TODAY, interval=Interval.ONE_DAY
        )

    # preparing dataframe to insert data
    logger.info("preparing data to insert")
    data_inset_df = pl.DataFrame()
    for ticker in current_batch:
        try:
            unit_data = prepare_ticker_history_table(result[ticker.upper()], ticker)
            data_inset_df = data_inset_df.vstack(unit_data)
        except YahooAPIError as e:
            logger.warning(f"{e}, so skipping it.")

    # inserting data to the `ticker_history` table
    with dbapi.connect(conn_string) as conn:
        data_inset_df.write_database(
            DBTableName.ticker_history.value, conn, if_table_exists="append"
        )

        logger.info(f"successfully inserted {len(data_inset_df)} rows")
