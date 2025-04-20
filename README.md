# AI 쇼핑 속임수 탐지 시스템

이 프로젝트는 AI 쇼핑 에이전트가 수집하는 정보를 실시간으로 모니터링하고 검증하여 전자상거래 사이트의 속임수를 탐지하는 시스템입니다.

## 시스템 개요

이 시스템은 AI 에이전트와 전자상거래 웹/데이터 소스 사이에 위치하여, 에이전트가 수집하는 정보를 실시간으로 모니터링하고 검증합니다. 이를 통해 전자상거래 사이트에서 발생할 수 있는 다양한 종류의 속임수(가격 변경, 허위 상품 설명 등)를 탐지하고 사용자에게 경고할 수 있습니다.

### 주요 구성 요소

1. **MCP 인터페이스 모듈**: 에이전트의 MCP(Merchant-Consumer Protocol) 요청/응답을 실시간으로 포착합니다.
   - `src/interfaces/mcp_interface.py`에 구현되어 있으며, 요청과 응답을 인터셉트하고 처리합니다.
   - 데이터 흐름을 기록하고 모니터링하는 프록시 역할을 수행합니다.

2. **문맥 저장소**: 에이전트가 처음 획득한 상품 정보의 스냅샷을 저장합니다.
   - `src/storage/context_storage.py`에 구현되어 메모리 기반 저장 방식을 사용합니다.
   - 나중에 비교할 수 있도록 세션 ID와 제품 ID를 기준으로 정보를 저장합니다.

3. **데이터 재수집 및 비교 모듈**: 거래 완료 전에 동일 상품의 최신 정보를 다시 불러와 비교합니다.
   - `src/detectors/data_collector.py`가 여러 채널(MCP, 웹 스크래핑)을 통해 최신 정보를 수집합니다.
   - `src/detectors/comparator.py`가 원본 정보와 최신 정보를 비교하여 불일치를 감지합니다.
   - LLM(Large Language Model)을 활용한 고급 설명 속임수 탐지 기능도 구현되어 있습니다.

4. **이상 탐지 엔진**: 비교 결과 비정상적인 변화가 감지되면 이를 속임수로 판단합니다.
   - `src/detectors/fraud_detector.py`에서 각종 이상 징후를 감지하고 점수화합니다.
   - 가격 변동률, 설명 텍스트 유사도, 특히 "혜택/서비스" 관련 단어의 추가/제거를 정밀하게 분석합니다.

5. **알림 및 대응 컴포넌트**: 이상 탐지 엔진이 속임수를 확인하면 즉시 대응합니다.
   - `src/notification/notifier.py`가 다양한 채널(콘솔, 로그, UI 경고)을 통해 알림을 발송합니다.
   - 심각도에 따라 단순 경고부터 거래 중단까지 여러 대응 방식을 제공합니다.

### MCP API 작동 방식

MCP(Merchant-Consumer Protocol) API는 AI 쇼핑 에이전트와 판매자 사이의 표준화된 통신 방식으로, 다음과 같은 흐름으로 작동합니다:

1. **API 엔드포인트**: 주요 엔드포인트는 `/api/mcp/product/<product_id>`, `/api/mcp/cart`, `/api/mcp/search` 등이 있습니다.
2. **데이터 호출 시점**:
   - 상품 상세 페이지 방문 시 자동으로 `/api/mcp/product/<product_id>` 호출
   - 장바구니 페이지 방문 시 자동으로 `/api/mcp/cart` 호출
3. **헤더 정보**: 각 요청에는 `X-Session-ID` 헤더가 포함되어 사용자 세션을 추적합니다.
4. **로깅**: 모든 MCP API 호출은 관리자 페이지의 로그 섹션에 기록되며, 요청과 응답 데이터를 모두 확인할 수 있습니다.

## 테스트용 모의 쇼핑몰

시스템 테스트를 위한 모의 쇼핑몰이 `src/mock_shop` 디렉토리에 구현되어 있습니다. 이 모의 쇼핑몰에서는 다양한 속임수 시나리오를 시뮬레이션할 수 있습니다.

### 주요 속임수 시나리오

1. **가격 속임수**: 제품의 광고 가격은 저렴하게 보여주고, 실제 결제 시에는 더 비싼 가격이 적용됩니다.
   - 예: 표시 가격 ₩800,000, 실제 가격 ₩1,000,000 (20% 할인된 것처럼 보이지만 결제 시 원래 가격 적용)
   - **기술적 구현**: `app.py`의 상품 데이터에서 `display_price`와 `price` 필드를 다르게 설정하여 구현
   - **관련 코드**: `src/mock_shop/app.py`의 `toggle_fraud` 함수에서 가격을 조작하는 로직 확인 가능

2. **설명 속임수**: 제품 설명에 실제로는 없는 기능이나 서비스를 추가하여 광고합니다.
   - 예: 실제로는 보증이 없는 제품에 "평생 무상 A/S와 물적 파손 보험 포함"과 같은 거짓 정보 추가
   - 예: 방수 기능이 없는 제품에 "IP68 완전 방수" 같은 거짓 정보 포함
   - **기술적 구현**: `app.py`의 상품 데이터에서 `display_description`과 `description` 필드를 다르게 설정
   - **속임수 판단 로직**: `src/detectors/comparator.py`의 `compare_descriptions_llm` 메서드에서 텍스트 분석을 통해 추가된 허위 혜택을 탐지


### 속임수 탐지 시스템 상세 작동 방식

1. **초기 정보 캡처**:
   - 사용자가 상품을 처음 볼 때 MCP API(`/api/mcp/product/<product_id>`)가 호출됩니다.
   - 이 정보는 `context_storage`에 원본 상품 정보로 저장됩니다.
   - 관련 코드: `src/mock_shop/detector_integration.py`의 `monitor_product_view` 메서드

2. **장바구니 추가 시 검증**:
   - 상품이 장바구니에 추가될 때 해당 상품의 최신 정보를 수집합니다.
   - 저장된 원본 정보와 새로 수집한 정보를 비교하여 속임수 여부를 판단합니다.
   - 관련 코드: `src/system.py`의 `on_add_to_cart` 메서드

3. **결제 단계 검증**:
   - 결제 페이지로 이동할 때 장바구니의 모든 상품에 대해 다시 한번 속임수 검증을 수행합니다.
   - 관련 코드: `src/system.py`의 `on_checkout` 메서드 및 `src/mock_shop/app.py`의 `checkout` 라우트

4. **설명 속임수 세부 탐지 방법**:
   - **텍스트 유사도 비교**: 전체 설명 텍스트의 유사도를 계산합니다.
   - **LLM 기반 의미 분석**: 설명에서 혜택, 서비스, 기능 관련 문구를 추출하고 비교합니다.
   - **기만성 점수 계산**: 추가/삭제된 혜택의 중요도와 수량에 따라 속임수 점수를 계산합니다.
   - 관련 코드: `src/detectors/comparator.py`의 `compare_descriptions_llm`, `_extract_benefits_from_llm_analysis` 메서드

5. **알림 및 대응**:
   - 속임수가 탐지되면 UI에 경고 메시지를 표시합니다.
   - 결제 과정에서는 실제 정확한 정보와 가격으로 진행합니다.
   - 관련 코드: `src/notification/notifier.py` 및 템플릿 파일의 경고 메시지 섹션

### 관리자 기능

관리자 페이지(`/admin`)에서는 다음 기능을 제공합니다:
- 상품별 속임수 설정/해제 (가격 또는 설명)
  - 버튼 클릭으로 각 상품의 속임수 유형을 전환할 수 있습니다.
  - 가격 속임수: 일반적으로 20% 할인된 가격으로 표시하도록 설정됩니다.
  - 설명 속임수: 실제로는 없는 혜택/기능을 추가합니다.

- MCP API 로그 조회 및 관리
  - 모든 MCP API 호출(요청/응답)을 시간 순으로 확인할 수 있습니다.
  - 각 로그 항목에는 엔드포인트, 헤더, 요청/응답 데이터가 포함됩니다.
  - "로그 지우기" 버튼으로 로그를 초기화할 수 있습니다.

- 가격과 설명 속임수에 대한 실시간 시뮬레이션
  - 관리자 인터페이스에서 속임수 설정 후 쇼핑 흐름을 통해 탐지 기능을 테스트할 수 있습니다.

## 설치 및 실행 방법

### 요구 사항

- Python 3.8 이상
- 필요 라이브러리: Flask, Requests, Python-dotenv, PyMongo, NLTK, NumPy, Loguru, Pydantic, OpenAI

### 설치

```bash
pip install -r requirements.txt
```

OpenAI API를 사용하는 경우 API 키 설정:
```bash
export OPENAI_API_KEY=your_api_key_here
```

### 모의 쇼핑몰 실행

```bash
cd src/mock_shop
python app.py
```

기본적으로 `http://localhost:5000`에서 모의 쇼핑몰이 실행됩니다.

### 시뮬레이션 실행

```bash
python src/main.py --scenario all
```

또는 대화형 모드로 실행:

```bash
python src/main.py
```

대규모 테스트 실행:

```bash
python src/main.py --scenario large_scale
```



## 사용 방법

1. 모의 쇼핑몰에 접속하여 상품을 탐색합니다.
2. 관리자 페이지에서 특정 상품에 대한 속임수를 설정합니다.
   - 가격 속임수: 할인된 가격으로 표시하지만 실제로는 원래 가격으로 계산
   - 설명 속임수: 실제로는 없는 혜택/기능을 추가하여 표시
3. 상품 상세 페이지에서 표시되는 정보를 확인합니다.
4. 장바구니에 상품을 추가하고 결제 페이지로 이동하여 속임수 탐지 결과를 확인합니다.
5. 결제 시 실제 상품 정보와 가격이 적용되는 것을 확인합니다.

## MCP API 테스트 방법

이 시스템은 실제 AI 쇼핑 에이전트가 호출하는 MCP API를 시뮬레이션합니다:

1. **자동 API 호출**:
   - 상품 상세 페이지 방문 시 자동으로 `/api/mcp/product/<product_id>` API가 호출됩니다.
   - 장바구니 페이지 방문 시 자동으로 `/api/mcp/cart` API가 호출됩니다.
   
2. **수동 API 테스트**:
   - 브라우저 개발자 도구의 콘솔에서 다음 코드로 API 호출 테스트 가능:
   ```javascript
   fetch('/api/mcp/product/PRODUCT001', {
     headers: { 'X-Session-ID': 'test-session' }
   }).then(r => r.json()).then(console.log);
   ```

3. **로그 확인**:
   - 관리자 페이지(`/admin`)에서 모든 API 호출 기록과 데이터를 확인할 수 있습니다.

## 상세 기술 구현

### 속임수 탐지 핵심 로직

1. **가격 속임수 탐지**:
   - `src/detectors/comparator.py`의 `compare_price` 메서드
   - 원본 가격과 현재 가격의 차이가 임계값(기본 5%)을 초과하면 속임수로 판단
   - 관련 코드: `return (abs(diff_ratio) > self.price_threshold, diff_ratio)`

2. **설명 속임수 탐지**:
   - 단순 텍스트 유사도 비교: `compare_description` 메서드
   - 의미론적 분석: `compare_descriptions_semantic` 메서드
   - LLM 기반 분석: `compare_descriptions_llm` 메서드가 가장 정확하게 혜택 추가/삭제를 감지
   - 관련 코드: LLM 프롬프트는 "상품 설명을 분석하고 실제 혜택과 허위 혜택을 구분" 요청

3. **문맥 저장 및 비교**:
   - `src/storage/context_storage.py`에서 세션별, 상품별 원본 정보 저장
   - `src/detectors/fraud_detector.py`의 `verify_product` 메서드에서 문맥과 최신 데이터 비교
   - 관련 코드: `detection_result = self.product_comparator.compare_product_info(original_info, current_info)`

4. **표현 변형 감지**:
   - `src/system.py`의 `WordingVariationCollector` 클래스
   - 미묘한 표현 변화에 대한 판단을 LLM에 위임하여 인간 판단과 유사한 결과 도출
   - 관련 코드: `product_info.description = "고급 스마트폰 - 1년 정품 보증 포함, 기술지원 서비스"`

## 테스트

```bash
pytest tests/
```

단위 테스트는 다음 시나리오를 검증합니다:
- 정상 상품(변경 없음) 시나리오
- 가격 속임수 시나리오
- 설명 속임수 시나리오
- 알림 생성 및 전달 시나리오

대규모 테스트는 다음과 같이 실행합니다:
```bash
python src/main.py --scenario large_scale
```

이 테스트는 다음 항목을 자동으로 측정하고 분석합니다:
- 가격/설명 속임수에 대한 탐지율
- 정상 시나리오에 대한 오탐지율
- 처리 시간 및 시스템 효율성
- 종합적인 정밀도 및 재현율

## 주요 시스템 흐름

1. 사용자가 상품 조회 → 원본 정보 저장
2. 장바구니 추가 → 속임수 검증
3. 결제 진행 → 모든 상품 재검증
4. 주문 완료 → 실제 정보로 결제

## 시스템 컴포넌트

- `src/interfaces/mcp_interface.py`: MCP 인터페이스 모듈
- `src/storage/context_storage.py`: 문맥 저장소
- `src/detectors/data_collector.py`: 데이터 재수집 모듈
- `src/detectors/comparator.py`: 상품 정보 비교 모듈
- `src/detectors/fraud_detector.py`: 이상 탐지 엔진
- `src/notification/notifier.py`: 알림 시스템
- `src/system.py`: 통합 시스템 (WordingVariationCollector 포함)
- `src/mock_shop/app.py`: 모의 쇼핑몰 애플리케이션
- `src/mock_shop/detector_integration.py`: 쇼핑몰-탐지 시스템 연동
- `src/main.py`: 테스트 및 시뮬레이션 도구

## 확장 및 개선 방향

1. **실시간 모니터링 대시보드**: 속임수 탐지 통계 및 패턴 분석
2. **머신러닝 모델 통합**: 더욱 정교한 속임수 탐지를 위한 지도 학습 모델 통합
3. **다중 소스 검증**: 여러 데이터 소스에서 상품 정보를 수집하여 교차 검증
4. **API 확장**: 더 많은 전자상거래 플랫폼과의 통합을 위한 API 확장
5. **자동화된 성능 보고서**: 성능 지표 시각화 및 자동 알림 시스템 구축

