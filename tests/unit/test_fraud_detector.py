import pytest
import asyncio
from datetime import datetime
from src.models.data_models import ProductInfo, DetectionResult
from src.detectors.fraud_detector import FraudDetector
from src.storage.context_storage import ContextStorage
from src.detectors.data_collector import DataCollector
from src.detectors.comparator import ProductComparator

class TestFraudDetector:
    """FraudDetector 유닛 테스트"""
    
    @pytest.fixture
    def context_storage(self):
        """ContextStorage 객체 생성"""
        return ContextStorage(storage_type="memory")
        
    @pytest.fixture
    def data_collector(self, monkeypatch):
        """DataCollector 객체 생성 및 모의 데이터 설정"""
        collector = DataCollector()
        
        # collect_via_mcp 메서드 모킹 - endpoint 매개변수에 기본값 추가
        async def mock_collect_via_mcp(product_id, endpoint="get_product", request_params=None):
            return ProductInfo(
                product_id=product_id,
                price=100000,
                description="상품 설명"
            )
            
        # collect_via_web 메서드 모킹
        async def mock_collect_via_web(product_id, url_template=None):
            # 상품 ID에 따라 다른 결과 반환
            if product_id == "PROD_PRICE_CHANGE":
                return ProductInfo(
                    product_id=product_id,
                    price=120000,  # 20% 가격 인상
                    description="상품 설명"
                )
            elif product_id == "PROD_DESC_CHANGE":
                return ProductInfo(
                    product_id=product_id,
                    price=100000,
                    description="변경된 상품 설명"  # 설명 변경
                )
            else:
                return ProductInfo(
                    product_id=product_id,
                    price=100000,
                    description="상품 설명"
                )
                
        monkeypatch.setattr(collector, "collect_via_mcp", mock_collect_via_mcp)
        monkeypatch.setattr(collector, "collect_via_web", mock_collect_via_web)
        
        return collector
        
    @pytest.fixture
    def fraud_detector(self, context_storage, data_collector):
        """FraudDetector 객체 생성"""
        comparator = ProductComparator(
            price_threshold=0.05,  # 5% 가격 변화 임계값
            description_similarity_threshold=0.8
        )
        
        return FraudDetector(
            context_storage=context_storage,
            data_collector=data_collector,
            product_comparator=comparator
        )
        
    @pytest.mark.asyncio
    async def test_normal_scenario(self, context_storage, fraud_detector):
        """정상 시나리오 테스트"""
        # 1. 원본 문맥 저장
        session_id = "test_session"
        product_id = "PROD_NORMAL"
        
        original_info = ProductInfo(
            product_id=product_id,
            price=100000,
            description="상품 설명"
        )
        
        context_storage.store_context(
            session_id=session_id,
            product_id=product_id,
            product_info=original_info
        )
        
        # 2. 검증 실행
        detection_result = await fraud_detector.verify_product(session_id, product_id)
        
        # 3. 결과 확인
        assert detection_result is not None
        assert detection_result.is_fraud_detected is False
        assert not detection_result.changes
        
    @pytest.mark.asyncio
    async def test_price_change_scenario(self, context_storage, fraud_detector):
        """가격 변경 시나리오 테스트"""
        # 1. 원본 문맥 저장
        session_id = "test_session"
        product_id = "PROD_PRICE_CHANGE"
        
        original_info = ProductInfo(
            product_id=product_id,
            price=100000,
            description="상품 설명"
        )
        
        context_storage.store_context(
            session_id=session_id,
            product_id=product_id,
            product_info=original_info
        )
        
        # 2. 검증 실행
        detection_result = await fraud_detector.verify_product(session_id, product_id)
        
        # 3. 결과 확인
        assert detection_result is not None
        assert detection_result.is_fraud_detected is True
        assert "price" in detection_result.changes
        assert detection_result.changes["price"]["original"] == 100000
        assert detection_result.changes["price"]["current"] == 120000
        
    @pytest.mark.asyncio
    async def test_description_change_scenario(self, context_storage, fraud_detector):
        """설명 변경 시나리오 테스트"""
        # 1. 원본 문맥 저장
        session_id = "test_session"
        product_id = "PROD_DESC_CHANGE"
        
        original_info = ProductInfo(
            product_id=product_id,
            price=100000,
            description="상품 설명"
        )
        
        context_storage.store_context(
            session_id=session_id,
            product_id=product_id,
            product_info=original_info
        )
        
        # 2. 검증 실행
        detection_result = await fraud_detector.verify_product(session_id, product_id)
        
        # 3. 결과 확인
        assert detection_result is not None
        assert detection_result.is_fraud_detected is True
        assert "description" in detection_result.changes
        assert detection_result.changes["description"]["original"] == "상품 설명"
        assert detection_result.changes["description"]["current"] == "변경된 상품 설명"
        
    @pytest.mark.asyncio
    async def test_notification_creation(self, context_storage, fraud_detector):
        """알림 생성 테스트"""
        # 결과 객체 생성
        detection_result = DetectionResult(
            session_id="test_session",
            product_id="PROD123",
            is_fraud_detected=True,
            changes={
                "price": {
                    "original": 100000,
                    "current": 120000,
                    "change_ratio": 0.2
                }
            },
            details="가격 변경 감지"
        )
        
        # 알림 생성
        notification = fraud_detector.create_notification(detection_result)
        
        # 결과 확인
        assert notification is not None
        assert notification.session_id == "test_session"
        assert notification.product_id == "PROD123"
        assert notification.severity == "warning"
        assert notification.action_required is True
        assert "가격" in notification.message 