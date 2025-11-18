"""
YouTube 댓글 추출 테스트 스크립트
URL을 입력하면 인기 댓글을 추출하여 출력합니다.
"""

import yt_dlp


def extract_video_id(url: str) -> str:
    """URL에서 video_id 추출"""
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    elif "watch?v=" in url:
        return url.split("watch?v=")[1].split("&")[0]
    else:
        return url


def get_comments(video_url: str, max_comments: int = 100) -> dict:
    """yt-dlp로 댓글 추출 (인기순)"""
    
    print(f"\n{'='*60}")
    print(f"영상 URL: {video_url}")
    print(f"요청 댓글 수: {max_comments}개")
    print(f"{'='*60}\n")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
        'getcomments': True,  # 댓글 가져오기
        'extractor_args': {
            'youtube': {
                'max_comments': [str(max_comments)],
                'comment_sort': ['top']  # 인기순 정렬
            }
        },
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'http_headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        },
        'retries': 3,
        'socket_timeout': 30,
    }
    
    try:
        print("[단계 1] 영상 정보 가져오는 중...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"[단계 2] 댓글 추출 중 (최대 {max_comments}개)...")
            info = ydl.extract_info(video_url, download=False)
            
            comments = []
            
            if info.get('comments'):
                print(f"[진행] 댓글 데이터 처리 중...")
                for comment in info['comments']:
                    comments.append({
                        'author': comment.get('author'),
                        'text': comment.get('text'),
                        'like_count': comment.get('like_count', 0),
                        'time_text': comment.get('time_text'),
                        'author_id': comment.get('author_id'),
                        'author_thumbnail': comment.get('author_thumbnail'),
                        'is_favorited': comment.get('is_favorited', False),
                        'author_is_uploader': comment.get('author_is_uploader', False),
                        'reply_count': comment.get('_reply_continuation', 0) if comment.get('_reply_continuation') else 0
                    })
                    if len(comments) >= max_comments:
                        break
            
            print(f"[완료] 댓글 추출 성공! ({len(comments)}개)\n")
            
            return {
                'success': True,
                'video_id': info.get('id'),
                'video_title': info.get('title'),
                'channel': info.get('uploader') or info.get('channel'),
                'comment_count': info.get('comment_count', 0),
                'comments': comments,
                'fetched_count': len(comments)
            }
            
    except Exception as e:
        print(f"[오류] 댓글 추출 실패: {str(e)}\n")
        return {
            'success': False,
            'error': str(e)
        }


def print_comments(result: dict):
    """댓글 출력"""
    if not result['success']:
        print(f"\n댓글 추출 실패: {result['error']}")
        return
    
    print(f"\n{'='*60}")
    print(f"댓글 추출 성공!")
    print(f"{'='*60}")
    print(f"영상 ID: {result['video_id']}")
    print(f"영상 제목: {result['video_title']}")
    print(f"채널: {result['channel']}")
    print(f"전체 댓글 수: {result['comment_count']:,}개")
    print(f"추출된 댓글 수: {result['fetched_count']}개")
    print(f"{'='*60}\n")
    
    # 댓글 출력
    print("[인기 댓글 목록 (좋아요 많은 순)]\n")
    
    for i, comment in enumerate(result['comments'], 1):
        print(f"{'='*60}")
        print(f"[{i}] {comment['author']}")
        
        # 특별 표시
        badges = []
        if comment.get('author_is_uploader'):
            badges.append("채널 주인")
        if comment.get('is_favorited'):
            badges.append("고정됨")
        
        if badges:
            print(f"    [{' | '.join(badges)}]")
        
        print(f"    좋아요: {comment['like_count']:,}개 | 답글: {comment.get('reply_count', 0)}개 | {comment['time_text']}")
        print(f"\n    {comment['text']}\n")
    
    print(f"{'='*60}")
    print(f"\n통계:")
    print(f"  - 총 좋아요 수: {sum(c['like_count'] for c in result['comments']):,}개")
    print(f"  - 평균 좋아요: {sum(c['like_count'] for c in result['comments']) / len(result['comments']):.1f}개")
    print(f"  - 최고 좋아요: {max(c['like_count'] for c in result['comments']):,}개")


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("YouTube 댓글 추출 테스트 (인기순)")
    print("="*60 + "\n")
    
    while True:
        # URL 입력
        url = input("YouTube URL을 입력하세요 (종료: q): ").strip()
        
        if url.lower() == 'q':
            print("\n프로그램을 종료합니다.")
            break
        
        if not url:
            print("URL을 입력해주세요.\n")
            continue
        
        # 댓글 개수 입력 (선택)
        count_input = input("댓글 개수를 입력하세요 (기본: 100): ").strip()
        max_comments = int(count_input) if count_input.isdigit() else 100
        
        # 댓글 추출
        result = get_comments(url, max_comments)
        
        # 결과 출력
        print_comments(result)
        
        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"\n예상치 못한 오류: {e}")

