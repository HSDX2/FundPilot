"""Tests for analysis Pydantic schemas."""

from datetime import date, datetime
from uuid import uuid4

from app.schemas.analysis import (
    AnalysisReportListData,
    AnalysisReportResponse,
    BatchGenerateAdviceRequest,
    BatchSentimentRequest,
    FundAdviceListData,
    FundAdviceResponse,
    GenerateAdviceRequest,
    GenerateAllReportsRequest,
    GenerateReportRequest,
    NewsSentimentResponse,
    SentimentResult,
)


class TestAnalysisReportResponse:
    def test_basic(self):
        uid = uuid4()
        data = AnalysisReportResponse(
            id=uid,
            date=date(2026, 5, 23),
            report_type="daily",
            content={"summary": "market up"},
            ai_model="deepseek-chat",
            created_at=datetime(2026, 5, 23, 16, 0),
        )
        assert data.report_type == "daily"
        assert data.content["summary"] == "market up"

    def test_ai_model_optional(self):
        data = AnalysisReportResponse(
            id=uuid4(),
            date=date.today(),
            report_type="weekly",
            content={},
            created_at=datetime.now(),
        )
        assert data.ai_model is None


class TestFundAdviceResponse:
    def test_basic(self):
        data = FundAdviceResponse(
            id=uuid4(),
            fund_id=uuid4(),
            date=date(2026, 5, 23),
            action="buy",
            reason={"technical": "bullish"},
            confidence=0.85,
            ai_model="deepseek-chat",
            created_at=datetime(2026, 5, 23, 16, 0),
        )
        assert data.action == "buy"
        assert data.confidence == 0.85

    def test_minimal(self):
        data = FundAdviceResponse(
            id=uuid4(),
            fund_id=uuid4(),
            date=date.today(),
            action="hold",
            reason={},
            created_at=datetime.now(),
        )
        assert data.confidence is None
        assert data.ai_model is None


class TestGenerateReportRequest:
    def test_default_report_type(self):
        req = GenerateReportRequest(sector_id=uuid4())
        assert req.report_type == "daily"

    def test_explicit_report_type(self):
        req = GenerateReportRequest(sector_id=uuid4(), report_type="weekly")
        assert req.report_type == "weekly"


class TestGenerateAllReportsRequest:
    def test_defaults(self):
        req = GenerateAllReportsRequest()
        assert req.report_type == "daily"
        assert req.limit == 10

    def test_custom(self):
        req = GenerateAllReportsRequest(report_type="monthly", limit=5)
        assert req.limit == 5


class TestGenerateAdviceRequest:
    def test_requires_fund_id(self):
        req = GenerateAdviceRequest(fund_id=uuid4())
        assert req.fund_id is not None


class TestBatchGenerateAdviceRequest:
    def test_requires_fund_ids(self):
        ids = [uuid4(), uuid4()]
        req = BatchGenerateAdviceRequest(fund_ids=ids)
        assert len(req.fund_ids) == 2


class TestBatchSentimentRequest:
    def test_default_limit(self):
        req = BatchSentimentRequest()
        assert req.limit == 20

    def test_custom_limit(self):
        req = BatchSentimentRequest(limit=50)
        assert req.limit == 50


class TestNewsSentimentResponse:
    def test_basic(self):
        uid = uuid4()
        resp = NewsSentimentResponse(
            processed=3,
            results=[SentimentResult(news_id=uid, sentiment_score=75.0)],
        )
        assert resp.processed == 3
        assert resp.results[0].sentiment_score == 75.0

    def test_defaults(self):
        resp = NewsSentimentResponse(processed=0)
        assert resp.processed == 0
        assert resp.results == []


class TestAnalysisReportListData:
    def test_basic(self):
        data = AnalysisReportListData(items=[], total=0)
        assert data.page == 1
        assert data.page_size == 20


class TestFundAdviceListData:
    def test_basic(self):
        data = FundAdviceListData(items=[], total=0)
        assert data.page == 1
        assert data.page_size == 20
