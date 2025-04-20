#!/usr/bin/env python3
# 플레이스홀더 이미지 생성 스크립트

import os
import sys
from PIL import Image, ImageDraw, ImageFont

def create_placeholder_image(output_path, width, height, text, bg_color=(240, 240, 240), text_color=(100, 100, 100)):
    """지정된 텍스트가 포함된 플레이스홀더 이미지 생성"""
    # 이미지 생성
    image = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(image)
    
    # 텍스트 그리기
    try:
        # 시스템 폰트가 있으면 사용
        font = ImageFont.truetype("Arial", 24)
    except IOError:
        # 시스템 폰트를 찾을 수 없으면 기본 폰트 사용
        font = ImageFont.load_default()
    
    # 텍스트 위치 계산 (중앙)
    try:
        # Pillow >= 9.2.0
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_width = right - left
        text_height = bottom - top
    except AttributeError:
        # 이전 버전 호환용 (9.2.0 이전)
        try:
            text_width, text_height = draw.textsize(text, font=font)
        except AttributeError:
            # 최신 Pillow에서는 다음 방법도 가능
            text_width = draw.textlength(text, font=font)
            text_height = font.getbbox(text)[3]  # 근사치
    
    # 텍스트 위치 계산 (중앙)
    position = ((width - text_width) // 2, (height - text_height) // 2)
    
    # 텍스트 그리기
    draw.text(position, text, font=font, fill=text_color)
    
    # 테두리 그리기
    draw.rectangle([(0, 0), (width-1, height-1)], outline=(200, 200, 200))
    
    # 디렉토리 확인 및 생성
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 이미지 저장
    image.save(output_path)
    print(f"이미지 생성 완료: {output_path}")

def main():
    """메인 함수"""
    # 스크립트 경로 기준으로 상대 경로 생성
    base_dir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(base_dir, 'static', 'images')
    
    # 디렉토리 생성
    os.makedirs(images_dir, exist_ok=True)
    
    # 플레이스홀더 이미지 생성
    create_placeholder_image(
        os.path.join(images_dir, 'placeholder.jpg'),
        400, 300, 
        "이미지 준비 중"
    )
    
    create_placeholder_image(
        os.path.join(images_dir, 'smartphone.jpg'),
        400, 300, 
        "스마트폰 이미지"
    )
    
    create_placeholder_image(
        os.path.join(images_dir, 'laptop.jpg'),
        400, 300, 
        "노트북 이미지"
    )
    
    create_placeholder_image(
        os.path.join(images_dir, 'earbuds.jpg'),
        400, 300, 
        "이어폰 이미지"
    )
    
    print("모든 이미지 생성 완료!")

if __name__ == "__main__":
    main() 