from typing import Dict, Any, Optional, List, Callable
import json
from datetime import datetime
from loguru import logger
from src.models.data_models import NotificationMessage, DetectionResult

class Notifier:
    """
    알림 및 대응 컴포넌트
    이상 탐지 엔진이 속임수를 확인하면 즉시 대응 조치 수행
    """
    
    def __init__(self):
        self.notification_handlers: Dict[str, List[Callable]] = {
            "info": [],
            "warning": [],
            "error": []
        }
        self.notification_history: Dict[str, List[NotificationMessage]] = {}  # {session_id: [notifications]}
        logger.info("알림 모듈 초기화 완료")
        
    def register_handler(self, severity: str, handler: Callable):
        """알림 핸들러 등록"""
        if severity not in self.notification_handlers:
            self.notification_handlers[severity] = []
        self.notification_handlers[severity].append(handler)
        logger.debug(f"{severity} 알림 핸들러 등록됨")
        
    def notify(self, notification: NotificationMessage) -> bool:
        """알림 발송"""
        try:
            session_id = notification.session_id
            
            # 알림 기록
            if session_id not in self.notification_history:
                self.notification_history[session_id] = []
            self.notification_history[session_id].append(notification)
            
            # 핸들러 호출
            handlers = self.notification_handlers.get(notification.severity, [])
            if not handlers:
                logger.warning(f"등록된 {notification.severity} 핸들러가 없음")
            
            for handler in handlers:
                try:
                    handler(notification)
                except Exception as e:
                    logger.error(f"알림 핸들러 실행 중 오류 발생: {e}")
            
            logger.info(f"알림 발송: {notification.severity} - {notification.message}")
            return True
        except Exception as e:
            logger.error(f"알림 발송 중 오류 발생: {e}")
            return False
            
    def get_notification_history(self, session_id: str) -> List[NotificationMessage]:
        """세션에 대한 알림 기록 조회"""
        return self.notification_history.get(session_id, [])


class DefaultNotificationHandlers:
    """기본 알림 핸들러 모음"""
    
    @staticmethod
    def console_handler(notification: NotificationMessage):
        """콘솔 출력 핸들러"""
        severity_marks = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "🛑"
        }
        mark = severity_marks.get(notification.severity, "")
        print(f"{mark} [{notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {notification.message}")
        
    @staticmethod
    def log_handler(notification: NotificationMessage):
        """로그 기록 핸들러"""
        if notification.severity == "info":
            logger.info(notification.message)
        elif notification.severity == "warning":
            logger.warning(notification.message)
        elif notification.severity == "error":
            logger.error(notification.message)
        else:
            logger.debug(notification.message)
            
    @staticmethod
    def agent_response_handler(notification: NotificationMessage):
        """에이전트 응답 핸들러 (실제로는 에이전트 API 호출 필요)"""
        logger.info(f"[에이전트 알림] {notification.message}")
        
        # 실제 구현에서는 에이전트 API를 호출하여 정보 전달
        # 예: agent_api.send_alert(notification.product_id, notification.message)
        
        if notification.action_required:
            logger.warning(f"[에이전트 조치] 상품 {notification.product_id}에 대한 조치 필요")
            # 예: agent_api.remove_from_cart(notification.product_id)
            
    @staticmethod
    def database_handler(notification: NotificationMessage):
        """데이터베이스 기록 핸들러 (실제로는 DB API 호출 필요)"""
        logger.info(f"[DB 로깅] {notification.severity}: {notification.message}")
        
        # 실제 구현에서는 데이터베이스에 기록
        # 예: db_api.insert_notification(notification.dict()) 