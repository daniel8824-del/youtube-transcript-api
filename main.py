"""
YouTube 영상 정보 + 자막 추출 API (youtube-transcript-api 최신 버전)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled, 
    NoTranscriptFound,
    VideoUnavailable
)
import logging
import time
from langdetect import detect, LangDetectException

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube Video Extractor", 
    version="2.0",
    description="유튜브 영상 정보와 자막을 추출하는 API"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 요청/응답 모델 =====

class VideoRequest(BaseModel):
    video_url: str
    languages: Optional[List[str]] = ["ko", "en"]

class BatchVideoRequest(BaseModel):
    video_urls: List[str]
    languages: Optional[List[str]] = ["ko", "en"]

class CommentRequest(BaseModel):
    video_url: str
    max_comments: Optional[int] = 100  # 기본 100개

class SubtitleUrlRequest(BaseModel):
    video_url: str

class SubtitleUrlResponse(BaseModel):
    video_id: str
    subtitle_urls: Optional[List[Dict[str, str]]] = None
    error: Optional[str] = None

class VideoResponse(BaseModel):
    # 기본 정보
    video_id: str
    title: str
    url: str
    description: Optional[str] = None
    
    # 조회/반응 통계
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    
    # 채널 정보
    channel: Optional[str] = None
    channel_id: Optional[str] = None
    channel_url: Optional[str] = None
    channel_follower_count: Optional[int] = None  # 구독자 수
    
    # 영상 메타데이터
    upload_date: Optional[str] = None
    duration: Optional[int] = None
    duration_string: Optional[str] = None  # "3:20" 형식
    language: Optional[str] = None
    
    # 미디어
    thumbnail: Optional[str] = None
    
    # 분류
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    
    # 자막 텍스트
    transcript: Optional[str] = None
    transcript_language: Optional[str] = None
    transcript_language_name: Optional[str] = None
    is_generated: Optional[bool] = None
    snippet_count: Optional[int] = None
    transcript_list: Optional[List[Dict[str, Any]]] = None
    
    # 자막 URL (언어, 형태, URL만 간단하게)
    subtitle_urls: Optional[List[Dict[str, str]]] = None
    
    error: Optional[str] = None

# ===== 유틸리티 함수 =====

def extract_video_id(url: str) -> str:
    """URL에서 video_id 추출"""
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    elif "watch?v=" in url:
        return url.split("watch?v=")[1].split("&")[0]
    else:
        return url

def detect_language(text: str) -> str:
    """텍스트 언어 감지 (langdetect 사용)"""
    if not text or len(text.strip()) < 3:
        return "unknown"
    try:
        lang = detect(text)
        return lang
    except LangDetectException:
        return "unknown"

def get_video_info(video_url: str) -> Dict[str, Any]:
    """yt-dlp로 영상 정보 추출"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
        'writesubtitles': True,  # 자막 정보 포함
        'writeautomaticsub': True,  # 자동 자막 정보 포함
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
        'fragment_retries': 3,
        'socket_timeout': 30,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"영상 정보 추출 중: {video_url}")
            info = ydl.extract_info(video_url, download=False)
            
            # duration을 "MM:SS" 형식으로 변환
            duration_string = None
            if info.get('duration'):
                minutes = info['duration'] // 60
                seconds = info['duration'] % 60
                duration_string = f"{minutes}:{seconds:02d}"
            
            # 자막 URL 추출 (간소화: language, ext, url만)
            subtitle_urls = []
            
            # 수동 자막 (VTT 우선)
            if info.get('subtitles'):
                for lang, subs in info['subtitles'].items():
                    # VTT를 우선으로 찾기
                    vtt_sub = next((s for s in subs if s.get('ext') == 'vtt'), None)
                    if vtt_sub:
                        subtitle_urls.append({
                            'language': lang,
                            'ext': 'vtt',
                            'url': vtt_sub.get('url')
                        })
                    else:
                        # VTT가 없으면 다른 포맷
                        for sub in subs:
                            if sub.get('ext') in ['json3', 'srv3']:
                                subtitle_urls.append({
                                    'language': lang,
                                    'ext': sub.get('ext'),
                                    'url': sub.get('url')
                                })
                                break
            
            # 자동 생성 자막 (VTT 우선)
            if info.get('automatic_captions'):
                for lang, subs in info['automatic_captions'].items():
                    # VTT를 우선으로 찾기
                    vtt_sub = next((s for s in subs if s.get('ext') == 'vtt'), None)
                    if vtt_sub:
                        subtitle_urls.append({
                            'language': lang,
                            'ext': 'vtt',
                            'url': vtt_sub.get('url')
                        })
                    else:
                        # VTT가 없으면 다른 포맷
                        for sub in subs:
                            if sub.get('ext') in ['json3', 'srv3']:
                                subtitle_urls.append({
                                    'language': lang,
                                    'ext': sub.get('ext'),
                                    'url': sub.get('url')
                                })
                                break
            
            return {
                # 기본 정보
                'video_id': info.get('id'),
                'title': info.get('title'),
                'url': video_url,
                'description': info.get('description'),
                
                # 조회/반응 통계
                'view_count': info.get('view_count'),
                'like_count': info.get('like_count'),
                'comment_count': info.get('comment_count'),
                
                # 채널 정보
                'channel': info.get('uploader') or info.get('channel'),
                'channel_id': info.get('channel_id') or info.get('uploader_id'),
                'channel_url': info.get('channel_url') or info.get('uploader_url'),
                'channel_follower_count': info.get('channel_follower_count'),  # 구독자 수
                
                # 영상 메타데이터
                'upload_date': info.get('upload_date'),
                'duration': info.get('duration'),
                'duration_string': duration_string,
                'language': info.get('language'),
                
                # 미디어
                'thumbnail': info.get('thumbnail'),
                
                # 분류
                'tags': info.get('tags'),
                'categories': info.get('categories'),
                
                # 자막 URL (간소화)
                'subtitle_urls': subtitle_urls if subtitle_urls else None
            }
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        logger.error(f"다운로드 오류: {error_msg}")
        if "Video unavailable" in error_msg:
            raise HTTPException(status_code=404, detail="영상을 찾을 수 없거나 접근이 제한되었습니다.")
        elif "Precondition check failed" in error_msg:
            raise HTTPException(status_code=429, detail="YouTube에서 일시적으로 요청을 제한했습니다. 잠시 후 다시 시도해주세요.")
        else:
            raise HTTPException(status_code=400, detail=f"영상 정보를 가져올 수 없습니다: {error_msg}")
    except Exception as e:
        logger.error(f"영상 정보 추출 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

def get_transcript(video_id: str, languages: List[str] = ["ko", "en"]) -> Dict[str, Any]:
    """
    youtube-transcript-api 최신 버전으로 자막 추출
    
    변경사항:
    - YouTubeTranscriptApi() 인스턴스 생성
    - list() 메서드로 사용 가능한 자막 확인
    - find_transcript() 메서드로 원하는 언어의 자막 찾기
    - fetch() 메서드로 자막 가져오기
    """
    logger.info(f"자막 추출 시도: {video_id}, 언어: {languages}")
    
    try:
        # 1. YouTubeTranscriptApi 인스턴스 생성
        ytt_api = YouTubeTranscriptApi()
        
        # 2. 사용 가능한 자막 목록 가져오기
        transcript_list = ytt_api.list(video_id)
        
        # 사용 가능한 자막 언어 로그
        available_langs = []
        for trans in transcript_list:
            available_langs.append(f"{trans.language} ({trans.language_code})")
        logger.info(f"사용 가능한 자막: {', '.join(available_langs)}")
        
        # 3. 원하는 언어의 자막 찾기
        transcript = transcript_list.find_transcript(languages)
        
        logger.info(f"자막 다운로드 시도: 언어={transcript.language_code}")
        
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
        
        logger.info(f"자막 추출 성공: {transcript.language} ({transcript.language_code}), {len(fetched_transcript)}개 구간, {len(full_text)}자")
        
        return {
            'transcript': full_text,
            'language': transcript.language,
            'language_code': transcript.language_code,
            'is_generated': transcript.is_generated,
            'snippet_count': len(fetched_transcript),
            'transcript_list': transcript_with_time
        }
        
    except NoTranscriptFound:
        # 수동 생성 자막만 시도
        try:
            logger.info("수동 생성 자막만 검색 중...")
            transcript = transcript_list.find_manually_created_transcript(languages)
            fetched_transcript = transcript.fetch()
            full_text = " ".join([snippet.text for snippet in fetched_transcript])
            
            transcript_with_time = [
                {'text': snippet.text, 'start': snippet.start, 'duration': snippet.duration}
                for snippet in fetched_transcript
            ]
            
            logger.info(f"수동 자막 추출 성공: {transcript.language}")
            return {
                'transcript': full_text,
                'language': transcript.language,
                'language_code': transcript.language_code,
                'is_generated': False,
                'snippet_count': len(fetched_transcript),
                'transcript_list': transcript_with_time
            }
        except:
            pass
        
        # 자동 생성 자막만 시도
        try:
            logger.info("자동 생성 자막만 검색 중...")
            transcript = transcript_list.find_generated_transcript(languages)
            fetched_transcript = transcript.fetch()
            full_text = " ".join([snippet.text for snippet in fetched_transcript])
            
            transcript_with_time = [
                {'text': snippet.text, 'start': snippet.start, 'duration': snippet.duration}
                for snippet in fetched_transcript
            ]
            
            logger.info(f"자동 자막 추출 성공: {transcript.language}")
            return {
                'transcript': full_text,
                'language': transcript.language,
                'language_code': transcript.language_code,
                'is_generated': True,
                'snippet_count': len(fetched_transcript),
                'transcript_list': transcript_with_time
            }
        except Exception as e:
            logger.warning(f"자막 없음: {video_id}")
            return {'transcript': None, 'language': None, 'language_code': None, 'error': '자막 없음'}
    
    except TranscriptsDisabled:
        logger.warning(f"자막 비활성화: {video_id}")
        return {'transcript': None, 'language': None, 'language_code': None, 'error': '자막 비활성화'}
    
    except VideoUnavailable:
        logger.error(f"영상 접근 불가: {video_id}")
        return {'transcript': None, 'language': None, 'language_code': None, 'error': '영상 접근 불가'}
    
    except Exception as e:
        logger.error(f"자막 추출 중 오류: {type(e).__name__} - {str(e)}")
        return {'transcript': None, 'language': None, 'language_code': None, 'error': str(e)}

def get_language_group(language_code: str) -> str:
    """언어 코드를 언어 그룹으로 매핑"""
    if language_code == 'ko':
        return 'korean'
    elif language_code == 'ja':
        return 'japanese'
    elif language_code.startswith('zh'):
        return 'chinese'
    elif language_code in ['th', 'id', 'vi']:
        return 'southeast_asian'
    elif language_code in ['en', 'fr', 'de']:
        return 'western'
    elif language_code in ['es', 'pt']:
        return 'latin'
    else:
        return 'others'

def get_comments(video_url: str, max_comments: int = 100) -> Dict[str, Any]:
    """yt-dlp로 댓글 추출 (인기순) + 언어 감지"""
    
    # 먼저 영상 정보를 가져와서 전체 댓글 수 확인
    try:
        video_info = get_video_info(video_url)
        total_comment_count = video_info.get('comment_count')
        video_like_count = video_info.get('like_count')
        video_tags = video_info.get('tags')
        video_categories = video_info.get('categories')
        upload_date_raw = video_info.get('upload_date')
        video_description = video_info.get('description')
        video_link = video_info.get('url')
        channel_name = video_info.get('channel')
        channel_link = video_info.get('channel_url')
        video_views = video_info.get('view_count')
        video_length = video_info.get('duration_string')  # "MM:SS" 형식
        video_thumbnail = video_info.get('thumbnail')
        
        # 업로드 날짜 형식 변환: "20251113" -> "2025-11-13"
        upload_date_formatted = None
        if upload_date_raw and len(str(upload_date_raw)) == 8:
            date_str = str(upload_date_raw)
            upload_date_formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except Exception as e:
        logger.warning(f"영상 정보 추출 실패, 댓글만 추출: {str(e)}")
        total_comment_count = None
        video_like_count = None
        video_tags = None
        video_categories = None
        upload_date_formatted = None
        video_description = None
        video_link = None
        channel_name = None
        channel_link = None
        video_views = None
        video_length = None
        video_thumbnail = None
    
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
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"댓글 추출 중: {video_url} (최대 {max_comments}개)")
            
            info = ydl.extract_info(video_url, download=False)
            
            comments = []
            
            if info.get('comments'):
                for comment in info['comments']:
                    text = comment.get('text', '')
                    
                    # 언어 감지
                    detected_lang = detect_language(text)
                    # 언어 그룹 매핑
                    language_group = get_language_group(detected_lang)
                    
                    comments.append({
                        'author': comment.get('author'),
                        'text': text,
                        'like_count': comment.get('like_count', 0),
                        'time_text': comment.get('time_text'),
                        'author_id': comment.get('author_id'),
                        'author_thumbnail': comment.get('author_thumbnail'),
                        'is_favorited': comment.get('is_favorited', False),
                        'author_is_uploader': comment.get('author_is_uploader', False),
                        'reply_count': comment.get('_reply_continuation', 0) if comment.get('_reply_continuation') else 0,
                        'language': detected_lang,  # 언어 코드 (ko, ja, en 등)
                        'language_group': language_group  # 언어 그룹 (korean, japanese, chinese 등)
                    })
                    if len(comments) >= max_comments:
                        break
            
            # 언어별 분류 (6개 그룹)
            # 1. 한국어
            korean_comments = [c for c in comments if c['language'] == 'ko']
            # 2. 일본어
            japanese_comments = [c for c in comments if c['language'] == 'ja']
            # 3. 중국어 (zh, zh-cn, zh-tw 등)
            chinese_comments = [c for c in comments if c['language'].startswith('zh')]
            # 4. 동남아시아 (태국어, 인도네시아어, 베트남어)
            southeast_asian_langs = ['th', 'id', 'vi']
            southeast_asian_comments = [c for c in comments if c['language'] in southeast_asian_langs]
            # 5. 서구권 (영어, 프랑스어, 독일어)
            western_langs = ['en', 'fr', 'de']
            western_comments = [c for c in comments if c['language'] in western_langs]
            # 6. 라틴권 (스페인어, 포르투갈어)
            latin_langs = ['es', 'pt']
            latin_comments = [c for c in comments if c['language'] in latin_langs]
            # 기타 언어
            all_classified_langs = ['ko', 'ja'] + southeast_asian_langs + western_langs + latin_langs
            other_comments = [c for c in comments if c['language'] not in all_classified_langs and not c['language'].startswith('zh')]
            
            logger.info(f"댓글 추출 완료: 총 {len(comments)}개 (한국어: {len(korean_comments)}, 일본어: {len(japanese_comments)}, 중국어: {len(chinese_comments)}, 동남아시아: {len(southeast_asian_comments)}, 서구권: {len(western_comments)}, 라틴권: {len(latin_comments)}, 기타: {len(other_comments)})")
            
            return {
                'videoId': info.get('id'),
                'title': info.get('title'),
                'description': video_description,
                'link': video_link,
                'channelName': channel_name,
                'channelLink': channel_link,
                'views': video_views,
                'likes': video_like_count,
                'comments': total_comment_count,
                'length': video_length,
                'thumbnail': video_thumbnail,
                'upload_date': upload_date_formatted,  # 업로드 날짜 (2025-11-13 형식)
                'tags': video_tags,  # get_video_info에서 가져온 태그
                'categories': video_categories,  # get_video_info에서 가져온 카테고리
                'fetched_count': len(comments),
                'language_stats': {
                    'korean': len(korean_comments),
                    'japanese': len(japanese_comments),
                    'chinese': len(chinese_comments),
                    'southeast_asian': len(southeast_asian_comments),
                    'western': len(western_comments),
                    'latin': len(latin_comments),
                    'others': len(other_comments)
                },
                'all_comments': comments,  # 모든 댓글 (언어 정보 포함)
                'korean_comments': korean_comments,  # 한국어 댓글만
                'japanese_comments': japanese_comments,  # 일본어 댓글만
                'chinese_comments': chinese_comments,  # 중국어 댓글만
                'southeast_asian_comments': southeast_asian_comments,  # 동남아시아 댓글만
                'western_comments': western_comments,  # 서구권 댓글만
                'latin_comments': latin_comments,  # 라틴권 댓글만
                'other_comments': other_comments  # 기타 언어 댓글
            }
            
    except Exception as e:
        logger.error(f"댓글 추출 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"댓글 추출 실패: {str(e)}")

def get_subtitle_url_only(video_url: str) -> SubtitleUrlResponse:
    """자막 URL만 추출 (한국어 VTT만)"""
    logger.info(f"자막 URL 추출 시작: {video_url}")
    
    try:
        # 영상 정보 추출
        video_info = get_video_info(video_url)
        video_id = video_info.get('video_id')
        
        # 한국어 VTT 자막 URL만 필터링
        subtitle_urls = []
        target_lang = 'ko'  # 한국어만
        
        # 수동 자막에서 한국어 VTT 찾기
        if video_info.get('subtitle_urls'):
            for sub in video_info['subtitle_urls']:
                if sub.get('language') == target_lang and sub.get('ext') == 'vtt':
                    subtitle_urls.append(sub)
                    logger.info(f"한국어 VTT 자막 URL 찾음: {target_lang}")
                    break
        
        # 자동 생성 자막에서 한국어 VTT 찾기 (수동 자막이 없을 경우)
        if not subtitle_urls:
            # 다시 영상 정보를 가져와서 자동 생성 자막 확인
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                if info.get('automatic_captions') and target_lang in info['automatic_captions']:
                    subs = info['automatic_captions'][target_lang]
                    vtt_sub = next((s for s in subs if s.get('ext') == 'vtt'), None)
                    if vtt_sub:
                        subtitle_urls.append({
                            'language': target_lang,
                            'ext': 'vtt',
                            'url': vtt_sub.get('url')
                        })
                        logger.info(f"한국어 자동 생성 VTT 자막 URL 찾음: {target_lang}")
        
        logger.info(f"자막 URL 추출 완료: {video_id}, 자막 개수: {len(subtitle_urls)}")
        
        return SubtitleUrlResponse(
            video_id=video_id,
            subtitle_urls=subtitle_urls if subtitle_urls else None,
            error=None
        )
    except Exception as e:
        logger.error(f"자막 URL 추출 실패: {str(e)}")
        video_id = extract_video_id(video_url)
        return SubtitleUrlResponse(
            video_id=video_id,
            subtitle_urls=None,
            error=str(e)
        )

def extract_video_data(video_url: str, languages: List[str] = ["ko", "en"]) -> VideoResponse:
    """영상 정보 + 자막 추출"""
    logger.info(f"영상 데이터 추출 시작: {video_url}")
    
    # 1. 영상 정보 추출
    video_info = get_video_info(video_url)
    logger.info(f"영상 정보 추출 완료: {video_info['title']}")
    
    # 2. 자막 추출
    transcript_data = get_transcript(video_info['video_id'], languages)
    
    # 3. 응답 구성
    return VideoResponse(
        **video_info,
        transcript=transcript_data.get('transcript'),
        transcript_language=transcript_data.get('language_code'),
        transcript_language_name=transcript_data.get('language'),
        is_generated=transcript_data.get('is_generated'),
        snippet_count=transcript_data.get('snippet_count'),
        transcript_list=transcript_data.get('transcript_list'),
        error=transcript_data.get('error')
    )

# ===== API 엔드포인트 =====

@app.get("/")
def root():
    return {
        "service": "YouTube Video Extractor API",
        "version": "2.1",
        "status": "running",
        "features": [
            "영상 메타데이터 (조회수, 좋아요, 댓글 수, 구독자 수)",
            "자막 텍스트 추출 (타임스탬프 포함)",
            "자막 URL 제공 (VTT 우선)",
            "댓글 추출 (작성자, 내용, 좋아요 수)",
            "배치 처리 지원 (최대 50개)"
        ],
        "endpoints": {
            "POST /extract": "단일 영상 추출 (메타데이터 + 자막)",
            "POST /subtitle-url": "자막 URL만 추출 (한국어 VTT만, 가장 가벼움)",
            "GET /subtitle-url/{video_id}": "자막 URL만 추출 (GET 방식, video_id로 직접 접근)",
            "POST /transcript": "여러 영상 일괄 추출 (최대 50개)",
            "POST /comments": "댓글 추출 (언어 감지 및 분류)",
            "GET /test/{video_id}": "영상 정보 간편 테스트",
            "GET /test-subtitle-url/{video_id}": "자막 URL 간편 테스트",
            "GET /test-comments/{video_id}": "댓글 간편 테스트"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }

@app.get("/health")
def health_check():
    """헬스 체크"""
    from datetime import datetime
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.1"
    }

@app.post("/extract", response_model=VideoResponse)
def extract_single_video(request: VideoRequest):
    """
    단일 영상 정보 + 자막 추출
    
    - **video_url**: 유튜브 영상 URL
    - **languages**: 자막 언어 우선순위 (기본값: ["ko", "en"])
    """
    try:
        return extract_video_data(request.video_url, request.languages)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"영상 추출 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcript", response_model=List[VideoResponse])
def extract_batch_videos(request: BatchVideoRequest):
    """
    여러 영상 일괄 추출 (최대 50개)
    
    - **video_urls**: 유튜브 영상 URL 리스트
    - **languages**: 자막 언어 우선순위
    """
    if len(request.video_urls) > 50:
        raise HTTPException(status_code=400, detail="최대 50개까지만 처리 가능합니다")
    
    results = []
    for idx, url in enumerate(request.video_urls, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"처리 중: {idx}/{len(request.video_urls)}")
        logger.info(f"{'='*60}")
        
        try:
            result = extract_video_data(url, request.languages)
            results.append(result)
        except Exception as e:
            logger.error(f"영상 처리 실패: {url} - {str(e)}")
            results.append(VideoResponse(
                video_id=extract_video_id(url),
                title="처리 실패",
                url=url,
                error=str(e)
            ))
        
        # API 제한 방지 (0.5초 대기)
        if idx < len(request.video_urls):
            time.sleep(0.5)
    
    logger.info(f"\n배치 처리 완료: 성공 {len([r for r in results if not r.error])}/{len(results)}")
    return results

@app.post("/comments")
def extract_comments(request: CommentRequest):
    """
    댓글 추출 (인기순) + 언어 감지 및 분류
    
    - **video_url**: 유튜브 영상 URL
    - **max_comments**: 최대 댓글 수 (기본값: 100, 제한 없음)
    
    특징:
    - 인기순(좋아요 많은 순)으로 정렬
    - 언어 자동 감지 (langdetect 사용)
    - 6개 언어 그룹별로 자동 분류
    - 비디오당 100개 권장 (빠르고 의미있는 댓글 수집)
    
    반환 정보:
    - video_id: 영상 ID
    - video_title: 영상 제목
    - comment_count: 전체 댓글 수
    - like_count: 영상 좋아요 수
    - tags: 태그 목록
    - categories: 카테고리 목록
    - fetched_count: 실제 가져온 댓글 수
    - language_stats: 언어별 통계 (6개 그룹)
      - korean: 한국어
      - japanese: 일본어
      - chinese: 중국어
      - southeast_asian: 동남아시아 (태국어, 인도네시아어, 베트남어)
      - western: 서구권 (영어, 프랑스어, 독일어)
      - latin: 라틴권 (스페인어, 포르투갈어)
      - others: 기타 언어
    - all_comments: 모든 댓글 (언어 정보 포함)
    - korean_comments: 한국어 댓글만
    - japanese_comments: 일본어 댓글만
    - chinese_comments: 중국어 댓글만
    - southeast_asian_comments: 동남아시아 댓글만
    - western_comments: 서구권 댓글만
    - latin_comments: 라틴권 댓글만
    - other_comments: 기타 언어 댓글
    
    각 댓글 정보:
    - author: 작성자 이름
    - text: 댓글 내용
    - like_count: 좋아요 수 (인기순 정렬 기준)
    - time_text: 작성 시간
    - author_id: 작성자 ID
    - author_thumbnail: 작성자 프로필 이미지
    - is_favorited: 고정 댓글 여부
    - author_is_uploader: 채널 주인 댓글 여부
    - reply_count: 답글 수
    - language: 감지된 언어 코드 (ko, en, ja, es 등)
    - language_group: 언어 그룹 (korean, japanese, chinese, southeast_asian, western, latin, others)
    """
    try:
        result = get_comments(request.video_url, request.max_comments)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"댓글 추출 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test/{video_id}")
def test_video(video_id: str, languages: str = "ko,en"):
    """
    영상 정보 + 자막 테스트 (브라우저에서 접근 가능)
    
    - **video_id**: 유튜브 비디오 ID (11자리)
    - **languages**: 쉼표로 구분된 언어 코드 (기본값: "ko,en")
    
    예시: http://localhost:8000/test/H5TAW-0X7eQ
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    lang_list = [lang.strip() for lang in languages.split(",")]
    
    try:
        result = extract_video_data(url, lang_list)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"테스트 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/subtitle-url", response_model=SubtitleUrlResponse)
def get_subtitle_url(request: SubtitleUrlRequest):
    """
    자막 URL만 추출 (한국어 VTT만, 가장 가벼운 엔드포인트)
    
    - **video_url**: 유튜브 영상 URL
    
    반환:
    - video_id: 영상 ID
    - subtitle_urls: 한국어 VTT 자막 URL 리스트 (없으면 null)
    - error: 에러 메시지 (있을 경우)
    
    예시 응답:
    ```json
    {
        "video_id": "H5TAW-0X7eQ",
        "subtitle_urls": [
            {
                "language": "ko",
                "ext": "vtt",
                "url": "https://www.youtube.com/api/timedtext?..."
            }
        ],
        "error": null
    }
    ```
    """
    try:
        # 차단 방지를 위한 최소 대기 시간
        time.sleep(0.5)
        return get_subtitle_url_only(request.video_url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"자막 URL 추출 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/subtitle-url/{video_id}", response_model=SubtitleUrlResponse)
def get_subtitle_url_by_id(video_id: str):
    """
    자막 URL만 추출 (GET 방식, video_id로 직접 접근)
    
    - **video_id**: 유튜브 비디오 ID (11자리)
    
    반환:
    - video_id: 영상 ID
    - subtitle_urls: 한국어 VTT 자막 URL 리스트
    - error: 에러 메시지 (있을 경우)
    
    예시: http://localhost:8000/subtitle-url/H5TAW-0X7eQ
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        # 차단 방지를 위한 최소 대기 시간
        time.sleep(0.5)
        return get_subtitle_url_only(url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"자막 URL 추출 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-subtitle-url/{video_id}")
def test_subtitle_url(video_id: str):
    """
    자막 URL 테스트 (브라우저에서 접근 가능)
    
    - **video_id**: 유튜브 비디오 ID (11자리)
    
    예시: http://localhost:8000/test-subtitle-url/H5TAW-0X7eQ
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        result = get_subtitle_url_only(url)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"자막 URL 테스트 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-comments/{video_id}")
def test_comments(video_id: str, max_comments: int = 100):
    """
    댓글 테스트 (브라우저에서 접근 가능)
    
    - **video_id**: 유튜브 비디오 ID (11자리)
    - **max_comments**: 최대 댓글 수 (기본값: 100)
    
    예시: 
    - http://localhost:8000/test-comments/H5TAW-0X7eQ
    - http://localhost:8000/test-comments/H5TAW-0X7eQ?max_comments=50
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        result = get_comments(url, max_comments)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"댓글 테스트 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    logger.info("YouTube Video Extractor API v2.1 시작...")
    logger.info("자막 텍스트 + 자막 URL + 댓글 제공 (언어 감지)")
    logger.info("엔드포인트:")
    logger.info("  - POST /subtitle-url (자막 URL만, 한국어 VTT)")
    logger.info("  - POST /extract (단일 영상, 메타데이터 + 자막)")
    logger.info("  - POST /transcript (여러개 일괄 처리)")
    logger.info("  - POST /comments (댓글 추출, 언어 감지 및 분류)")
    logger.info("테스트:")
    logger.info("  - GET /test-subtitle-url/{id} (자막 URL만)")
    logger.info("  - GET /test/{id} (영상 정보)")
    logger.info("  - GET /test-comments/{id} (댓글)")
    uvicorn.run(app, host="0.0.0.0", port=8000)