import logging
from dataclasses import dataclass
from datetime import date

import polars as pl
import yfinance as yf

from investing.core.models import Interval, Period, StockExchangeYahooIdentifier

logger = logging.getLogger("factor-investing")


@dataclass
class StockData:
    """
    A class to interact with stock data provided by yfinanc api.

    Attributes
    ----------
        ticker : str | list[str]
            Ticker or list of ticker symbol the stock data.
    """

    ticker: str | list[str]
    exchage_market: StockExchangeYahooIdentifier | None = (
        StockExchangeYahooIdentifier.nse
    )

    # TickerData = namedtuple("TickerData", [])

    def __post_init__(self):
        self._ticker_without_exchange = self._remove_exchange_symbol(self.ticker)
        if isinstance(self.ticker, str):
            # python splits all letters of string & we'll have many keys instead of one
            self._ticker_data = dict.fromkeys([self._ticker_without_exchange])

        if isinstance(self.ticker, list):
            self._ticker_data = dict.fromkeys(self._ticker_without_exchange)

    @property
    def yahoo_aware_ticker(self) -> str | list[str]:
        return self._add_exchange_symbol(
            self._ticker_without_exchange, self.exchage_market.value
        )

    @property
    def ticker_handler(self) -> yf.Ticker | yf.Tickers:
        return (
            yf.Ticker(self.yahoo_aware_ticker)
            if isinstance(self.ticker, str)
            else yf.Tickers(" ".join(self.yahoo_aware_ticker))
        )

    def get_ticker_info(self) -> dict[str, dict]:
        if isinstance(self.ticker_handler, yf.Ticker):
            self._ticker_data[self._ticker_without_exchange] = (
                self.ticker_handler.get_info()
            )
        else:
            for ex_tick, tick in zip(
                self.yahoo_aware_ticker, self._ticker_without_exchange
            ):
                self._ticker_data[tick] = self.ticker_handler.tickers[
                    ex_tick
                ].get_info()

        return self._ticker_data

    def get_ticker_history(
        self,
        period: Period = Period.MAX,
        interval: Interval = Interval.ONE_DAY,
        start: str | date | None = None,
        end: str | date | None = None,
    ) -> dict[str, pl.DataFrame]:
        if isinstance(self.ticker, str):
            result = self.ticker_handler.history(
                period=period.value,
                interval=interval.value,
                start=start,
                end=end,
                actions=False,
                raise_errors=True,
                # NOTE - not present in single `Tickers` object
                # progress=False,
                # group_by="ticker",
            )
            self._ticker_data[self._ticker_without_exchange] = pl.from_pandas(
                result, include_index=True
            )

        else:
            result = self.ticker_handler.history(
                period=period.value,
                interval=interval.value,
                start=start,
                end=end,
                group_by="ticker",
                actions=False,
                progress=False,
                # raise_errors=True, # NOTE - currently not supported by `Tickers` object
            )
            for ex_tick, tick in zip(
                self.yahoo_aware_ticker, self._ticker_without_exchange
            ):
                self._ticker_data[tick] = pl.from_pandas(
                    result[ex_tick], include_index=True
                )

        return self._ticker_data

    # TODO - add methods supporting all other api functionality provided by YFinance

    @staticmethod
    def _remove_exchange_symbol(symbol: str | list[str]) -> str | list[str]:
        if isinstance(symbol, str):
            return symbol.split(".")[0]
        else:
            return [i.split(".")[0] for i in symbol]

    @staticmethod
    def _add_exchange_symbol(symbol: str | list[str], exchange) -> str | list[str]:
        if isinstance(symbol, str):
            return symbol + exchange
        else:
            return [i + exchange for i in symbol]
