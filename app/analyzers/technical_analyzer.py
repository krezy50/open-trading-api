import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


class TechnicalAnalyzer:
    @staticmethod
    def calculate_sma(series: pd.Series, period: int) -> pd.Series:
        """단순이동평균 계산"""
        return series.rolling(window=period).mean()

    @staticmethod
    def calculate_ema(series: pd.Series, period: int) -> pd.Series:
        """지수이동평균 계산"""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """ATR (Average True Range) 계산"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    @staticmethod
    def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2) -> Tuple[
        pd.Series, pd.Series, pd.Series]:
        """볼린저 밴드 계산"""
        sma = TechnicalAnalyzer.calculate_sma(df['close'], period)
        std = df['close'].rolling(window=period).std()

        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)

        return upper_band, sma, lower_band

    @staticmethod
    def calculate_squeeze_momentum(df: pd.DataFrame, bb_length: int = 20, kc_length: int = 20,
                                   kc_mult: float = 1.5, mom_length: int = 12) -> Dict:
        """
        Squeeze Momentum Indicator 계산
        """
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = TechnicalAnalyzer.calculate_bollinger_bands(df, bb_length)

        # Keltner Channel
        hl2 = (df['high'] + df['low']) / 2
        kc_middle = TechnicalAnalyzer.calculate_sma(hl2, kc_length)
        atr = TechnicalAnalyzer.calculate_atr(df, kc_length)
        kc_upper = kc_middle + (atr * kc_mult)
        kc_lower = kc_middle - (atr * kc_mult)

        # Squeeze 조건 확인
        squeeze_on = (bb_lower > kc_lower) & (bb_upper < kc_upper)
        squeeze_off = (bb_lower < kc_lower) | (bb_upper > kc_upper)
        no_squeeze = ~(squeeze_on | squeeze_off)

        # Momentum 계산
        highest = df['high'].rolling(window=mom_length).max()
        lowest = df['low'].rolling(window=mom_length).min()
        m1 = (highest + lowest) / 2
        m2 = (m1 + TechnicalAnalyzer.calculate_sma(df['close'], mom_length)) / 2
        momentum = df['close'] - m2

        # Linear Regression을 이용한 모멘텀 값 계산
        momentum_values = []
        for i in range(len(momentum)):
            if i < mom_length:
                momentum_values.append(0)
            else:
                y = momentum.iloc[i - mom_length + 1:i + 1].values
                x = np.arange(len(y))
                if len(y) > 1:
                    slope = np.polyfit(x, y, 1)[0]
                    momentum_values.append(slope)
                else:
                    momentum_values.append(0)

        return {
            'squeeze_on': squeeze_on,
            'squeeze_off': squeeze_off,
            'no_squeeze': no_squeeze,
            'momentum': pd.Series(momentum_values, index=df.index),
            'bb_upper': bb_upper,
            'bb_lower': bb_lower,
            'kc_upper': kc_upper,
            'kc_lower': kc_lower
        }

    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """MACD 계산"""
        # 지수이동평균 계산
        ema_fast = TechnicalAnalyzer.calculate_ema(df['close'], fast)
        ema_slow = TechnicalAnalyzer.calculate_ema(df['close'], slow)

        # MACD 라인
        macd_line = ema_fast - ema_slow

        # Signal 라인
        macd_signal = TechnicalAnalyzer.calculate_ema(macd_line, signal)

        # Histogram
        macd_histogram = macd_line - macd_signal

        return {
            'macd': macd_line,
            'signal': macd_signal,
            'histogram': macd_histogram
        }

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = df['close'].diff()

        # 상승분과 하락분 분리
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        # 평균 상승분과 평균 하락분 계산 (Wilder's smoothing)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        # 첫 번째 계산 후 Wilder's smoothing 적용
        for i in range(period, len(gain)):
            avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
            avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

        # RS와 RSI 계산
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Dict:
        """스토캐스틱 계산"""
        lowest_low = df['low'].rolling(window=k_period).min()
        highest_high = df['high'].rolling(window=k_period).max()

        # %K 계산
        k_percent = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))

        # %D 계산 (%K의 이동평균)
        d_percent = k_percent.rolling(window=d_period).mean()

        return {
            'k_percent': k_percent,
            'd_percent': d_percent
        }

    @staticmethod
    def calculate_williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Williams %R 계산"""
        highest_high = df['high'].rolling(window=period).max()
        lowest_low = df['low'].rolling(window=period).min()

        williams_r = -100 * ((highest_high - df['close']) / (highest_high - lowest_low))

        return williams_r

    @staticmethod
    def calculate_cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """CCI (Commodity Channel Index) 계산"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = typical_price.rolling(window=period).mean()

        # Mean Deviation 계산
        mad = typical_price.rolling(window=period).apply(
            lambda x: np.mean(np.abs(x - x.mean())), raw=True
        )

        cci = (typical_price - sma_tp) / (0.015 * mad)

        return cci

    @staticmethod
    def calculate_volume_profile(df: pd.DataFrame, bins: int = 20) -> Dict:
        """거래량 프로파일 분석"""
        # 가격대별 거래량 분석
        try:
            price_bins = pd.cut(df['close'], bins=bins)
            price_volume = df.groupby(price_bins)['volume'].sum()

            # POC (Point of Control) - 최대 거래량 가격대
            max_volume_idx = price_volume.idxmax()
            poc = max_volume_idx.mid if hasattr(max_volume_idx, 'mid') else df['close'].median()

            return {
                'volume_profile': price_volume,
                'poc': poc,  # Point of Control
                'avg_volume': df['volume'].rolling(20).mean()
            }
        except Exception as e:
            # 에러 발생시 기본값 반환
            return {
                'volume_profile': pd.Series(dtype=float),
                'poc': df['close'].iloc[-1] if len(df) > 0 else 0,
                'avg_volume': df['volume'].rolling(20).mean() if 'volume' in df.columns else pd.Series(dtype=float)
            }

    @staticmethod
    def calculate_obv(df: pd.DataFrame) -> pd.Series:
        """OBV (On Balance Volume) 계산"""
        obv = pd.Series(index=df.index, dtype=float)
        obv.iloc[0] = df['volume'].iloc[0]

        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i - 1]:
                obv.iloc[i] = obv.iloc[i - 1] + df['volume'].iloc[i]
            elif df['close'].iloc[i] < df['close'].iloc[i - 1]:
                obv.iloc[i] = obv.iloc[i - 1] - df['volume'].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i - 1]

        return obv

    @staticmethod
    def calculate_adx(df: pd.DataFrame, period: int = 14) -> Dict:
        """ADX (Average Directional Index) 계산"""
        # True Range 계산
        tr = TechnicalAnalyzer.calculate_atr(df, 1) * 1  # 1일 TR

        # Directional Movement 계산
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        # Smoothed values
        tr_smooth = tr.rolling(window=period).mean()
        plus_dm_smooth = plus_dm.rolling(window=period).mean()
        minus_dm_smooth = minus_dm.rolling(window=period).mean()

        # Directional Indicators
        plus_di = 100 * (plus_dm_smooth / tr_smooth)
        minus_di = 100 * (minus_dm_smooth / tr_smooth)

        # ADX 계산
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di
        }