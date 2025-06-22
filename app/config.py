# app/config.py (수정된 코드)
from pydantic_settings import BaseSettings, SettingsConfigDict # Pydantic v2 스타일 임포트

class Settings(BaseSettings):
    # Pydantic v2의 설정: .env 파일을 로드하고, 환경 변수 이름의 대소문자를 무시합니다.
    # env_prefix=''는 모든 환경 변수 앞에 특정 접두사가 붙을 때 사용합니다. (여기서는 필요 없음)
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_case_sensitive=False # <-- 이 부분을 꼭 추가하세요! 대소문자 무시.
                                 # 예를 들어 .env의 URL_BASE와 Settings의 url_base를 매칭시킬 수 있습니다.
    )

    # KIS API 설정
    KIS_APP_KEY: str
    KIS_APP_SECRET: str
    KIS_ACCOUNT_NO: str # 이제 .env에 있으니 문제 없음

    # !!! 이 필드를 추가하세요 !!!
    # .env의 URL_BASE를 받기 위함
    url_base: str

    # !!! 이 필드를 추가하세요 !!!
    # .env의 ACNT_PRDT_CD를 받기 위함
    acnt_prdt_cd: str

    # 기존 KIS_ACCOUNT_PRODUCT_CD는 이제 필요 없을 수도 있습니다.
    # 만약 이 필드가 코드 내 다른 곳에서 사용된다면,
    # 'acnt_prdt_cd' 값을 여기에 할당하거나,
    # KIS_ACCOUNT_PRODUCT_CD: str = Field(alias="acnt_prdt_cd") 처럼 매핑할 수 있습니다.
    # 가장 간단한 방법은 'acnt_prdt_cd'를 직접 사용하는 것입니다.
    # 만약 KIS_ACCOUNT_PRODUCT_CD가 필요하다면, 아래와 같이 acnt_prdt_cd의 값을 할당할 수 있습니다.
    # KIS_ACCOUNT_PRODUCT_CD: str = "01" # 이 부분은 이제 acnt_prdt_cd가 대체할 수 있습니다.
                                     # 만약 기존 KIS_ACCOUNT_PRODUCT_CD를 계속 사용하고 싶다면,
                                     # KIS_ACCOUNT_PRODUCT_CD: str = Field(alias="ACNT_PRDT_CD")
                                     # 또는 단순히 acnt_prdt_cd의 값을 KIS_ACCOUNT_PRODUCT_CD에 할당

    KIS_IS_MOCK: bool = False # 이 필드는 기본값이 있으므로 .env에 없어도 됩니다.

    # 데이터베이스 설정
    DATABASE_URL: str = "sqlite:///./trading.db"

    # 매매 설정
    MAX_POSITION_SIZE: float = 1000000
    RISK_PER_TRADE: float = 0.02

    # 스케줄러 설정
    TRADING_START_TIME: str = "09:00"
    TRADING_END_TIME: str = "15:20"

settings = Settings()