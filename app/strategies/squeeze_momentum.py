from .base import BaseStrategy
from ..analyzers.technical_analyzer import TechnicalAnalyzer
import pandas as pd
from typing import Dict, List


class SqueezeMomentumStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("Squeeze Momentum", {
            'bb_length': 20,
            'kc_length': 20,
            'kc_mult': 1.5,
            'mom_length': 12,
            'min_momentum': 0.5,
            'volume_threshold': 1.5  # 평균 거래량의 1.5배 이상
        })
        self.analyzer = TechnicalAnalyzer()

    async def analyze(self, stock_code: str, df: pd.DataFrame) -> Dict:
        """Squeeze Momentum 분석"""
        # 데이터 전처리
        df = df.copy()
        df['close'] = pd.to_numeric(df['stck_clpr'])  # 종가
        df['high'] = pd.to_numeric(df['stck_hgpr'])  # 고가
        df['low'] = pd.to_numeric(df['stck_lwpr'])  # 저가
        df['volume'] = pd.to_numeric(df['acml_vol'])  # 거래량

        # Squeeze Momentum 계산
        squeeze_data = self.analyzer.calculate_squeeze_momentum(df)

        # 거래량 분석
        volume_analysis = self.analyzer.calculate_volume_profile(df)

        return {
            'squeeze_data': squeeze_data,
            'volume_analysis': volume_analysis,
            'current_price': df['close'].iloc[-1],
            'current_volume': df['volume'].iloc[-1]
        }

    async def generate_signals(self, stock_code: str, analysis: Dict) -> List[Dict]:
        """매매 신호 생성"""
        signals = []
        squeeze_data = analysis['squeeze_data']
        volume_analysis = analysis['volume_analysis']

        current_momentum = squeeze_data['momentum'].iloc[-1]
        prev_momentum = squeeze_data['momentum'].iloc[-2] if len(squeeze_data['momentum']) > 1 else 0

        # Squeeze 해제 확인
        squeeze_off_current = squeeze_data['squeeze_off'].iloc[-1]
        squeeze_on_prev = squeeze_data['squeeze_on'].iloc[-2] if len(squeeze_data['squeeze_on']) > 1 else False

        # 거래량 확인
        avg_volume = volume_analysis['avg_volume'].iloc[-1]
        current_volume = analysis['current_volume']
        volume_surge = current_volume > (avg_volume * self.params['volume_threshold'])

        # 매수 신호: Squeeze 해제 + 상승 모멘텀 + 거래량 급증
        if (squeeze_off_current and squeeze_on_prev and
                current_momentum > self.params['min_momentum'] and
                current_momentum > prev_momentum and volume_surge):

            signals.append({
                'stock_code': stock_code,
                'action': 'BUY',
                'reason': 'Squeeze 해제 + 상승 모멘텀',
                'momentum': current_momentum,
                'price': analysis['current_price'],
                'confidence': min(abs(current_momentum) * 10, 100)
            })

        # 매도 신호: 모멘텀 하락 전환
        elif (current_momentum < 0 and prev_momentum > 0 and
              stock_code in self.positions):

            signals.append({
                'stock_code': stock_code,
                'action': 'SELL',
                'reason': '모멘텀 하락 전환',
                'momentum': current_momentum,
                'price': analysis['current_price'],
                'confidence': min(abs(current_momentum) * 10, 100)
            })

        return signals
