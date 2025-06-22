from .base import BaseStrategy
from ..analyzers.technical_analyzer import TechnicalAnalyzer
import pandas as pd
from typing import Dict, List


class MACDStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("MACD Strategy", {
            'fast_period': 12,
            'slow_period': 26,
            'signal_period': 9,
            'min_histogram': 0.1,
            'rsi_oversold': 30,
            'rsi_overbought': 70
        })
        self.analyzer = TechnicalAnalyzer()

    async def analyze(self, stock_code: str, df: pd.DataFrame) -> Dict:
        """MACD 분석"""
        # 데이터 전처리
        df = df.copy()
        df['close'] = pd.to_numeric(df['stck_clpr'])
        df['high'] = pd.to_numeric(df['stck_hgpr'])
        df['low'] = pd.to_numeric(df['stck_lwpr'])
        df['volume'] = pd.to_numeric(df['acml_vol'])

        # MACD 계산
        macd_data = self.analyzer.calculate_macd(df)

        # RSI 계산 (추가 필터)
        rsi = self.analyzer.calculate_rsi(df)

        # 거래량 분석
        volume_analysis = self.analyzer.calculate_volume_profile(df)

        return {
            'macd_data': macd_data,
            'rsi': rsi,
            'volume_analysis': volume_analysis,
            'current_price': df['close'].iloc[-1],
            'current_volume': df['volume'].iloc[-1]
        }

    async def generate_signals(self, stock_code: str, analysis: Dict) -> List[Dict]:
        """MACD 매매 신호 생성"""
        signals = []
        macd_data = analysis['macd_data']
        rsi = analysis['rsi']

        current_macd = macd_data['macd'].iloc[-1]
        current_signal = macd_data['signal'].iloc[-1]
        current_histogram = macd_data['histogram'].iloc[-1]
        prev_histogram = macd_data['histogram'].iloc[-2] if len(macd_data['histogram']) > 1 else 0

        current_rsi = rsi.iloc[-1]

        # 골든크로스 + RSI 과매도 구간
        if (current_macd > current_signal and
                prev_histogram <= 0 and current_histogram > 0 and
                current_rsi < 50 and current_histogram > self.params['min_histogram']):

            signals.append({
                'stock_code': stock_code,
                'action': 'BUY',
                'reason': 'MACD 골든크로스 + RSI 과매도',
                'macd': current_macd,
                'signal': current_signal,
                'histogram': current_histogram,
                'rsi': current_rsi,
                'price': analysis['current_price'],
                'confidence': min((current_histogram / self.params['min_histogram']) * 20, 100)
            })

        # 데드크로스 + RSI 과매수 구간
        elif (current_macd < current_signal and
              prev_histogram >= 0 and current_histogram < 0 and
              current_rsi > 50 and stock_code in self.positions):

            signals.append({
                'stock_code': stock_code,
                'action': 'SELL',
                'reason': 'MACD 데드크로스 + RSI 과매수',
                'macd': current_macd,
                'signal': current_signal,
                'histogram': current_histogram,
                'rsi': current_rsi,
                'price': analysis['current_price'],
                'confidence': min((abs(current_histogram) / self.params['min_histogram']) * 20, 100)
            })

        return signals