"""
YouTube 자막 추출 테스트 스크립트
URL을 입력하면 자막을 추출하여 출력합니다.
"""

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)
import re


def extract_video_id(url: str) -> str:
    """URL에서 video_id 추출"""
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    elif "watch?v=" in url:
        return url.split("watch?v=")[1].split("&")[0]
    else:
        return url


def get_transcript(video_id: str, languages: list = ["ko", "en"]) -> dict:
    """자막 추출 (main.py와 완전히 동일한 방식)"""
    print(f"\n{'='*60}")
    print(f"비디오 ID: {video_id}")
    print(f"요청 언어: {', '.join(languages)}")
    print(f"{'='*60}\n")
    
    try:
        # 1. YouTubeTranscriptApi 인스턴스 생성
        print("[단계 1] API 인스턴스 생성...")
        ytt_api = YouTubeTranscriptApi()
        
        # 2. 사용 가능한 자막 목록 가져오기
        print("[단계 2] 사용 가능한 자막 목록 확인 중...")
        transcript_list = ytt_api.list(video_id)
        
        # 사용 가능한 자막 언어 출력
        available_langs = []
        for trans in transcript_list:
            available_langs.append(f"{trans.language} ({trans.language_code})")
        print(f"[정보] 사용 가능한 자막: {', '.join(available_langs)}\n")
        
        # 3. 원하는 언어의 자막 찾기
        print(f"[단계 3] {', '.join(languages)} 자막 검색 중...")
        transcript = transcript_list.find_transcript(languages)
        
        print(f"[성공] {transcript.language} ({transcript.language_code}) 자막 발견!")
        print(f"[단계 4] 자막 다운로드 중...")
        
        # 4. 자막 데이터 가져오기
        fetched_transcript = transcript.fetch()
        
        # 5. 자막 텍스트 결합
        full_text = " ".join([snippet.text for snippet in fetched_transcript])
        
        # 6. transcript_list 변환 (타임스탬프 포함)
        transcript_with_time = [
            {
                'text': snippet.text,
                'start': snippet.start,
                'duration': snippet.duration
            }
            for snippet in fetched_transcript
        ]
        
        print(f"[완료] 자막 추출 성공!")
        print(f"[정보] 조각 수: {len(fetched_transcript)}개")
        print(f"[정보] 텍스트 길이: {len(full_text)}자\n")
        
        return {
            'success': True,
            'language': transcript.language,
            'language_code': transcript.language_code,
            'is_generated': transcript.is_generated,
            'snippet_count': len(fetched_transcript),
            'text_length': len(full_text),
            'transcript': full_text,
            'transcript_list': transcript_with_time
        }
        
    except NoTranscriptFound:
        print("[실패] 요청한 언어의 자막을 찾을 수 없습니다.")
        return {
            'success': False,
            'error': '요청한 언어의 자막이 없습니다'
        }
        
    except TranscriptsDisabled:
        print("[오류] 이 영상은 자막이 비활성화되어 있습니다.")
        return {'success': False, 'error': '자막 비활성화'}
        
    except VideoUnavailable:
        print("[오류] 영상을 찾을 수 없거나 접근할 수 없습니다.")
        return {'success': False, 'error': '영상 접근 불가'}
        
    except Exception as e:
        print(f"[오류] {type(e).__name__}: {str(e)}")
        return {'success': False, 'error': str(e)}


def print_transcript(result: dict):
    """자막 출력"""
    if not result['success']:
        print(f"\n❌ 자막 추출 실패: {result['error']}")
        return
    
    print(f"\n{'='*60}")
    print(f"✅ 자막 추출 성공!")
    print(f"{'='*60}")
    print(f"언어: {result['language']} ({result['language_code']})")
    print(f"자막 유형: {'자동 생성' if result.get('is_generated') else '수동 생성'}")
    print(f"조각 수: {result['snippet_count']}개")
    print(f"텍스트 길이: {result['text_length']}자")
    print(f"{'='*60}\n")
    
    # 전체 텍스트 출력
    print("[전체 자막 텍스트]")
    print(result['transcript'])
    print(f"\n{'='*60}")
    
    # 타임스탬프 포함 출력 (처음 10개만)
    print("\n[타임스탬프 포함 (처음 10개)]")
    for i, item in enumerate(result['transcript_list'][:10], 1):
        start = item['start']
        duration = item['duration']
        minutes = int(start // 60)
        seconds = int(start % 60)
        print(f"[{minutes:02d}:{seconds:02d}] ({duration:.2f}초) {item['text']}")
    
    if len(result['transcript_list']) > 10:
        print(f"... (외 {len(result['transcript_list']) - 10}개)")


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("YouTube 자막 추출 테스트")
    print("="*60 + "\n")
    
    while True:
        # URL 입력
        url = input("YouTube URL을 입력하세요 (종료: q): ").strip()
        
        if url.lower() == 'q':
            print("\n프로그램을 종료합니다.")
            break
        
        if not url:
            print("❌ URL을 입력해주세요.\n")
            continue
        
        # 언어 입력 (선택)
        lang_input = input("언어를 입력하세요 (기본: ko,en): ").strip()
        languages = [l.strip() for l in lang_input.split(",")] if lang_input else ["ko", "en"]
        
        # 비디오 ID 추출
        video_id = extract_video_id(url)
        
        # 자막 추출
        result = get_transcript(video_id, languages)
        
        # 결과 출력
        print_transcript(result)
        
        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"\n예상치 못한 오류: {e}")

