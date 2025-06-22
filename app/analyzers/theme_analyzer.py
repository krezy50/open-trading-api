import requests
import pandas as pd
from bs4 import BeautifulSoup
import asyncio
import aiohttp
from typing import Dict, List
import re


class ThemeAnalyzer:
    def __init__(self):
        self.theme_keywords = [
            "AI", "인공지능", "반도체", "2차전지", "전기차", "바이오", "헬스케어",
            "메타버스", "NFT", "블록체인", "ESG", "친환경", "수소", "태양광",
            "게임", "엔터테인먼트", "K-POP", "방산", "우주항공", "로봇"
        ]

    async def get_hot_themes(self) -> List[Dict]:
        """네이버 금융에서 급등 테마 수집"""
        try:
            url = "https://finance.naver.com/sise/theme.naver"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    html = await response.text()

            soup = BeautifulSoup(html, 'html.parser')
            theme_table = soup.find('table', {'class': 'type_1'})

            themes = []
            if theme_table:
                rows = theme_table.find_all('tr')[2:]  # 헤더 제외

                for row in rows[:10]:  # 상위 10개 테마
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        theme_name = cols[0].get_text(strip=True)
                        change_rate = cols[2].get_text(strip=True)

                        # 상승률이 양수인 테마만 선택
                        if '+' in change_rate:
                            themes.append({
                                'name': theme_name,
                                'change_rate': change_rate,
                                'url': cols[0].find('a')['href'] if cols[0].find('a') else None
                            })

            return themes

        except Exception as e:
            print(f"테마 분석 오류: {e}")
            return []

    async def get_theme_stocks(self, theme_url: str) -> List[str]:
        """특정 테마의 종목 코드 수집"""
        try:
            if not theme_url:
                return []

            full_url = f"https://finance.naver.com{theme_url}"

            async with aiohttp.ClientSession() as session:
                async with session.get(full_url) as response:
                    html = await response.text()

            soup = BeautifulSoup(html, 'html.parser')
            stock_table = soup.find('table', {'class': 'type_1'})

            stock_codes = []
            if stock_table:
                rows = stock_table.find_all('tr')[2:]  # 헤더 제외

                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        stock_link = cols[0].find('a')
                        if stock_link and 'code=' in stock_link['href']:
                            code = re.search(r'code=(\d+)', stock_link['href'])
                            if code:
                                stock_codes.append(code.group(1))

            return stock_codes[:20]  # 상위 20개 종목

        except Exception as e:
            print(f"테마 종목 수집 오류: {e}")
            return []

    async def analyze_sector_flow(self) -> Dict:
        """섹터별 자금 흐름 분석"""
        try:
            url = "https://finance.naver.com/sise/sise_group.naver?type=group"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    html = await response.text()

            soup = BeautifulSoup(html, 'html.parser')
            sector_table = soup.find('table', {'class': 'type_1'})

            sectors = []
            if sector_table:
                rows = sector_table.find_all('tr')[2:]

                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        sector_name = cols[0].get_text(strip=True)
                        change_rate = cols[2].get_text(strip=True)
                        volume = cols[4].get_text(strip=True) if len(cols) > 4 else "0"

                        sectors.append({
                            'name': sector_name,
                            'change_rate': change_rate,
                            'volume': volume
                        })

            # 상승률 기준으로 정렬
            sectors.sort(key=lambda x: float(x['change_rate'].replace('%', '').replace('+', '').replace('-', '0')),
                         reverse=True)

            return {
                'hot_sectors': sectors[:5],
                'all_sectors': sectors
            }

        except Exception as e:
            print(f"섹터 분석 오류: {e}")
            return {'hot_sectors': [], 'all_sectors': []}

    async def get_volume_surge_stocks(self) -> List[str]:
        """거래량 급증 종목 찾기"""
        try:
            url = "https://finance.naver.com/sise/sise_quant.naver"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    html = await response.text()

            soup = BeautifulSoup(html, 'html.parser')
            stock_table = soup.find('table', {'class': 'type_2'})

            volume_stocks = []
            if stock_table:
                rows = stock_table.find_all('tr')[2:]

                for row in rows[:30]:  # 상위 30개
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        stock_link = cols[1].find('a')
                        if stock_link and 'code=' in stock_link['href']:
                            code = re.search(r'code=(\d+)', stock_link['href'])
                            if code:
                                volume_stocks.append(code.group(1))

            return volume_stocks

        except Exception as e:
            print(f"거래량 급증 종목 분석 오류: {e}")
            return []