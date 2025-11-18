"""
YouTube 영상 정보 + 자막 추출 API
- 자막: youtube-transcript-api 우선 사용 (간단하고 안정적)
- 폴백: yt-dlp 사용 (클라우드 환경 또는 youtube-transcript-api 실패 시)
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import yt_dlp
import requests
import logging
import time
import re
import os
import csv
import io
import json
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# youtube-transcript-api (자막 추출용)
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        TranscriptsDisabled,
        NoTranscriptFound,
        VideoUnavailable
    )
    YOUTUBE_TRANSCRIPT_AVAILABLE = True
    logger.info("youtube-transcript-api 사용 가능 (자막 추출 우선 사용)")
except ImportError:
    YOUTUBE_TRANSCRIPT_AVAILABLE = False
    logger.warning("youtube-transcript-api를 사용할 수 없습니다. yt-dlp만 사용합니다.")

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
    languages: Optional[List[str]] = ["ko"]  # 기본값: 한국어만

class BatchVideoRequest(BaseModel):
    video_urls: List[str]
    languages: Optional[List[str]] = ["ko"]  # 기본값: 한국어만

class CommentRequest(BaseModel):
    video_url: str
    max_comments: Optional[int] = 100  # 기본 100개

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

def get_ydl_opts_base() -> dict:
    """
    yt-dlp 기본 옵션 (봇 감지 방지)
    환경 변수 YOUTUBE_COOKIES_FILE이 설정되어 있으면 쿠키 사용
    """
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'http_headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Referer': 'https://www.youtube.com/',
            'Origin': 'https://www.youtube.com'
        },
        'retries': 3,
        'fragment_retries': 3,
        'socket_timeout': 30,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web', 'mweb'],  # 여러 클라이언트 시도
                'player_skip': ['webpage'],  # 웹페이지 파싱 스킵
            }
        },
        'extractor_retries': 3,  # 추출기 재시도
        'no_check_certificate': False,
        'prefer_insecure': False,
    }
    
    # 환경 변수에서 쿠키 파일 경로 확인
    cookies_file = os.getenv('YOUTUBE_COOKIES_FILE')
    if cookies_file and os.path.exists(cookies_file):
        opts['cookiefile'] = cookies_file
        logger.info(f"쿠키 파일 사용: {cookies_file}")
    
    return opts

def extract_video_id(url: str) -> str:
    """URL에서 video_id 추출"""
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    elif "watch?v=" in url:
        return url.split("watch?v=")[1].split("&")[0]
    else:
        return url

def get_video_info(video_url: str, max_retries: int = 3) -> Dict[str, Any]:
    """
    yt-dlp로 영상 정보 추출
    봇 감지 오류 시 재시도
    """
    for attempt in range(max_retries):
        try:
            ydl_opts = get_ydl_opts_base()
            ydl_opts.update({
                'writesubtitles': True,  # 자막 정보 포함
                'writeautomaticsub': True,  # 자동 자막 정보 포함
            })
            
            # 재시도 시 딜레이
            if attempt > 0:
                wait_time = min(2 ** attempt, 10)
                logger.info(f"영상 정보 추출 재시도 {attempt}/{max_retries-1} - {wait_time}초 대기...")
                time.sleep(wait_time)
    
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
            
            result = {
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
            return result
                
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            logger.warning(f"영상 정보 추출 오류 (시도 {attempt+1}/{max_retries}): {error_msg}")
            
            # 봇 감지 오류 또는 429 오류 감지
            if any(keyword in error_msg.lower() for keyword in ['bot', 'sign in', 'cookies', '429', 'too many requests', 'rate limit', 'precondition']):
                if attempt < max_retries - 1:
                    continue  # 재시도
                else:
                    logger.error(f"영상 정보 추출 실패: 최대 재시도 횟수 초과")
                    if 'bot' in error_msg.lower() or 'sign in' in error_msg.lower():
                        raise HTTPException(
                            status_code=403,
                            detail="YouTube 봇 감지로 인해 접근이 제한되었습니다. 쿠키 파일을 사용하거나 잠시 후 다시 시도해주세요."
                        )
                    else:
                        raise HTTPException(
                            status_code=429,
                            detail="YouTube에서 요청을 제한했습니다. 잠시 후 다시 시도해주세요."
                        )
            elif "failed to extract" in error_msg.lower() or "player response" in error_msg.lower():
                # yt-dlp 파싱 오류 - YouTube 봇 감지 가능성
                if attempt < max_retries - 1:
                    logger.warning(f"Player response 추출 실패, 재시도 중... (시도 {attempt+1}/{max_retries})")
                    continue
                else:
                    # 쿠키 파일 사용 권장 메시지
                    cookies_file = os.getenv('YOUTUBE_COOKIES_FILE')
                    if not cookies_file:
                        detail_msg = "YouTube 데이터 추출에 실패했습니다. YouTube 봇 감지로 인한 차단일 수 있습니다. 쿠키 파일을 사용하거나 잠시 후 다시 시도해주세요. (쿠키 파일 설정: YOUTUBE_COOKIES_FILE 환경 변수)"
                    else:
                        detail_msg = "YouTube 데이터 추출에 실패했습니다. 쿠키 파일을 사용 중이지만 여전히 차단되었습니다. 쿠키 파일을 갱신하거나 잠시 후 다시 시도해주세요."
                    raise HTTPException(
                        status_code=500,
                        detail=detail_msg
                    )
            elif "Video unavailable" in error_msg:
                raise HTTPException(status_code=404, detail="영상을 찾을 수 없거나 접근이 제한되었습니다.")
            else:
                # 다른 오류는 즉시 실패
                raise HTTPException(status_code=400, detail=f"영상 정보를 가져올 수 없습니다: {error_msg}")
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"영상 정보 추출 오류: {type(e).__name__} - {error_msg}")
            
            # 봇 감지 관련 오류인지 확인
            if any(keyword in error_msg.lower() for keyword in ['bot', 'sign in', 'cookies']):
                if attempt < max_retries - 1:
                    continue  # 재시도
                else:
                    raise HTTPException(
                        status_code=403,
                        detail="YouTube 봇 감지로 인해 접근이 제한되었습니다. 쿠키 파일을 사용하거나 잠시 후 다시 시도해주세요."
                    )
            else:
                raise HTTPException(status_code=500, detail=f"서버 오류: {error_msg}")
    
    # 모든 재시도 실패
    logger.error(f"영상 정보 추출 실패: 최대 재시도 횟수({max_retries}) 초과")
    raise HTTPException(
        status_code=403,
        detail="YouTube 봇 감지로 인해 접근이 제한되었습니다. 쿠키 파일을 사용하거나 잠시 후 다시 시도해주세요."
    )

def get_transcript(video_id: str, languages: List[str] = ["ko"]) -> Dict[str, Any]:
    """
    자막 추출 (youtube-transcript-api 우선, 실패 시 yt-dlp 사용)
    
    전략:
    1. youtube-transcript-api 시도 (간단하고 안정적, 로컬에서 잘 작동)
    2. 실패 시 yt-dlp 사용 (클라우드 환경 또는 봇 감지 시)
    """
    logger.info(f"자막 추출 시도: {video_id}, 선호 언어: {languages}")
    
    # 1. youtube-transcript-api 시도 (우선)
    if YOUTUBE_TRANSCRIPT_AVAILABLE:
        try:
            logger.info("youtube-transcript-api로 자막 추출 시도...")
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(video_id)
            
            # 원하는 언어의 자막 찾기
            transcript = transcript_list.find_transcript(languages)
            fetched_transcript = transcript.fetch()
            
            # 자막 텍스트 결합
            full_text = " ".join([snippet.text for snippet in fetched_transcript])
            
            # transcript_list 변환 (타임스탬프 포함)
            transcript_with_time = [
                {
                    'text': snippet.text,
                    'start': snippet.start,
                    'duration': snippet.duration
                }
                for snippet in fetched_transcript
            ]
            
            logger.info(f"자막 추출 성공 (youtube-transcript-api): {transcript.language} ({transcript.language_code}), {len(fetched_transcript)}개 구간")
            
            return {
                'transcript': full_text,
                'language': transcript.language,
                'language_code': transcript.language_code,
                'is_generated': transcript.is_generated,
                'snippet_count': len(fetched_transcript),
                'transcript_list': transcript_with_time
            }
            
        except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as e:
            logger.warning(f"youtube-transcript-api 실패: {type(e).__name__}, yt-dlp로 폴백...")
            # yt-dlp로 폴백
        except Exception as e:
            logger.warning(f"youtube-transcript-api 오류: {str(e)}, yt-dlp로 폴백...")
            # yt-dlp로 폴백
    
    # 2. yt-dlp로 폴백 (클라우드 환경 또는 youtube-transcript-api 실패 시)
    logger.info("yt-dlp로 자막 추출 시도...")
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = get_ydl_opts_base()
    ydl_opts.update({
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': languages,
        'subtitlesformat': 'vtt',  # VTT 형식으로 받기
    })
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            # 자막 데이터 추출
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            
            # 사용 가능한 자막 언어 로그
            available_langs = list(subtitles.keys()) + list(automatic_captions.keys())
            logger.info(f"사용 가능한 자막: {', '.join(set(available_langs))}")
            
            # 선호 언어 순서대로 확인
            for lang in languages:
                # 1. 수동 자막 우선
                if lang in subtitles:
                    subtitle_data = subtitles[lang]
                    for sub in subtitle_data:
                        if 'vtt' in sub.get('ext', ''):
                            # 429 오류 방지를 위한 딜레이
                            time.sleep(0.5)
                            result = download_subtitle_vtt(sub['url'])
                            if result:
                                logger.info(f"자막 추출 성공 (yt-dlp): {lang} (수동 자막), {len(result['transcript'])}자, {result['snippet_count']}개 구간")
                                result['language'] = lang
                                result['language_code'] = lang
                                result['is_generated'] = False
                                return result
                
                # 2. 자동 생성 자막
                if lang in automatic_captions:
                    caption_data = automatic_captions[lang]
                    for cap in caption_data:
                        if 'vtt' in cap.get('ext', ''):
                            # 429 오류 방지를 위한 딜레이 (더 길게)
                            time.sleep(1.0)  # 0.5초 → 1초로 증가
                            result = download_subtitle_vtt(cap['url'])
                            if result:
                                logger.info(f"자막 추출 성공 (yt-dlp): {lang} (자동 생성), {len(result['transcript'])}자, {result['snippet_count']}개 구간")
                                result['language'] = lang
                                result['language_code'] = lang
                                result['is_generated'] = True
                                return result
            
            logger.warning(f"요청한 언어의 자막을 찾을 수 없음: {languages}")
            return {'transcript': None, 'language': None, 'language_code': None, 'error': '자막 없음'}
            
    except Exception as e:
        logger.error(f"자막 추출 오류 (yt-dlp): {type(e).__name__} - {str(e)}")
        return {'transcript': None, 'language': None, 'language_code': None, 'error': str(e)}


def download_subtitle_vtt(url: str, max_retries: int = 3) -> dict:
    """
    VTT 형식의 자막 URL에서 텍스트 및 타임스탬프 추출
    429 오류 시 exponential backoff로 재시도
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/vtt, text/plain, */*',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.youtube.com/',
        'Origin': 'https://www.youtube.com'
    }
    
    for attempt in range(max_retries):
        try:
            # 재시도 시 딜레이 (exponential backoff)
            if attempt > 0:
                wait_time = min(2 ** attempt, 10)  # 최대 10초
                logger.info(f"429 오류 재시도 {attempt}/{max_retries-1} - {wait_time}초 대기...")
                time.sleep(wait_time)
            
            response = requests.get(url, headers=headers, timeout=15)
            
            # 429 오류 처리
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    continue  # 재시도
                else:
                    logger.error(f"429 오류: 최대 재시도 횟수 초과")
                    return None
            
            response.raise_for_status()
            
            vtt_content = response.text
            
            # VTT 파싱
            texts = []
            transcript_list = []
            lines = vtt_content.split('\n')
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # 타임스탬프 라인 찾기 (00:00:00.000 --> 00:00:02.000)
                if '-->' in line:
                    try:
                        # 타임스탬프 파싱
                        time_parts = line.split('-->')
                        start_time_str = time_parts[0].strip().split(' ')[0]  # align 제거
                        end_time_str = time_parts[1].strip().split(' ')[0]
                        
                        # 시간을 초로 변환
                        start_seconds = parse_vtt_time(start_time_str)
                        end_seconds = parse_vtt_time(end_time_str)
                        duration = end_seconds - start_seconds
                        
                        # 다음 라인들에서 자막 텍스트 추출
                        i += 1
                        subtitle_text = []
                        while i < len(lines) and lines[i].strip() and '-->' not in lines[i]:
                            text = lines[i].strip()
                            # HTML 태그 제거 (예: <c> 태그)
                            text = remove_vtt_tags(text)
                            if text:
                                subtitle_text.append(text)
                            i += 1
                        
                        if subtitle_text:
                            full_text = ' '.join(subtitle_text)
                            texts.append(full_text)
                            transcript_list.append({
                                'text': full_text,
                                'start': start_seconds,
                                'duration': duration
                            })
                    except Exception as e:
                        logger.warning(f"VTT 라인 파싱 실패: {line} - {str(e)}")
                        i += 1
                else:
                    i += 1
            
            return {
                'transcript': " ".join(texts),
                'snippet_count': len(transcript_list),
                'transcript_list': transcript_list
            }
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                if attempt < max_retries - 1:
                    continue  # 재시도
                else:
                    logger.error(f"VTT 다운로드 오류 (429): 최대 재시도 횟수 초과")
                    return None
            else:
                logger.error(f"VTT 다운로드 HTTP 오류: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"VTT 다운로드 오류: {str(e)}")
            return None
    
    # 모든 재시도 실패
    logger.error(f"VTT 다운로드 실패: 최대 재시도 횟수({max_retries}) 초과")
    return None


def parse_vtt_time(time_str: str) -> float:
    """VTT 시간 형식을 초로 변환 (00:00:00.000)"""
    try:
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    except:
        return 0.0


def remove_vtt_tags(text: str) -> str:
    """VTT 태그 제거 (예: <c>, <00:00:01.234> 등)"""
    # <00:00:01.234> 형식의 타임스탬프 제거
    text = re.sub(r'<\d+:\d+:\d+\.\d+>', '', text)
    # <c> 태그 제거
    text = re.sub(r'</?c[^>]*>', '', text)
    # 기타 HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def get_comments(video_url: str, max_comments: int = 100) -> Dict[str, Any]:
    """yt-dlp로 댓글 추출 (인기순)"""
    
    ydl_opts = get_ydl_opts_base()
    ydl_opts.update({
        'getcomments': True,  # 댓글 가져오기
        'extractor_args': {
            'youtube': {
                'max_comments': [str(max_comments)],
                'comment_sort': ['top']  # 인기순 정렬
            }
        },
    })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"댓글 추출 중: {video_url} (최대 {max_comments}개)")
            
            info = ydl.extract_info(video_url, download=False)
            
            comments = []
            
            if info.get('comments'):
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
            
            logger.info(f"댓글 추출 완료: {len(comments)}개")
            
            return {
                'video_id': info.get('id'),
                'video_title': info.get('title'),
                'comment_count': info.get('comment_count', 0),
                'comments': comments,
                'fetched_count': len(comments)
            }
            
    except Exception as e:
        logger.error(f"댓글 추출 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"댓글 추출 실패: {str(e)}")

def extract_video_data(video_url: str, languages: List[str] = ["ko"]) -> VideoResponse:
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
            "배치 처리 지원 (최대 200개)",
            "CSV 파일 업로드 지원"
        ],
        "endpoints": {
            "POST /extract": "단일 영상 추출 (메타데이터 + 자막)",
            "POST /transcript": "여러 영상 일괄 추출 (최대 200개)",
            "POST /transcript/csv": "CSV 파일에서 URL 읽어 일괄 추출 (최대 200개)",
            "POST /transcript/csv-save": "CSV 파일에서 URL 읽어 추출 후 파일로 다운로드 (JSON/CSV)",
            "POST /comments": "댓글 추출 (최대 지정 개수)",
            "GET /test/{video_id}": "영상 정보 간편 테스트",
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
        
        # API 제한 방지 (429 오류 대응 - 더 긴 딜레이)
        if idx < len(request.video_urls):
            # 100개 이상: 5초, 50개 이상: 3초, 그 외: 2초 대기
            if len(request.video_urls) >= 100:
                delay = 5.0  # 100개 이상은 5초 대기 (429 오류 방지)
            elif len(request.video_urls) > 50:
                delay = 3.0
            else:
                delay = 2.0
            time.sleep(delay)
    
    logger.info(f"\n배치 처리 완료: 성공 {len([r for r in results if not r.error])}/{len(results)}")
    return results

@app.post("/transcript/csv", response_model=List[VideoResponse])
async def extract_batch_from_csv(
    file: UploadFile = File(...),
    languages: Optional[str] = "ko,en"
):
    """
    CSV 파일에서 URL을 읽어 일괄 추출 (최대 200개)
    
    CSV 형식:
    - 첫 번째 컬럼이 URL 또는 video_id
    - 헤더 행은 자동으로 건너뜀
    
    예시 CSV:
    ```
    url
    https://www.youtube.com/watch?v=VIDEO_ID_1
    https://www.youtube.com/watch?v=VIDEO_ID_2
    VIDEO_ID_3
    ```
    
    주의사항:
    - 100개 처리 시 약 5분 소요 (영상당 3초 대기)
    - youtube-transcript-api 사용 시 봇 감지 가능성 낮음 (로컬 IP)
    - 클라우드 환경에서는 yt-dlp로 자동 폴백
    """
    try:
        # CSV 파일 읽기
        contents = await file.read()
        csv_content = contents.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(csv_content))
        
        # URL 추출
        urls = []
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
        
        if not urls:
            raise HTTPException(status_code=400, detail="CSV 파일에서 유효한 URL을 찾을 수 없습니다.")
        
        if len(urls) > 200:
            raise HTTPException(status_code=400, detail=f"최대 200개까지만 처리 가능합니다. 현재 {len(urls)}개입니다.")
        
        logger.info(f"CSV 파일에서 {len(urls)}개 URL 추출")
        
        # 언어 파싱
        lang_list = [lang.strip() for lang in languages.split(",")] if languages else ["ko", "en"]
        
        # 배치 처리
        results = []
        for idx, url in enumerate(urls, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"처리 중: {idx}/{len(urls)}")
            logger.info(f"{'='*60}")
            
            try:
                result = extract_video_data(url, lang_list)
                results.append(result)
            except Exception as e:
                logger.error(f"영상 처리 실패: {url} - {str(e)}")
                results.append(VideoResponse(
                    video_id=extract_video_id(url),
                    title="처리 실패",
                    url=url,
                    error=str(e)
                ))
            
            # API 제한 방지 (대량 처리 시 더 긴 딜레이)
            if idx < len(urls):
                # 100개 이상: 3초, 50개 이상: 2초, 그 외: 1초 대기
                if len(urls) >= 100:
                    delay = 3.0  # 100개 이상은 3초 대기 (봇 감지 방지)
                elif len(urls) > 50:
                    delay = 2.0
                else:
                    delay = 1.0
                time.sleep(delay)
        
        logger.info(f"\nCSV 배치 처리 완료: 성공 {len([r for r in results if not r.error])}/{len(results)}")
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV 파일 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"CSV 파일 처리 실패: {str(e)}")

@app.post("/transcript/csv-save")
async def extract_batch_from_csv_and_save(
    file: UploadFile = File(...),
    languages: Optional[str] = "ko,en",
    format: Optional[str] = "json"  # json 또는 csv
):
    """
    CSV 파일에서 URL을 읽어 일괄 추출 후 파일로 저장
    
    - **file**: CSV 파일 (URL 목록)
    - **languages**: 언어 코드 (쉼표로 구분, 기본값: "ko,en")
    - **format**: 저장 형식 ("json" 또는 "csv", 기본값: "json")
    
    반환: 추출된 데이터가 포함된 파일 다운로드
    """
    try:
        # CSV 파일 읽기
        contents = await file.read()
        csv_content = contents.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(csv_content))
        
        # URL 추출
        urls = []
        for row_idx, row in enumerate(csv_reader):
            if row_idx == 0:
                continue
            if row and len(row) > 0:
                url = row[0].strip()
                if url and ('youtube.com' in url or 'youtu.be' in url or len(url) == 11):
                    if not url.startswith('http'):
                        url = f"https://www.youtube.com/watch?v={url}"
                    urls.append(url)
        
        if not urls:
            raise HTTPException(status_code=400, detail="CSV 파일에서 유효한 URL을 찾을 수 없습니다.")
        
        if len(urls) > 200:
            raise HTTPException(status_code=400, detail=f"최대 200개까지만 처리 가능합니다. 현재 {len(urls)}개입니다.")
        
        logger.info(f"CSV 파일에서 {len(urls)}개 URL 추출")
        
        # 언어 파싱
        lang_list = [lang.strip() for lang in languages.split(",")] if languages else ["ko", "en"]
        
        # 배치 처리
        results = []
        for idx, url in enumerate(urls, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"처리 중: {idx}/{len(urls)}")
            logger.info(f"{'='*60}")
            
            try:
                result = extract_video_data(url, lang_list)
                results.append(result)
            except Exception as e:
                logger.error(f"영상 처리 실패: {url} - {str(e)}")
                results.append(VideoResponse(
                    video_id=extract_video_id(url),
                    title="처리 실패",
                    url=url,
                    error=str(e)
                ))
            
            # API 제한 방지 (429 오류 대응 - 더 긴 딜레이)
            if idx < len(urls):
                if len(urls) >= 100:
                    delay = 5.0  # 100개 이상: 5초 대기 (429 오류 방지)
                elif len(urls) > 50:
                    delay = 3.0
                else:
                    delay = 2.0
                time.sleep(delay)
        
        logger.info(f"\nCSV 배치 처리 완료: 성공 {len([r for r in results if not r.error])}/{len(results)}")
        
        # 파일로 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format.lower() == "csv":
            # CSV 형식으로 저장
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 헤더 작성
            writer.writerow([
                'video_id', 'title', 'url', 'view_count', 'like_count', 'comment_count',
                'channel', 'channel_follower_count', 'upload_date', 'duration_string',
                'transcript', 'transcript_language', 'transcript_snippet_count'
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
                    result.snippet_count
                ])
            
            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8-sig')),  # BOM 추가 (Excel 호환)
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=youtube_extract_{timestamp}.csv"
                }
            )
        else:
            # JSON 형식으로 저장
            json_data = json.dumps([result.dict() for result in results], ensure_ascii=False, indent=2)
            return Response(
                content=json_data.encode('utf-8'),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=youtube_extract_{timestamp}.json"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV 파일 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"CSV 파일 처리 실패: {str(e)}")

@app.post("/comments")
def extract_comments(request: CommentRequest):
    """
    댓글 추출 (인기순)
    
    - **video_url**: 유튜브 영상 URL
    - **max_comments**: 최대 댓글 수 (기본값: 100, 제한 없음)
    
    특징:
    - 인기순(좋아요 많은 순)으로 정렬
    - 비디오당 100개 권장 (빠르고 의미있는 댓글 수집)
    - 배치 처리로 여러 영상 동시 수집 가능
    
    반환 정보:
    - author: 작성자 이름
    - text: 댓글 내용
    - like_count: 좋아요 수 (인기순 정렬 기준)
    - time_text: 작성 시간
    - author_id: 작성자 ID
    - author_thumbnail: 작성자 프로필 이미지
    - is_favorited: 고정 댓글 여부
    - author_is_uploader: 채널 주인 댓글 여부
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
    logger.info("자막 텍스트 + 자막 URL + 댓글 제공")
    logger.info("엔드포인트: /extract (단일), /transcript (여러개), /comments (댓글)")
    logger.info("테스트: /test/{id} (영상), /test-comments/{id} (댓글)")
    uvicorn.run(app, host="0.0.0.0", port=8000)