"""
터미널에서 직접 실행하는 CSV 배치 추출 스크립트
CSV 파일에서 URL을 읽어 추출 후 결과를 파일로 저장
"""

import csv
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# main.py의 함수들을 import
from main import extract_video_data, extract_video_id
import time
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def read_urls_from_csv(csv_file_path: str) -> list:
    """CSV 파일에서 URL 추출"""
    urls = []
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            for row_idx, row in enumerate(csv_reader):
                if row_idx == 0:
                    # 헤더 행 건너뛰기
                    continue
                if row and len(row) > 0:
                    url = row[0].strip()
                    if url and ('youtube.com' in url or 'youtu.be' in url or len(url) == 11):
                        # URL 형식이 아니면 video_id로 간주
                        if not url.startswith('http'):
                            url = f"https://www.youtube.com/watch?v={url}"
                        urls.append(url)
        return urls
    except Exception as e:
        logger.error(f"CSV 파일 읽기 오류: {str(e)}")
        return []


def save_to_json(results: list, output_file: str):
    """JSON 파일로 저장"""
    data = [result.dict() for result in results]
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"JSON 파일 저장 완료: {output_file}")


def save_to_csv(results: list, output_file: str):
    """CSV 파일로 저장"""
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:  # BOM 추가 (Excel 호환)
        writer = csv.writer(f)
        
        # 헤더 작성
        writer.writerow([
            'video_id', 'title', 'url', 'view_count', 'like_count', 'comment_count',
            'channel', 'channel_follower_count', 'upload_date', 'duration_string',
            'transcript_preview', 'transcript_language', 'transcript_snippet_count',
            'transcript_full', 'error'
        ])
        
        # 데이터 작성
        for result in results:
            writer.writerow([
                result.video_id,
                result.title,
                result.url,
                result.view_count,
                result.like_count,
                result.comment_count,
                result.channel,
                result.channel_follower_count,
                result.upload_date,
                result.duration_string,
                result.transcript[:500] if result.transcript else "",  # 처음 500자만
                result.transcript_language,
                result.snippet_count,
                result.transcript if result.transcript else "",  # 전체 자막
                result.error if result.error else ""
            ])
    logger.info(f"CSV 파일 저장 완료: {output_file}")


def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        print("\n사용법:")
        print("  python extract_from_csv.py <CSV파일경로> [언어] [출력형식] [출력파일경로]")
        print("\n예시:")
        print("  python extract_from_csv.py urls.csv")
        print("  python extract_from_csv.py urls.csv ko")
        print("  python extract_from_csv.py urls.csv ko json")
        print("  python extract_from_csv.py urls.csv ko csv output.csv")
        print("\n참고: 기본값은 한국어(ko)만 추출합니다.")
        print("\nCSV 파일 형식:")
        print("  url")
        print("  https://www.youtube.com/watch?v=VIDEO_ID_1")
        print("  VIDEO_ID_2")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    languages = sys.argv[2].split(",") if len(sys.argv) > 2 else ["ko"]  # 기본값: 한국어만
    output_format = sys.argv[3] if len(sys.argv) > 3 else "json"
    output_file = sys.argv[4] if len(sys.argv) > 4 else None
    
    # CSV 파일 확인
    if not os.path.exists(csv_file):
        logger.error(f"CSV 파일을 찾을 수 없습니다: {csv_file}")
        sys.exit(1)
    
    # URL 읽기
    logger.info(f"CSV 파일 읽기: {csv_file}")
    urls = read_urls_from_csv(csv_file)
    
    if not urls:
        logger.error("유효한 URL을 찾을 수 없습니다.")
        sys.exit(1)
    
    logger.info(f"총 {len(urls)}개 URL 발견")
    
    if len(urls) > 200:
        logger.warning(f"200개를 초과합니다. 처음 200개만 처리합니다.")
        urls = urls[:200]
    
    # 출력 파일명 생성
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if output_format.lower() == "csv":
            output_file = f"youtube_extract_{timestamp}.csv"
        else:
            output_file = f"youtube_extract_{timestamp}.json"
    
    # 배치 처리
    results = []
    for idx, url in enumerate(urls, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"처리 중: {idx}/{len(urls)}")
        logger.info(f"URL: {url}")
        logger.info(f"{'='*60}")
        
        try:
            result = extract_video_data(url, languages)
            results.append(result)
            logger.info(f"성공: {result.title}")
        except Exception as e:
            logger.error(f"실패: {str(e)}")
            from main import VideoResponse
            results.append(VideoResponse(
                video_id=extract_video_id(url),
                title="처리 실패",
                url=url,
                error=str(e)
            ))
        
        # API 제한 방지 (429 오류 대응)
        if idx < len(urls):
            if len(urls) >= 100:
                delay = 5.0  # 100개 이상: 5초 대기 (429 오류 방지)
            elif len(urls) > 50:
                delay = 3.0  # 50개 이상: 3초 대기
            else:
                delay = 2.0  # 그 외: 2초 대기
            logger.info(f"다음 요청까지 {delay}초 대기...")
            time.sleep(delay)
    
    # 결과 저장
    logger.info(f"\n{'='*60}")
    logger.info(f"처리 완료: 성공 {len([r for r in results if not r.error])}/{len(results)}")
    logger.info(f"{'='*60}\n")
    
    if output_format.lower() == "csv":
        save_to_csv(results, output_file)
    else:
        save_to_json(results, output_file)
    
    logger.info(f"\n모든 작업 완료!")
    logger.info(f"결과 파일: {os.path.abspath(output_file)}")
    logger.info(f"성공: {len([r for r in results if not r.error])}개")
    logger.info(f"실패: {len([r for r in results if r.error])}개")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\n작업이 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n예상치 못한 오류: {str(e)}")
        sys.exit(1)

