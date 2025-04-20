from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime


class ProductInfo(BaseModel):
    """상품 정보를 나타내는 모델"""
    product_id: str
    price: float
    description: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def get_key_features(self) -> Dict[str, Any]:
        """가격과 같은 핵심 특성 반환"""
        return {
            "price": self.price,
            "description": self.description
        }


class ContextRecord(BaseModel):
    """문맥 저장소에 저장될 레코드 모델"""
    session_id: str
    product_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    product_info: ProductInfo
    source_url: Optional[str] = None
    agent_id: Optional[str] = None


class DetectionResult(BaseModel):
    """이상 탐지 결과 모델"""
    session_id: str
    product_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    is_fraud_detected: bool = False
    changes: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    confidence_score: float = 1.0
    details: Optional[str] = None
    
    def has_price_change(self) -> bool:
        """가격 변화 여부 확인"""
        return "price" in self.changes
    
    def has_description_change(self) -> bool:
        """설명 변화 여부 확인"""
        return "description" in self.changes
    
    def get_change_summary(self) -> str:
        """변경 사항 요약"""
        if not self.is_fraud_detected:
            return "이상 없음"
            
        summaries = []
        for field, change in self.changes.items():
            if field == "price":
                pct_change = ((change["current"] - change["original"]) / change["original"]) * 100
                summaries.append(f"가격: {change['original']}원 → {change['current']}원 ({pct_change:.1f}% {'상승' if pct_change > 0 else '하락'})")
            elif field == "description":
                summaries.append(f"설명 변경: '{change['original']}' → '{change['current']}'")
        
        return ", ".join(summaries)


class NotificationMessage(BaseModel):
    """알림 메시지 모델"""
    session_id: str
    product_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    message: str
    severity: str = "warning"  # info, warning, error
    action_required: bool = False
    details: Optional[DetectionResult] = None 