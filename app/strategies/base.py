from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import pandas as pd


class BaseStrategy(ABC):
    def __init__(self, name: str, params: Dict):
        self.name = name
        self.params = params
        self.is_active = True
        self.positions = {}  # 현재 포지션

    @abstractmethod
    async def analyze(self, stock_code: str, df: pd.DataFrame) -> Dict:
        """기술적 분석 수행"""
        pass

    @abstractmethod
    async def generate_signals(self, stock_code: str, analysis: Dict) -> List[Dict]:
        """매매 신호 생성"""
        pass

    def calculate_position_size(self, price: float, risk_amount: float) -> int:
        """포지션 크기 계산"""
        return int(risk_amount / price)

    def update_position(self, stock_code: str, action: str, quantity: int, price: float):
        """포지션 업데이트"""
        if stock_code not in self.positions:
            self.positions[stock_code] = {'quantity': 0, 'avg_price': 0}

        if action == 'BUY':
            current_qty = self.positions[stock_code]['quantity']
            current_avg = self.positions[stock_code]['avg_price']

            new_qty = current_qty + quantity
            new_avg = ((current_qty * current_avg) + (quantity * price)) / new_qty

            self.positions[stock_code] = {'quantity': new_qty, 'avg_price': new_avg}

        elif action == 'SELL':
            self.positions[stock_code]['quantity'] -= quantity
            if self.positions[stock_code]['quantity'] <= 0:
                del self.positions[stock_code]