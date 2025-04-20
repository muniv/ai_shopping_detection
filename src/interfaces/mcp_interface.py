from typing import Dict, Any, Optional, Callable
import json
from loguru import logger
from src.models.data_models import ProductInfo

class MCPInterface:
    """
    MCP(Merchant-Consumer Protocol) 인터페이스
    에이전트와 전자상거래 사이트 간의 통신을 모니터링
    """
    
    def __init__(self):
        self.request_interceptors: Dict[str, Callable] = {}
        self.response_interceptors: Dict[str, Callable] = {}
        logger.info("MCP 인터페이스 초기화 완료")
        
    def register_request_interceptor(self, endpoint: str, interceptor: Callable):
        """특정 엔드포인트에 대한 요청 인터셉터 등록"""
        self.request_interceptors[endpoint] = interceptor
        logger.debug(f"요청 인터셉터 등록: {endpoint}")
        
    def register_response_interceptor(self, endpoint: str, interceptor: Callable):
        """특정 엔드포인트에 대한 응답 인터셉터 등록"""
        self.response_interceptors[endpoint] = interceptor
        logger.debug(f"응답 인터셉터 등록: {endpoint}")
        
    def intercept_request(self, endpoint: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """요청 데이터 인터셉트"""
        if endpoint in self.request_interceptors:
            logger.debug(f"요청 인터셉트: {endpoint}")
            modified_request = self.request_interceptors[endpoint](request_data)
            return modified_request
        return request_data
        
    def intercept_response(self, endpoint: str, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """응답 데이터 인터셉트"""
        if endpoint in self.response_interceptors:
            logger.debug(f"응답 인터셉트: {endpoint}")
            modified_response = self.response_interceptors[endpoint](response_data)
            return modified_response
        return response_data
    
    def extract_product_info(self, product_data: Dict[str, Any]) -> Optional[ProductInfo]:
        """MCP 응답에서 상품 정보 추출"""
        try:
            # MCP 응답 형식에 맞게 제품 정보 파싱
            product_id = product_data.get("id") or product_data.get("product_id")
            if not product_id:
                logger.warning("제품 ID를 찾을 수 없음")
                return None
                
            price = float(product_data.get("price", 0))
            description = product_data.get("description", "")
            
            # 추가 속성 및 메타데이터 추출
            attributes = {}
            for key, value in product_data.items():
                if key not in ["id", "product_id", "price", "description"]:
                    attributes[key] = value
            
            return ProductInfo(
                product_id=product_id,
                price=price,
                description=description,
                attributes=attributes
            )
        except Exception as e:
            logger.error(f"제품 정보 추출 중 오류 발생: {e}")
            return None

class MCPProxy:
    """
    MCP 프록시
    에이전트와 서버 사이에서 통신을 중개하는 역할
    """
    
    def __init__(self, mcp_interface: MCPInterface):
        self.mcp_interface = mcp_interface
        logger.info("MCP 프록시 초기화 완료")
        
    async def forward_request(self, endpoint: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """에이전트의 요청을 서버로 전달"""
        # 요청 인터셉트
        modified_request = self.mcp_interface.intercept_request(endpoint, request_data)
        
        # 실제 API 호출은 구현하지 않음 (실제로는 여기서 HTTP 요청 수행)
        # 여기서는 시뮬레이션을 위해 요청을 그대로 응답으로 반환
        logger.info(f"요청 전달: {endpoint}")
        return modified_request
        
    async def forward_response(self, endpoint: str, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """서버의 응답을 에이전트로 전달"""
        # 응답 인터셉트
        modified_response = self.mcp_interface.intercept_response(endpoint, response_data)
        
        logger.info(f"응답 전달: {endpoint}")
        return modified_response 