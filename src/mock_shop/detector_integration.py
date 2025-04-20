import sys
import os
import asyncio
import json
from datetime import datetime
import requests
from loguru import logger

# 프로젝트 루트 경로를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.system import FraudDetectionSystem
from src.models.data_models import ProductInfo, ContextRecord

class MCPMonitor:
    """
    MCP 모니터링 클래스
    가상 쇼핑몰의 MCP API 통신을 모니터링하고 속임수 탐지 시스템과 연동
    """
    
    def __init__(self, shop_url="http://localhost:5000"):
        """
        Args:
            shop_url: 가상 쇼핑몰 URL
        """
        self.shop_url = shop_url
        self.fraud_system = FraudDetectionSystem()
        self.session_contexts = {}  # {session_id: {product_id: original_context}}
        logger.info(f"MCP 모니터 초기화 완료 (쇼핑몰 URL: {shop_url})")
        
    async def monitor_product_view(self, session_id, product_id):
        """상품 조회 모니터링"""
        try:
            # MCP API를 통해 상품 정보 가져오기
            response = requests.get(
                f"{self.shop_url}/api/mcp/product/{product_id}",
                headers={"X-Session-ID": session_id}
            )
            
            if response.status_code != 200:
                logger.warning(f"상품 정보 조회 실패: {product_id}")
                return None
                
            product_data = response.json()
            
            # 상품 정보를 ProductInfo 객체로 변환
            product_info = ProductInfo(
                product_id=product_data.get("id"),
                price=float(product_data.get("price", 0)),
                description=product_data.get("description", ""),
                attributes={
                    "name": product_data.get("name", ""),
                    "brand": product_data.get("brand", ""),
                    "category": product_data.get("category", "")
                }
            )
            
            # 속임수 탐지 시스템에 상품 조회 이벤트 전달
            await self.fraud_system.on_product_view(session_id, product_id, product_data)
            
            # 세션별 상품 문맥 저장
            if session_id not in self.session_contexts:
                self.session_contexts[session_id] = {}
                
            self.session_contexts[session_id][product_id] = product_info
            
            return product_info
        except Exception as e:
            logger.error(f"상품 조회 모니터링 중 오류 발생: {e}")
            return None
            
    async def monitor_add_to_cart(self, session_id, product_id):
        """장바구니 추가 모니터링"""
        try:
            # 이전에 본 상품 정보가 있는지 확인
            if session_id in self.session_contexts and product_id in self.session_contexts[session_id]:
                # 속임수 탐지 수행
                detection_result = await self.fraud_system.on_add_to_cart(session_id, product_id)
                
                # 결과 처리
                if detection_result and detection_result.is_fraud_detected:
                    logger.warning(f"속임수 탐지: 세션 {session_id}, 상품 {product_id}")
                    
                    # 변경 사항 로깅
                    changes = []
                    if "price" in detection_result.changes:
                        price_change = detection_result.changes["price"]
                        changes.append(f"가격 변경: {price_change['original']} -> {price_change['current']}")
                        
                    if "description" in detection_result.changes:
                        desc_change = detection_result.changes["description"]
                        changes.append(f"설명 변경: 유사도 {desc_change.get('similarity', 0):.1%}")
                        
                    logger.info(f"변경 사항: {', '.join(changes)}")
                    
                    return detection_result
                else:
                    logger.info(f"속임수 없음: 세션 {session_id}, 상품 {product_id}")
                    return None
            else:
                logger.warning(f"이전 상품 조회 내역 없음: 세션 {session_id}, 상품 {product_id}")
                return None
        except Exception as e:
            logger.error(f"장바구니 추가 모니터링 중 오류 발생: {e}")
            return None
            
    async def monitor_checkout(self, session_id, product_ids):
        """결제 진행 모니터링"""
        try:
            # 모든 상품에 대해 속임수 탐지 수행
            results = await self.fraud_system.on_checkout(session_id, product_ids)
            
            # 결과 처리
            if results:
                fraud_detected = False
                fraud_products = []
                
                for product_id, result in results.items():
                    if result and result.is_fraud_detected:
                        fraud_detected = True
                        fraud_products.append(product_id)
                        
                if fraud_detected:
                    logger.warning(f"결제 과정에서 속임수 탐지: 세션 {session_id}, 상품 {', '.join(fraud_products)}")
                else:
                    logger.info(f"결제 과정에서 속임수 없음: 세션 {session_id}")
                    
                return results
            else:
                logger.warning(f"결제 시 속임수 탐지 실패: 세션 {session_id}")
                return None
        except Exception as e:
            logger.error(f"결제 모니터링 중 오류 발생: {e}")
            return None
            
    def start_auto_verification(self, session_id, product_ids):
        """자동 검증 시작"""
        asyncio.create_task(self.fraud_system.start_auto_verification(session_id, product_ids))
        logger.info(f"자동 검증 시작: 세션 {session_id}, 상품 {len(product_ids)}개")
        
    def stop_auto_verification(self, session_id):
        """자동 검증 중단"""
        self.fraud_system.stop_auto_verification(session_id)
        logger.info(f"자동 검증 중단: 세션 {session_id}")
        
    def cleanup(self):
        """리소스 정리"""
        self.fraud_system.cleanup()
        logger.info("MCP 모니터 정리 완료")


class BrowserMonitor:
    """
    브라우저 모니터링 클래스
    가상 쇼핑몰 웹 인터페이스를 모니터링하고 속임수 탐지 시스템과 연동
    """
    
    def __init__(self, shop_url="http://localhost:5000"):
        """
        Args:
            shop_url: 가상 쇼핑몰 URL
        """
        self.shop_url = shop_url
        self.fraud_system = FraudDetectionSystem()
        self.session_contexts = {}  # {session_id: {product_id: original_html}}
        logger.info(f"브라우저 모니터 초기화 완료 (쇼핑몰 URL: {shop_url})")
        
    def monitor_page_visit(self, session_id, url, html_content):
        """페이지 방문 모니터링"""
        try:
            # 상품 상세 페이지인지 확인
            if "/product/" in url:
                product_id = url.split("/product/")[1].split("/")[0]
                
                # HTML에서 상품 정보 추출 (실제로는 DOM 파싱 필요)
                # 여기서는 간단한 예시로 표현
                logger.info(f"상품 페이지 방문 감지: {product_id}")
                
                # 세션별 상품 HTML 저장
                if session_id not in self.session_contexts:
                    self.session_contexts[session_id] = {}
                    
                self.session_contexts[session_id][product_id] = {
                    "url": url,
                    "html": html_content,
                    "timestamp": datetime.now()
                }
                
                return True
            return False
        except Exception as e:
            logger.error(f"페이지 방문 모니터링 중 오류 발생: {e}")
            return False
            
    def compare_product_page(self, session_id, product_id, current_html):
        """상품 페이지 비교"""
        try:
            if session_id in self.session_contexts and product_id in self.session_contexts[session_id]:
                original_html = self.session_contexts[session_id][product_id]["html"]
                
                # HTML 비교 (실제로는 DOM 파싱 후 구조화된 비교 필요)
                # 여기서는 간단한 예시로 표현
                logger.info(f"상품 페이지 비교: {product_id}")
                
                # 가격 변경 확인 예시
                original_price_match = "₩1,000,000"  # 실제로는 정규식 등으로 추출
                current_price_match = "₩800,000"  # 실제로는 정규식 등으로 추출
                
                if original_price_match != current_price_match:
                    logger.warning(f"가격 변경 감지: {original_price_match} -> {current_price_match}")
                    return {"price_changed": True, "original": original_price_match, "current": current_price_match}
                    
                return {"price_changed": False}
            else:
                logger.warning(f"이전 상품 페이지 내역 없음: 세션 {session_id}, 상품 {product_id}")
                return None
        except Exception as e:
            logger.error(f"상품 페이지 비교 중 오류 발생: {e}")
            return None
    
    def cleanup(self):
        """리소스 정리"""
        # 오래된 컨텍스트 삭제 등
        for session_id in list(self.session_contexts.keys()):
            del self.session_contexts[session_id]
        logger.info("브라우저 모니터 정리 완료")


# 테스트용 메인 함수
async def test_mcp_monitor():
    """MCP 모니터 테스트"""
    logger.info("MCP 모니터 테스트 시작")
    
    monitor = MCPMonitor()
    session_id = "test_session_12345"
    
    # 1. 상품 조회 테스트
    product_id = "PROD001"
    product_info = await monitor.monitor_product_view(session_id, product_id)
    
    if product_info:
        logger.info(f"상품 정보: {product_info.dict()}")
        
        # 2. 장바구니 추가 테스트
        detection_result = await monitor.monitor_add_to_cart(session_id, product_id)
        
        if detection_result:
            logger.info(f"속임수 탐지 결과: {detection_result.dict()}")
        else:
            logger.info("속임수가 감지되지 않았습니다.")
    
    # 정리
    monitor.cleanup()
    logger.info("MCP 모니터 테스트 완료")


if __name__ == "__main__":
    # 로그 설정
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # 테스트 실행
        asyncio.run(test_mcp_monitor())
    else:
        logger.info("detector_integration.py를 직접 실행하려면 'test' 인자를 추가하세요.")
        logger.info("예: python detector_integration.py test") 