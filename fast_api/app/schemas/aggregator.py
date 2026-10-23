from typing import Optional

from pydantic import BaseModel, Field, field_validator


class WeatherResponse(BaseModel):
    location: str = Field(..., description="City name")
    condition: str = Field(..., description="Weather condition text")
    temperature_c: int = Field(..., description="Temperature in Celsius")


class CryptoResponse(BaseModel):
    symbol: str = Field(..., description="Crypto symbol")
    price_usd: float = Field(..., description="Price in USD")

    @field_validator("price_usd")
    @classmethod
    def price_must_be_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Price must be positive")
        return value


class NewsItem(BaseModel):
    id: int = Field(..., description="Story ID")
    title: str = Field(..., description="Story title")
    author: Optional[str] = Field(None, description="Story author")
    score: int = Field(default=0, description="Upvote count")
    url: Optional[str] = Field(None, description="Story URL")

    @field_validator("score")
    @classmethod
    def score_must_be_non_negative(cls, value: int) -> int:
        return max(value, 0)


class AggregateResponse(BaseModel):
    weather: Optional[WeatherResponse] = Field(None, description="Weather data")
    crypto: Optional[CryptoResponse] = Field(None, description="Crypto data")
    news: Optional[NewsItem] = Field(None, description="News data")
    failed_sources: list[str] = Field(default_factory=list, description="Failed providers")
