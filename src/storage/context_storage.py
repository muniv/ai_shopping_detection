from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
from loguru import logger
from src.models.data_models import ProductInfo, ContextRecord

class ContextStorage:
    """
    문맥 저장소
    에이전트가 처음 획득한 상품 정보의 스냅샷을 저장
    """
    
    def __init__(self, storage_type: str = "memory"):
        """
        Args:
            storage_type: 저장소 타입 (memory, mongodb 등)
        """
        self.storage_type = storage_type
        self.memory_storage: Dict[str, Dict[str, ContextRecord]] = {}  # {session_id: {product_id: record}}
        logger.info(f"문맥 저장소 초기화 완료 (타입: {storage_type})")
        
    def store_context(self, session_id: str, product_id: str, product_info: ProductInfo, 
                     source_url: Optional[str] = None, agent_id: Optional[str] = None) -> bool:
        """상품 정보 문맥 저장"""
        try:
            if self.storage_type == "memory":
                if session_id not in self.memory_storage:
                    self.memory_storage[session_id] = {}
                
                context_record = ContextRecord(
                    session_id=session_id,
                    product_id=product_id,
                    timestamp=datetime.now(),
                    product_info=product_info,
                    source_url=source_url,
                    agent_id=agent_id
                )
                
                self.memory_storage[session_id][product_id] = context_record
                logger.info(f"문맥 저장 완료: 세션 {session_id}, 상품 {product_id}")
                return True
            else:
                logger.error(f"지원하지 않는 저장소 타입: {self.storage_type}")
                return False
        except Exception as e:
            logger.error(f"문맥 저장 중 오류 발생: {e}")
            return False
            
    def get_context(self, session_id: str, product_id: str) -> Optional[ContextRecord]:
        """저장된 상품 정보 문맥 조회"""
        try:
            if self.storage_type == "memory":
                if session_id not in self.memory_storage:
                    logger.warning(f"세션 ID를 찾을 수 없음: {session_id}")
                    return None
                    
                if product_id not in self.memory_storage[session_id]:
                    logger.warning(f"상품 ID를 찾을 수 없음: {product_id}")
                    return None
                    
                return self.memory_storage[session_id][product_id]
            else:
                logger.error(f"지원하지 않는 저장소 타입: {self.storage_type}")
                return None
        except Exception as e:
            logger.error(f"문맥 조회 중 오류 발생: {e}")
            return None
            
    def get_all_contexts_for_session(self, session_id: str) -> List[ContextRecord]:
        """세션의 모든 상품 정보 문맥 조회"""
        try:
            if self.storage_type == "memory":
                if session_id not in self.memory_storage:
                    logger.warning(f"세션 ID를 찾을 수 없음: {session_id}")
                    return []
                    
                return list(self.memory_storage[session_id].values())
            else:
                logger.error(f"지원하지 않는 저장소 타입: {self.storage_type}")
                return []
        except Exception as e:
            logger.error(f"세션 문맥 조회 중 오류 발생: {e}")
            return []
            
    def delete_context(self, session_id: str, product_id: str) -> bool:
        """상품 정보 문맥 삭제"""
        try:
            if self.storage_type == "memory":
                if session_id not in self.memory_storage:
                    logger.warning(f"세션 ID를 찾을 수 없음: {session_id}")
                    return False
                    
                if product_id not in self.memory_storage[session_id]:
                    logger.warning(f"상품 ID를 찾을 수 없음: {product_id}")
                    return False
                    
                del self.memory_storage[session_id][product_id]
                logger.info(f"문맥 삭제 완료: 세션 {session_id}, 상품 {product_id}")
                return True
            else:
                logger.error(f"지원하지 않는 저장소 타입: {self.storage_type}")
                return False
        except Exception as e:
            logger.error(f"문맥 삭제 중 오류 발생: {e}")
            return False
            
    def cleanup_old_contexts(self, max_age_hours: int = 24) -> int:
        """오래된 문맥 정보 정리"""
        try:
            if self.storage_type == "memory":
                count = 0
                cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
                
                for session_id in list(self.memory_storage.keys()):
                    for product_id in list(self.memory_storage[session_id].keys()):
                        record = self.memory_storage[session_id][product_id]
                        if record.timestamp < cutoff_time:
                            del self.memory_storage[session_id][product_id]
                            count += 1
                    
                    # 세션이 비어있으면 세션도 삭제
                    if not self.memory_storage[session_id]:
                        del self.memory_storage[session_id]
                
                logger.info(f"오래된 문맥 {count}개 정리 완료")
                return count
            else:
                logger.error(f"지원하지 않는 저장소 타입: {self.storage_type}")
                return 0
        except Exception as e:
            logger.error(f"문맥 정리 중 오류 발생: {e}")
            return 0 