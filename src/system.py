from typing import Dict, Any, Optional, List, Callable
import asyncio
from datetime import datetime
from loguru import logger

from src.models.data_models import ProductInfo, DetectionResult, ContextRecord, NotificationMessage
from src.interfaces.mcp_interface import MCPInterface, MCPProxy
from src.storage.context_storage import ContextStorage
from src.detectors.data_collector import DataCollector
from src.detectors.comparator import ProductComparator
from src.detectors.fraud_detector import FraudDetector
from src.notification.notifier import Notifier, DefaultNotificationHandlers

class FraudDetectionSystem:
    """
    AI 쇼핑 속임수 탐지 시스템
    모든 구성 요소를 통합하여 전체 시스템 동작 관리
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: 시스템 설정
        """
        config = config or {}
        
        # 컴포넌트 초기화
        self.mcp_interface = MCPInterface()
        self.mcp_proxy = MCPProxy(self.mcp_interface)
        self.context_storage = ContextStorage(
            storage_type=config.get("storage_type", "memory")
        )
        self.data_collector = DataCollector(
            mcp_interface=self.mcp_interface
        )
        self.product_comparator = ProductComparator(
            price_threshold=config.get("price_threshold", 0.05),
            description_similarity_threshold=config.get("description_threshold", 0.8)
        )
        self.fraud_detector = FraudDetector(
            context_storage=self.context_storage,
            data_collector=self.data_collector,
            product_comparator=self.product_comparator
        )
        self.notifier = Notifier()
        
        # 기본 알림 핸들러 등록
        self._setup_default_handlers()
        
        # 인터셉터 등록
        self._setup_interceptors()
        
        # 자동 검증 타이머 초기화
        self.auto_verify_interval = config.get("auto_verify_interval", 300)  # 기본 5분
        self.auto_verify_enabled = config.get("auto_verify_enabled", False)
        self._verify_tasks = {}  # {session_id: task}
        
        logger.info("AI 쇼핑 속임수 탐지 시스템 초기화 완료")
        
    def _setup_default_handlers(self):
        """기본 알림 핸들러 설정"""
        self.notifier.register_handler("info", DefaultNotificationHandlers.console_handler)
        self.notifier.register_handler("warning", DefaultNotificationHandlers.console_handler)
        self.notifier.register_handler("error", DefaultNotificationHandlers.console_handler)
        
        self.notifier.register_handler("info", DefaultNotificationHandlers.log_handler)
        self.notifier.register_handler("warning", DefaultNotificationHandlers.log_handler)
        self.notifier.register_handler("error", DefaultNotificationHandlers.log_handler)
        
        self.notifier.register_handler("warning", DefaultNotificationHandlers.agent_response_handler)
        self.notifier.register_handler("error", DefaultNotificationHandlers.agent_response_handler)
        
    def _setup_interceptors(self):
        """MCP 인터셉터 설정"""
        # 응답 인터셉터 - 상품 정보 추출 및 저장
        def product_response_interceptor(response_data: Dict[str, Any]) -> Dict[str, Any]:
            try:
                session_id = response_data.get("session_id", "unknown")
                product_data = response_data.get("product", {})
                
                if not product_data:
                    return response_data
                    
                product_info = self.mcp_interface.extract_product_info(product_data)
                if product_info:
                    self.context_storage.store_context(
                        session_id=session_id,
                        product_id=product_info.product_id,
                        product_info=product_info,
                        source_url=response_data.get("source_url")
                    )
            except Exception as e:
                logger.error(f"응답 인터셉터 오류: {e}")
                
            return response_data
            
        # 상품 응답 인터셉터 등록
        self.mcp_interface.register_response_interceptor("get_product", product_response_interceptor)
        self.mcp_interface.register_response_interceptor("search_products", product_response_interceptor)
        
    async def on_product_view(self, session_id: str, product_id: str, product_data: Dict[str, Any]) -> bool:
        """상품 조회 시 핸들러 - 상품 정보 저장"""
        try:
            product_info = self.mcp_interface.extract_product_info(product_data)
            if not product_info:
                logger.warning(f"상품 정보를 추출할 수 없음: {product_id}")
                return False
                
            success = self.context_storage.store_context(
                session_id=session_id,
                product_id=product_id,
                product_info=product_info
            )
            
            logger.info(f"상품 조회 처리: 세션 {session_id}, 상품 {product_id}")
            return success
        except Exception as e:
            logger.error(f"상품 조회 처리 중 오류 발생: {e}")
            return False
    
    async def verify_product_now(self, session_id: str, product_id: str) -> Optional[DetectionResult]:
        """즉시 상품 검증 수행"""
        try:
            detection_result = await self.fraud_detector.verify_product(session_id, product_id)
            
            if detection_result and detection_result.is_fraud_detected:
                # 알림 발송
                notification = self.fraud_detector.create_notification(detection_result)
                if notification:
                    self.notifier.notify(notification)
                    
            return detection_result
        except Exception as e:
            logger.error(f"상품 검증 중 오류 발생: {e}")
            return None
            
    async def on_add_to_cart(self, session_id: str, product_id: str) -> Optional[DetectionResult]:
        """장바구니 추가 이벤트 핸들러 - 상품 검증"""
        logger.info(f"장바구니 추가: 세션 {session_id}, 상품 {product_id}")
        return await self.verify_product_now(session_id, product_id)
        
    async def on_checkout(self, session_id: str, product_ids: List[str]) -> Dict[str, DetectionResult]:
        """결제 진행 이벤트 핸들러 - 모든 상품 검증"""
        logger.info(f"결제 진행: 세션 {session_id}, 상품 {len(product_ids)}개")
        
        results = {}
        for product_id in product_ids:
            result = await self.verify_product_now(session_id, product_id)
            if result:
                results[product_id] = result
                
        return results
        
    async def start_auto_verification(self, session_id: str, product_ids: List[str]):
        """자동 검증 시작"""
        if not self.auto_verify_enabled:
            logger.info("자동 검증이 비활성화되어 있음")
            return
            
        async def verify_periodically():
            try:
                while True:
                    logger.info(f"자동 검증 시작: 세션 {session_id}")
                    for product_id in product_ids:
                        await self.verify_product_now(session_id, product_id)
                    await asyncio.sleep(self.auto_verify_interval)
            except asyncio.CancelledError:
                logger.info(f"자동 검증 중단: 세션 {session_id}")
            except Exception as e:
                logger.error(f"자동 검증 중 오류 발생: {e}")
                
        # 이미 실행 중인 태스크가 있으면 취소
        if session_id in self._verify_tasks:
            self._verify_tasks[session_id].cancel()
            
        # 새 태스크 시작
        task = asyncio.create_task(verify_periodically())
        self._verify_tasks[session_id] = task
        logger.info(f"자동 검증 시작됨: 세션 {session_id}, 상품 {len(product_ids)}개")
        
    def stop_auto_verification(self, session_id: str):
        """자동 검증 중단"""
        if session_id in self._verify_tasks:
            self._verify_tasks[session_id].cancel()
            del self._verify_tasks[session_id]
            logger.info(f"자동 검증 중단됨: 세션 {session_id}")
            
    def cleanup(self):
        """시스템 정리"""
        # 모든 자동 검증 태스크 취소
        for session_id, task in self._verify_tasks.items():
            task.cancel()
        self._verify_tasks.clear()
        
        # 오래된 문맥 정리
        count = self.context_storage.cleanup_old_contexts()
        logger.info(f"시스템 정리 완료: {count}개의 오래된 문맥 삭제됨")
        
    async def simulate_fraud_scenario(self, scenario_type: str = "price_change") -> Dict[str, Any]:
        """사기 시나리오 시뮬레이션"""
        session_id = f"sim_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 시나리오별로 다른 상품 ID 사용하여 수집 모듈에서 구분 가능하게 함
        if scenario_type == "price_change":
            product_id = "PROD_PRICE_CHANGE"
            # 가격 변경 시나리오
            original_product = {
                "id": product_id,
                "price": 100000,
                "description": "고급 스마트폰 - 정품 1년 보증",
                "brand": "브랜드X",
                "category": "전자제품"
            }
        elif scenario_type == "description_change":
            product_id = "PROD_DESC_CHANGE"
            # 설명 변경 시나리오
            original_product = {
                "id": product_id,
                "price": 100000,
                "description": "고급 스마트폰 - 정품 1년 보증 포함, 무상 수리 서비스",
                "brand": "브랜드X",
                "category": "전자제품"
            }
        elif scenario_type == "wording_variation":
            product_id = "PROD_WORDING_VAR"
            # 표현 변형 시나리오 - 문구 순서나 단어 선택의 차이
            original_product = {
                "id": product_id,
                "price": 100000,
                "description": "고급 스마트폰 - 정품 1년 보증 포함, A/S 지원",
                "brand": "브랜드X",
                "category": "전자제품"
            }
            
            # 데이터 수집기 확장 - 다양한 마케팅 표현 테스트용
            class WordingVariationCollector(DataCollector):
                async def collect_via_web(self, product_id, url_template=None):
                    # 원래 메서드 호출
                    product_info = await super().collect_via_web(product_id, url_template)
                    
                    # 판매자가 마케팅 문구를 약간 변경한 케이스 시뮬레이션
                    if product_info and product_id == "PROD_WORDING_VAR":
                        product_info.description = "고급 스마트폰 - 1년 정품 보증 포함, 기술지원 서비스"
                    
                    return product_info
            
            # 확장된 데이터 수집기 사용
            self.data_collector = WordingVariationCollector()
        else:
            product_id = "PROD_NORMAL"
            # 정상 시나리오
            original_product = {
                "id": product_id,
                "price": 100000,
                "description": "고급 스마트폰 - 정품 1년 보증",
                "brand": "브랜드X",
                "category": "전자제품"
            }
            
        # 2. 상품 조회 시뮬레이션
        logger.info(f"시뮬레이션 시작: {scenario_type}")
        await self.on_product_view(session_id, product_id, original_product)
        
        # 3. 일정 시간 대기 (실제 상황에서는 사용자가 상품을 검토하는 시간)
        await asyncio.sleep(1)
        
        # 4. 장바구니 추가 시뮬레이션
        detection_result = await self.on_add_to_cart(session_id, product_id)
        
        # 5. 결과 정리
        simulation_result = {
            "scenario": scenario_type,
            "session_id": session_id,
            "product_id": product_id,
            "original_info": original_product,
            "detection_result": detection_result.dict() if detection_result else None,
            "is_fraud_detected": detection_result.is_fraud_detected if detection_result else False
        }
        
        logger.info(f"시뮬레이션 완료: {scenario_type}")
        return simulation_result 