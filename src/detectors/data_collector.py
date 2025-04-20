from typing import Dict, Any, Optional, List
import requests
import json
from loguru import logger
from src.models.data_models import ProductInfo
from src.interfaces.mcp_interface import MCPInterface
import asyncio
import random

class DataCollector:
    """
    데이터 재수집 모듈
    거래 완료 전에 동일 상품의 최신 정보를 다시 불러오는 역할
    """
    
    def __init__(self, mcp_interface: Optional[MCPInterface] = None):
        self.mcp_interface = mcp_interface or MCPInterface()
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        logger.info("데이터 재수집 모듈 초기화 완료")
        
    async def collect_via_mcp(self, product_id: str, endpoint: str = "get_product", 
                          request_params: Dict[str, Any] = None) -> Optional[ProductInfo]:
        """MCP를 통한 상품 정보 재수집"""
        try:
            # 기본 요청 파라미터 설정
            request_params = request_params or {}
            request_params["product_id"] = product_id
            
            # 여기서는 실제 요청을 보내지 않고 시뮬레이션
            # 실제 구현에서는 MCP 서버에 HTTP 요청을 보내야 함
            logger.info(f"MCP를 통한 상품 정보 재수집: {product_id}")
            
            # 임시 응답 데이터 (실제로는 서버 응답)
            response_data = {
                "id": product_id,
                "price": 100000,  # 임시 가격
                "description": "상품 설명",
                "brand": "브랜드명",
                "category": "카테고리"
            }
            
            # MCP 인터페이스를 통해 응답 데이터 처리
            product_info = self.mcp_interface.extract_product_info(response_data)
            if not product_info:
                logger.warning(f"상품 정보를 추출할 수 없음: {product_id}")
                return None
                
            logger.info(f"MCP 상품 정보 재수집 완료: {product_id}")
            return product_info
        except Exception as e:
            logger.error(f"MCP 상품 정보 재수집 중 오류 발생: {e}")
            return None
            
    async def collect_via_web(self, product_id: str, 
                          url_template: str = "https://example.com/products/{product_id}") -> Optional[ProductInfo]:
        """웹 스크래핑을 통한 상품 정보 재수집"""
        try:
            # URL 생성
            url = url_template.format(product_id=product_id)
            
            # 웹 통신 지연 시뮬레이션 (0.1초~0.4초 사이 랜덤 지연)
            await asyncio.sleep(random.uniform(0.1, 0.4))
            
            # 여기서는 실제 요청을 보내지 않고 시뮬레이션
            # 실제 구현에서는 HTTP 요청 및 웹 스크래핑을 수행해야 함
            logger.info(f"웹 스크래핑을 통한 상품 정보 재수집: {url}")
            
            # 상품 ID에 따라 다른 시뮬레이션 데이터 반환
            if product_id == "PROD_PRICE_CHANGE":
                # 가격 변경 시나리오
                scraped_data = {
                    "id": product_id,
                    "price": 120000,  # 20% 가격 인상
                    "description": "고급 스마트폰 - 정품 1년 보증",  # 설명 동일
                    "brand": "브랜드X",
                    "category": "전자제품"
                }
            elif product_id == "PROD_DESC_CHANGE":
                # 설명 변경 시나리오
                scraped_data = {
                    "id": product_id,
                    "price": 100000,  # 가격 동일
                    "description": "고급 스마트폰 (보증 없음)",  # 설명 변경
                    "brand": "브랜드X",
                    "category": "전자제품"
                }
            else:
                # 정상 시나리오 또는 기본 케이스
                scraped_data = {
                    "id": product_id,
                    "price": 100000,  # 가격 동일
                    "description": "고급 스마트폰 - 정품 1년 보증",  # 설명 동일
                    "brand": "브랜드X",
                    "category": "전자제품"
                }
            
            # 스크래핑 데이터에서 상품 정보 추출
            product_info = ProductInfo(
                product_id=product_id,
                price=float(scraped_data.get("price", 0)),
                description=scraped_data.get("description", ""),
                attributes={k: v for k, v in scraped_data.items() 
                           if k not in ["id", "product_id", "price", "description"]}
            )
            
            logger.info(f"웹 상품 정보 재수집 완료: {product_id}")
            return product_info
        except Exception as e:
            logger.error(f"웹 상품 정보 재수집 중 오류 발생: {e}")
            return None
    
    async def collect_product_data(self, product_id: str, 
                                collect_methods: List[str] = ["mcp", "web"]) -> Dict[str, Optional[ProductInfo]]:
        """다양한 방식으로 상품 정보 수집"""
        results = {}
        
        if "mcp" in collect_methods:
            results["mcp"] = await self.collect_via_mcp(product_id)
            
        if "web" in collect_methods:
            results["web"] = await self.collect_via_web(product_id)
            
        if not any(results.values()):
            logger.warning(f"어떤 방식으로도 상품 정보를 수집할 수 없음: {product_id}")
            
        return results 