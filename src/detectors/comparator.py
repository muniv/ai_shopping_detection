from typing import Dict, Any, Optional, List, Tuple
import difflib
import re
import os
import json
from loguru import logger
from src.models.data_models import ProductInfo, DetectionResult
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import openai
from dotenv import load_dotenv
import statistics

# .env 파일 로드
load_dotenv()

# OpenAI API 키 설정
openai.api_key = os.getenv("OPENAI_API_KEY")

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
    
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')


class ProductComparator:
    """
    상품 정보 비교 모듈
    저장된 원본 문맥과 재수집된 최신 정보를 비교하여 불일치 탐지
    """
    
    def __init__(self, price_threshold: float = 0.05, 
                description_similarity_threshold: float = 0.8,
                use_llm_for_description: bool = True,
                deception_threshold: float = 5.0):
        """
        Args:
            price_threshold: 가격 변화 임계값 (예: 0.05는 5% 변화)
            description_similarity_threshold: 설명 유사도 임계값 (0~1 사이)
            use_llm_for_description: LLM을 사용한 설명 비교 활성화 여부
            deception_threshold: LLM 기반 속임수 탐지 시 기만성 점수 임계값 (0~10)
        """
        self.price_threshold = price_threshold
        self.description_similarity_threshold = description_similarity_threshold
        self.use_llm_for_description = use_llm_for_description
        self.deception_threshold = deception_threshold
        self.stop_words = set(stopwords.words('english'))
        logger.info("상품 정보 비교 모듈 초기화 완료")
        
    def compare_price(self, original_price: float, current_price: float) -> Tuple[bool, float]:
        """가격 비교"""
        if original_price <= 0:
            logger.warning(f"원본 가격이 유효하지 않음: {original_price}")
            return False, 0
            
        if current_price <= 0:
            logger.warning(f"현재 가격이 유효하지 않음: {current_price}")
            return False, 0
            
        price_change_ratio = abs(current_price - original_price) / original_price
        is_price_changed = price_change_ratio > self.price_threshold
        
        logger.debug(f"가격 비교: {original_price} -> {current_price} "
                   f"(변화율: {price_change_ratio:.2%}, 임계값: {self.price_threshold:.2%})")
                   
        return is_price_changed, price_change_ratio
        
    def compare_description(self, original_desc: str, current_desc: str) -> Tuple[bool, float]:
        """설명 비교"""
        if not original_desc or not current_desc:
            logger.warning("원본 또는 현재 설명이 비어있음")
            return False, 0
            
        # 텍스트 정규화
        original_desc = re.sub(r'\s+', ' ', original_desc.lower().strip())
        current_desc = re.sub(r'\s+', ' ', current_desc.lower().strip())
        
        # 간단한 유사도 계산 (더 복잡한 알고리즘으로 대체 가능)
        similarity = difflib.SequenceMatcher(None, original_desc, current_desc).ratio()
        is_description_changed = similarity < self.description_similarity_threshold
        
        logger.debug(f"설명 비교: 유사도: {similarity:.2%}, 임계값: {self.description_similarity_threshold:.2%}")
        
        return is_description_changed, similarity
        
    def compare_descriptions_semantic(self, original_desc: str, current_desc: str) -> Tuple[bool, float]:
        """의미적 설명 비교 (단어 집합 기반)"""
        if not original_desc or not current_desc:
            logger.warning("원본 또는 현재 설명이 비어있음")
            return False, 0
            
        # 텍스트 정규화 및 토큰화
        original_tokens = [w.lower() for w in word_tokenize(original_desc) 
                          if w.isalnum() and w.lower() not in self.stop_words]
        current_tokens = [w.lower() for w in word_tokenize(current_desc) 
                         if w.isalnum() and w.lower() not in self.stop_words]
        
        # 단어 집합 비교
        original_set = set(original_tokens)
        current_set = set(current_tokens)
        
        # 자카드 유사도 계산 (교집합 / 합집합)
        if not original_set or not current_set:
            return False, 0
            
        intersection = len(original_set.intersection(current_set))
        union = len(original_set.union(current_set))
        
        if union == 0:
            similarity = 0
        else:
            similarity = intersection / union
            
        is_description_changed = similarity < self.description_similarity_threshold
        
        return is_description_changed, similarity
        
    def compare_descriptions_llm(self, original_desc: str, current_desc: str) -> Tuple[bool, float, Dict[str, Any]]:
        """LLM을 사용한 의미적 설명 비교"""
        if not original_desc or not current_desc:
            logger.warning("원본 또는 현재 설명이 비어있음")
            return False, 0, {"error": "설명 부재"}
            
        try:
            # LLM에 전송할 프롬프트 구성
            prompt = f"""
다음은 제품 설명의 원본과 현재 버전입니다:

원본 설명: "{original_desc}"
현재 설명: "{current_desc}"

두 설명 사이에 소비자의 구매 결정에 영향을 줄 수 있는 중요한 의미 변화가 있는지 분석해주세요.
다음 항목에 JSON 형식으로 답해주세요:

1. 유사도 점수(0~1 사이, 1이 완전 동일): 
2. 중요한 의미 변화 여부(true/false): 
3. 변화 내용 설명(있다면): 
4. 소비자 기만성(0~10 사이, 10이 매우 심각): 
5. 제거된 혜택/기능(있다면 배열로): 
6. 추가된 혜택/기능(있다면 배열로): 
7. 변경된 혜택/기능(있다면 배열로): 

반드시 다음 JSON 형식으로 응답하세요:
{{"similarity_score": 0.8, "has_significant_change": true, "change_description": "설명", "deception_score": 7, "removed_benefits": ["혜택1", "혜택2"], "added_benefits": ["혜택3"], "changed_benefits": ["변경된 혜택 설명"]}}
"""
            
            # OpenAI API 호출 - AI 모델 사용
            response = openai.chat.completions.create(
                model="gpt-4o",  # AI 쇼핑 분석 모델 사용
                messages=[
                    {"role": "system", "content": "상품 설명 분석 전문가입니다. JSON 형식으로 응답합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1  # 일관된 결과를 위해 낮은 temperature 사용
            )
            
            # 응답 텍스트 추출
            response_text = response.choices[0].message.content
            
            # JSON 문자열 추출 (응답에 다른 텍스트가 있을 경우 대비)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                analysis = json.loads(json_str)
            else:
                # JSON이 명확하지 않은 경우 텍스트 전체를 파싱 시도
                analysis = json.loads(response_text)
                
            # 필요한 필드 확인 및 기본값 설정
            similarity_score = analysis.get("similarity_score", 0.5)
            has_significant_change = analysis.get("has_significant_change", False)
            deception_score = analysis.get("deception_score", 0.0)
            
            # 기만성 점수가 임계값을 넘으면 속임수로 판단
            is_fraud = deception_score > self.deception_threshold
            
            logger.info(f"AI 설명 비교 결과: 유사도={similarity_score:.2f}, 기만성={deception_score:.2f}, 속임수={is_fraud}")
            
            return is_fraud, similarity_score, analysis
            
        except Exception as e:
            logger.error(f"AI 설명 비교 중 오류 발생: {e}")
            # 오류 발생 시 기본 문자열 유사도 비교로 폴백
            is_desc_changed, similarity = self.compare_description(original_desc, current_desc)
            return is_desc_changed, similarity, {"error": str(e), "fallback": "기본 유사도 사용"}
    
    def _extract_benefits_from_llm_analysis(self, analysis: Dict[str, Any]) -> Dict[str, List[str]]:
        """LLM 분석 결과에서 혜택 정보 추출"""
        benefits_changes = {
            "removed": analysis.get("removed_benefits", []),
            "added": analysis.get("added_benefits", []),
            "changed": analysis.get("changed_benefits", [])
        }
        return benefits_changes
    
    def compare_product_info(self, original_info: ProductInfo, current_info: ProductInfo) -> DetectionResult:
        """상품 정보 전체 비교"""
        if original_info.product_id != current_info.product_id:
            logger.error(f"상품 ID가 일치하지 않음: {original_info.product_id} vs {current_info.product_id}")
            return DetectionResult(
                session_id="unknown",
                product_id=original_info.product_id,
                is_fraud_detected=False,
                details="상품 ID 불일치"
            )
            
        session_id = "unknown"  # 실제로는 호출 코드에서 세션 ID 전달해야 함
        product_id = original_info.product_id
        changes = {}
        
        # 가격 비교
        price_changed, price_change_ratio = self.compare_price(original_info.price, current_info.price)
        if price_changed:
            changes["price"] = {
                "original": original_info.price,
                "current": current_info.price,
                "change_ratio": price_change_ratio
            }
        
        # 설명 비교 - LLM 또는 기본 알고리즘 사용
        if self.use_llm_for_description and openai.api_key:
            # LLM 기반 설명 비교 사용
            desc_changed, desc_similarity, llm_analysis = self.compare_descriptions_llm(
                original_info.description, current_info.description)
                
            if desc_changed:
                # 혜택 변경 정보 추출
                benefits_changes = self._extract_benefits_from_llm_analysis(llm_analysis)
                
                changes["description"] = {
                    "original": original_info.description,
                    "current": current_info.description,
                    "similarity": desc_similarity,
                    "change_description": llm_analysis.get("change_description", ""),
                    "deception_score": llm_analysis.get("deception_score", 0),
                    "benefits_changes": benefits_changes
                }
        else:
            # 기본 설명 비교 사용
            desc_changed, desc_similarity = self.compare_description(
                original_info.description, current_info.description)
            if desc_changed:
                changes["description"] = {
                    "original": original_info.description,
                    "current": current_info.description,
                    "similarity": desc_similarity
                }
            
        # 속성 비교 (옵션)
        for key, original_value in original_info.attributes.items():
            if key in current_info.attributes:
                current_value = current_info.attributes[key]
                if original_value != current_value:
                    if "attributes" not in changes:
                        changes["attributes"] = {}
                    changes["attributes"][key] = {
                        "original": original_value,
                        "current": current_value
                    }
        
        # 사기 탐지 결과 생성
        is_fraud_detected = len(changes) > 0
        confidence_score = 1.0  # 실제로는 변화 정도에 따라 신뢰도 계산
        
        # 상세 정보 생성
        if is_fraud_detected:
            if "description" in changes and self.use_llm_for_description and "change_description" in changes["description"]:
                # LLM 분석이 있는 경우 더 상세한 정보 제공
                details = f"변경된 항목: {', '.join(changes.keys())}. "
                details += f"설명 변경: {changes['description']['change_description']}"
                
                # 혜택 변경 정보가 있으면 추가
                if "benefits_changes" in changes["description"]:
                    benefits = changes["description"]["benefits_changes"]
                    if benefits["removed"]:
                        details += f" 제거된 혜택: {', '.join(benefits['removed'])}"
                    if benefits["added"]:
                        details += f" 추가된 혜택: {', '.join(benefits['added'])}"
            else:
                details = f"변경된 항목: {', '.join(changes.keys())}"
        else:
            details = "변경 사항 없음"
            
        return DetectionResult(
            session_id=session_id,
            product_id=product_id,
            is_fraud_detected=is_fraud_detected,
            changes=changes,
            confidence_score=confidence_score,
            details=details
        ) 