import pandas as pd
import pytest
from src.market_data import SimulatedMarketData, validate_ohlcv

def test_simulated_data_and_invalid_data():
    assert len(SimulatedMarketData.from_closes([1,2,3]).candles)==3
    with pytest.raises(ValueError): validate_ohlcv(pd.DataFrame({'close':[1]}))
    with pytest.raises(ValueError): SimulatedMarketData.from_closes([])
