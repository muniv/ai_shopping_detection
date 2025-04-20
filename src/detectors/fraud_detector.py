from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger
from src.models.data_models import ProductInfo, DetectionResult, ContextRecord, NotificationMessage
from src.storage.context_storage import ContextStorage
from src.detectors.data_collector import DataCollector
from src.detectors.comparator import ProductComparator

class FraudDetector:
    """
    이상 탐지 엔진
    비교 결과 비정상적인 변화가 감지되면 이를 속임수로 판단
    """
    
    def __init__(self, 
                 context_storage: ContextStorage,
                 data_collector: Optional[DataCollector] = None,
                 product_comparator: Optional[ProductComparator] = None,
                 price_threshold: float = 0.05,
                 description_threshold: float = 0.8,
                 use_llm_for_description: bool = True,
                 deception_threshold: float = 5.0):
        
        self.context_storage = context_storage
        self.data_collector = data_collector or DataCollector()
        self.product_comparator = product_comparator or ProductComparator(
            price_threshold=price_threshold,
            description_similarity_threshold=description_threshold,
            use_llm_for_description=use_llm_for_description,
            deception_threshold=deception_threshold
        )
        self.detection_history: Dict[str, List[DetectionResult]] = {}  # {session_id: [results]}
        self.use_llm_for_description = use_llm_for_description
        logger.info("이상 탐지 엔진 초기화 완료")
        if self.use_llm_for_description:
            logger.info("AI 기반 설명 속임수 탐지 활성화됨")
        
    async def verify_product(self, session_id: str, product_id: str) -> Optional[DetectionResult]:
        """상품 정보 검증"""
        try:
            # 1. 원본 문맥 불러오기
            context_record = self.context_storage.get_context(session_id, product_id)
            if not context_record:
                logger.warning(f"문맥 정보를 찾을 수 없음: 세션 {session_id}, 상품 {product_id}")
                return None
                
            original_info = context_record.product_info
            logger.info(f"원본 문맥 불러오기 완료: 세션 {session_id}, 상품 {product_id}")
            
            # 2. 최신 데이터 수집
            collected_data = await self.data_collector.collect_product_data(product_id)
            if not collected_data or not any(collected_data.values()):
                logger.warning(f"최신 데이터를 수집할 수 없음: 상품 {product_id}")
                return None
                
            # Web 데이터가 있으면 우선 사용, 없으면 MCP 데이터 사용
            current_info = collected_data.get("web") or collected_data.get("mcp")
            if not current_info:
                logger.warning(f"유효한 최신 데이터를 찾을 수 없음: 상품 {product_id}")
                return None
                
            logger.info(f"최신 데이터 수집 완료: 상품 {product_id}")
            
            # 3. 비교 수행
            detection_result = self.product_comparator.compare_product_info(original_info, current_info)
            detection_result.session_id = session_id  # 세션 ID 설정
            
            # 4. 결과 저장
            if session_id not in self.detection_history:
                self.detection_history[session_id] = []
            self.detection_history[session_id].append(detection_result)
            
            if detection_result.is_fraud_detected:
                logger.warning(f"이상 탐지: 세션 {session_id}, 상품 {product_id}, "
                             f"변경 항목: {', '.join(detection_result.changes.keys())}")
                
                # LLM 분석 결과가 있으면 로그에 추가 정보 출력
                if self.use_llm_for_description and "description" in detection_result.changes:
                    desc_change = detection_result.changes["description"]
                    if "change_description" in desc_change:
                        logger.warning(f"AI 분석 결과: {desc_change['change_description']}")
                    if "deception_score" in desc_change:
                        logger.warning(f"기만성 점수: {desc_change['deception_score']:.1f}/10")
            else:
                logger.info(f"이상 없음: 세션 {session_id}, 상품 {product_id}")
                
            return detection_result
        except Exception as e:
            logger.error(f"상품 검증 중 오류 발생: {e}")
            return None
            
    def get_detection_history(self, session_id: str) -> List[DetectionResult]:
        """세션에 대한 탐지 기록 조회"""
        return self.detection_history.get(session_id, [])
    
    def create_notification(self, detection_result: DetectionResult) -> Optional[NotificationMessage]:
        """탐지 결과로부터 알림 메시지 생성"""
        try:
            if not detection_result or not detection_result.is_fraud_detected:
                return None
                
            severity = "warning"
            action_required = True
            
            # 기본 메시지 생성
            message = f"상품 {detection_result.product_id}에 대한 중요 정보가 변경되었습니다: "
            
            # LLM 분석 결과가 있으면 더 상세한 메시지 생성
            if self.use_llm_for_description and "description" in detection_result.changes:
                desc_change = detection_result.changes["description"]
                if "change_description" in desc_change:
                    # LLM 분석 결과 활용
                    message += desc_change["change_description"]
                    
                    # 혜택 변경 정보가 있으면 추가
                    if "benefits_changes" in desc_change:
                        benefits = desc_change["benefits_changes"]
                        if benefits["removed"]:
                            message += f" 제거된 혜택: {', '.join(benefits['removed'])}."
                        if benefits["added"]:
                            message += f" 추가된 혜택: {', '.join(benefits['added'])}."
                    
                    # 기만성 점수가 높으면 심각도를 error로 높임
                    if "deception_score" in desc_change and desc_change["deception_score"] > 7:
                        severity = "error"
                else:
                    # 기본 변경 요약 사용
                    message += detection_result.get_change_summary()
            else:
                # 기본 변경 요약 사용
                message += detection_result.get_change_summary()
            
            return NotificationMessage(
                session_id=detection_result.session_id,
                product_id=detection_result.product_id,
                message=message,
                severity=severity,
                action_required=action_required,
                details=detection_result
            )
        except Exception as e:
            logger.error(f"알림 메시지 생성 중 오류 발생: {e}")
            return None 