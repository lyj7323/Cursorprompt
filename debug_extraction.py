#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cursor 프롬프트 추출 모듈

Cursor 에디터의 프롬프트 데이터를 추출하고 엑셀 파일로 저장하는 기능을 제공합니다.
"""

import os
import sqlite3
import json
import logging
import hashlib
import traceback
from datetime import datetime, timedelta
import pandas as pd
import re
import shutil

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('CursorLogsExtractor')

# 기본 경로 설정
HOME_DIR = os.path.expanduser("~")
WORKSPACE_PATH = os.path.join(HOME_DIR, "Library", "Application Support", "Cursor", "User", "workspaceStorage")
STATE_DB_FILE = "state.vscdb"
SAVE_PATH = os.path.join(HOME_DIR, "Desktop", "RYJ", "saveprompt")

# 프롬프트 처리 기록 파일
PROCESSED_PROMPTS_FILE = "processed_prompts.json"

def extract_timestamp_from_data(data, db_mod_time=None):
    """
    데이터에서 타임스탬프를 추출합니다. 항상 데이터베이스 파일의 수정 시간을 사용합니다.
    
    Args:
        data (dict): 추출할 데이터 객체
        db_mod_time (float, optional): 데이터베이스 파일의 수정 시간 타임스탬프
    
    Returns:
        tuple: (추출된 타임스탬프, 타임스탬프 출처)
    """
    # 데이터베이스 수정 시간이 제공되면 항상 이 시간을 사용
    if db_mod_time:
        return datetime.fromtimestamp(db_mod_time), 'DB_MOD_TIME'
    
    # 데이터베이스 수정 시간이 없는 경우 현재 시간 사용 (폴백)
    return datetime.now(), 'CURRENT_TIME'

def load_processed_prompts(save_path=SAVE_PATH):
    """
    이전에 처리된 프롬프트 ID와 타임스탬프 목록을 로드
    
    Args:
        save_path (str): 저장 경로
    
    Returns:
        dict: 프롬프트 ID를 키로 하고 값으로 첫 발견 시간을 갖는 딕셔너리
    """
    processed_file = os.path.join(save_path, PROCESSED_PROMPTS_FILE)
    if os.path.exists(processed_file):
        try:
            with open(processed_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"처리된 프롬프트 목록 로드 중 오류 발생: {str(e)}")
            # 파일이 손상되었으면 백업 후 새로 시작
            if os.path.exists(processed_file):
                backup_file = f"{processed_file}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
                os.rename(processed_file, backup_file)
                logger.info(f"손상된 processed_prompts.json 파일을 백업했습니다: {backup_file}")
    return {}  # 파일이 없거나 오류 발생 시 빈 딕셔너리 반환

def save_processed_prompts(processed_prompts, save_path=SAVE_PATH):
    """
    처리된 프롬프트 ID와 타임스탬프 목록을 저장
    
    Args:
        processed_prompts (dict): 프롬프트 ID를 키로 하고 값으로 첫 발견 시간을 갖는 딕셔너리
        save_path (str): 저장 경로
    """
    os.makedirs(save_path, exist_ok=True)
    processed_file = os.path.join(save_path, PROCESSED_PROMPTS_FILE)
    try:
        with open(processed_file, 'w', encoding='utf-8') as f:
            json.dump(processed_prompts, f, ensure_ascii=False, indent=2)
        logger.info(f"처리된 프롬프트 목록 저장 완료: {len(processed_prompts)}개")
    except Exception as e:
        logger.error(f"처리된 프롬프트 목록 저장 중 오류 발생: {str(e)}")
        # 오류 발생 시 백업 생성
        if os.path.exists(processed_file):
            try:
                backup_file = f"{processed_file}.error.{datetime.now().strftime('%Y%m%d%H%M%S')}"
                os.rename(processed_file, backup_file)
                logger.info(f"저장 중 오류가 발생한 파일을 백업했습니다: {backup_file}")
            except Exception as bkp_err:
                logger.error(f"백업 생성 중 오류 발생: {str(bkp_err)}")

def is_file_path(text):
    """
    텍스트가 파일 경로인지 확인
    
    Args:
        text (str): 확인할 텍스트
    
    Returns:
        bool: 파일 경로이면 True, 아니면 False
    """
    # 파일 경로 패턴 (예: /path/to/file.ext 또는 C:\path\to\file.ext)
    file_path_pattern = r'^(?:/[^/\n]+)+/?$|^[a-zA-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*$'
    
    # 파일 확장자를 가진 경우 추가 체크
    has_extension = re.search(r'\.[a-zA-Z0-9]+$', text)
    
    return bool(re.match(file_path_pattern, text) or has_extension)

def find_today_folders(workspace_path=WORKSPACE_PATH):
    """
    주어진 경로에서 오늘 수정된 폴더 목록 찾기
    
    Args:
        workspace_path (str): 탐색할 기본 경로
    
    Returns:
        list: 오늘 수정된 폴더 목록
    """
    logger.info(f"Cursor 데이터 경로 검색: {workspace_path}")
    today_folders = []
    
    try:
        for item in os.listdir(workspace_path):
            item_path = os.path.join(workspace_path, item)
            
            # 폴더인지 확인
            if os.path.isdir(item_path):
                # state.vscdb 파일 확인
                db_path = os.path.join(item_path, STATE_DB_FILE)
                
                if os.path.exists(db_path):
                    # 일단 모든 폴더 포함 (최종 필터링은 나중에)
                    logger.info(f"오늘 수정된 폴더 발견: {item}")
                    today_folders.append(item_path)
    except Exception as e:
        logger.error(f"폴더 탐색 중 오류 발생: {str(e)}")
    
    logger.info(f"오늘 수정된 폴더 {len(today_folders)}개 발견")
    return today_folders

def extract_project_name(folder_path, db_path):
    """
    폴더 경로에서 프로젝트 이름을 추출합니다.
    
    Args:
        folder_path (str): 폴더 경로
        db_path (str): 데이터베이스 파일 경로
    
    Returns:
        str: 프로젝트 이름
    """
    try:
        # 연결 시도
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # debug.selectedroot에서 프로젝트 경로 추출
        cursor.execute("SELECT value FROM ItemTable WHERE key = 'debug.selectedroot'")
        result = cursor.fetchone()
        
        if result:
            project_path = result[0]
            logger.info(f"[{os.path.basename(folder_path)}] debug.selectedroot에서 프로젝트명 추출: {os.path.basename(project_path)}")
            
            # URL 인코딩된 경로 디코딩
            try:
                import urllib.parse
                project_path = urllib.parse.unquote(project_path)
            except Exception as e:
                logger.error(f"URL 디코딩 실패: {e}")
            
            # file:/// 형식 처리
            if project_path.startswith("file:///"):
                project_path = project_path[8:]
            
            # .vscode/launch.json 형식 처리
            if project_path.endswith(".vscode/launch.json"):
                # .vscode/launch.json을 제외한 경로 추출
                project_path = project_path.replace("/.vscode/launch.json", "")
            
            # 프로젝트 이름 추출 (디렉토리명 사용)
            project_name = os.path.basename(project_path)
            
            if not project_name or project_name == "launch.json" or project_name == "settings.json":
                # editor.state에서 프로젝트 이름 추출 시도
                cursor.execute("SELECT value FROM ItemTable WHERE key = 'memento/editorpart'")
                result = cursor.fetchone()
                if result:
                    editor_state = result[0]
                    # 열린 파일 경로에서 프로젝트 이름 추출 시도
                    for path_match in re.finditer(r'"resource":{"path":"([^"]+)"', editor_state):
                        file_path = path_match.group(1)
                        if file_path:
                            parts = file_path.split('/')
                            if len(parts) > 1:
                                project_name = parts[1]  # 첫 번째 디렉토리 이름
                                break
            
            # 특수 문자 처리
            if project_name:
                project_name = re.sub(r'[^\w\d가-힣\s_-]', '_', project_name)
                logger.info(f"[{os.path.basename(folder_path)}] 정리된 프로젝트명: {project_name}")
                return project_name
    except Exception as e:
        logger.error(f"프로젝트명 추출 오류: {e}")
    
    # 실패시 폴더명 사용
    logger.info(f"[{os.path.basename(folder_path)}] 프로젝트명을 찾지 못해 폴더명 사용: {os.path.basename(folder_path)}")
    return os.path.basename(folder_path)

def process_database(folder_path):
    """
    데이터베이스 파일을 처리하여 프롬프트 추출
    
    Args:
        folder_path (str): 처리할 폴더 경로
        
    Returns:
        tuple: (프로젝트명, 데이터 목록)
    """
    folder_name = os.path.basename(folder_path)
    logger.info(f"[{folder_name}] 데이터베이스 연결 성공")
    logger.info(f"[{folder_name}] 데이터베이스 분석 시작")
    
    # 결과 저장
    results = []
    
    try:
        # 데이터베이스 파일 경로
        db_path = os.path.join(folder_path, STATE_DB_FILE)
        
        # DB 파일 수정 시간 (항상 이것만 사용)
        db_mod_time = os.path.getmtime(db_path)
        
        # 프로젝트 이름 추출
        project_name = extract_project_name(folder_path, db_path)
        
        # SQLite 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블 목록 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"[{folder_name}] 테이블 목록: {tables}")
        
        # 1. 프롬프트 데이터 추출
        cursor.execute("SELECT value FROM ItemTable WHERE key = 'aiService.prompts'")
        row = cursor.fetchone()
        
        prompts_data = []
        if row and row[0]:
            try:
                prompts_data = json.loads(row[0])
                logger.info(f"[{folder_name}] 프롬프트 개수: {len(prompts_data)}")
            except json.JSONDecodeError as e:
                logger.error(f"프롬프트 데이터 파싱 오류: {e}")
        
        # 프롬프트 데이터가 없으면 빈 리스트 반환
        if not prompts_data:
            logger.warning(f"[{folder_name}] 프롬프트 데이터가 없거나 비어있습니다.")
            return project_name, []
            
        logger.info(f"첫번째 프롬프트 예시: {str(prompts_data[0])[:200]}...")
        
        # 오늘 날짜 계산
        today = datetime.now().strftime('%Y%m%d')
        logger.info(f"오늘 날짜: {today}")
        
        # 처리된 프롬프트 목록 로드
        processed_prompts = load_processed_prompts()
        logger.info(f"이미 처리된 프롬프트 ID 수: {len(processed_prompts)}")
        
        # 새로 처리된 ID 수 카운트
        new_processed_count = 0
        
        # 프롬프트 데이터 처리
        for prompt in prompts_data:
            if not isinstance(prompt, dict):
                logger.warning(f"프롬프트 데이터가 딕셔너리가 아닙니다: {type(prompt)}")
                continue
            
            # text 필드가 없으면 건너뛰기
            if 'text' not in prompt:
                logger.warning(f"프롬프트에 text 필드가 없습니다: {str(prompt)[:100]}...")
                continue
            
            # 프롬프트 텍스트 추출 및 ID 생성 (텍스트 기반)
            prompt_text = prompt.get('text', '')
            
            # 항상 MD5 해시 기반으로 ID 생성
            prompt_id = hashlib.md5(prompt_text.encode()).hexdigest()
            logger.info(f"프롬프트 ID 생성: {prompt_id[:8]}... (텍스트 MD5 해시)")
                
            # 이미 처리된 프롬프트는 건너뛰기
            if prompt_id in processed_prompts:
                processed_date = processed_prompts[prompt_id]
                logger.info(f"이미 처리된 프롬프트 건너뛰기: {prompt_id[:8]}... (처리일: {processed_date})")
                continue
            
            # 날짜/시간 정보 추출 (DB 파일 수정 시간 사용)
            db_timestamp, _ = extract_timestamp_from_data(None, db_mod_time)
            db_date_time = db_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            date_str = db_date_time.split()[0]
            time_str = db_date_time.split()[1]
            
            # DB 날짜가 오늘인지만 확인 (어제 데이터 필터링)
            db_date = date_str.replace('-', '')
            if db_date != today:
                logger.info(f"프롬프트 날짜({db_date})가 오늘({today})이 아니므로 건너뜁니다.")
                continue
            
            # 결과 추가
            results.append({
                'date': date_str,
                'time': time_str,
                'prompt': prompt_text
            })
            
            logger.info(f"프롬프트 데이터 추가: {date_str} {time_str} - {prompt_text[:50]}...")
            
            # 처리 완료된 프롬프트 ID 기록
            processed_prompts[prompt_id] = today
            new_processed_count += 1
        
        logger.info(f"새로 처리된 프롬프트 ID 수: {new_processed_count}")
        
        # 처리된 프롬프트 ID 목록 저장
        save_processed_prompts(processed_prompts)
        
        conn.close()
    except Exception as e:
        logger.error(f"데이터베이스 처리 중 오류 발생: {str(e)}\n{traceback.format_exc()}")
    
    logger.info(f"처리된 데이터 개수: {len(results)}")
    return project_name, results

def save_to_excel(project_name, data, save_path=SAVE_PATH):
    """
    데이터를 엑셀 파일로 저장
    
    Args:
        project_name (str): 프로젝트 이름
        data (list): 저장할 데이터 목록
        save_path (str): 저장 경로
        
    Returns:
        str: 저장된 파일 경로
    """
    if not data:
        logger.warning(f"저장할 데이터가 없습니다. 엑셀 파일을 생성하지 않습니다.")
        return None
    
    try:
        # 날짜 추출 (첫 번째 항목 기준)
        date_str = data[0]['date'].replace('-', '')
        
        # 저장 경로 생성
        project_folder = os.path.join(save_path, project_name)
        os.makedirs(project_folder, exist_ok=True)
        logger.info(f"프로젝트 폴더 생성: {project_folder}")
        
        # 파일 경로
        file_name = f"{project_name}_{date_str}_prompt.xlsx"
        file_path = os.path.join(project_folder, file_name)
        logger.info(f"엑셀 파일 저장 경로: {file_path}")
        
        # 컬럼 순서 정의 (응답 관련 열 제거)
        columns = ['date', 'time', 'prompt']
        
        # 특수 문자 제거 또는 치환
        for item in data:
            for key in item:
                if isinstance(item[key], str):
                    # 엑셀에서 처리할 수 없는 특수 문자 제거
                    # 제어 문자 제거 (0x00-0x1F, 0x7F 제외 탭, 개행, 캐리지 리턴)
                    item[key] = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', item[key])
                    # 문자열 길이 제한 (엑셀 셀 최대 길이는 32,767자)
                    if len(item[key]) > 32700:
                        item[key] = item[key][:32700]
        
        # 기존 파일 확인
        if os.path.exists(file_path):
            logger.info(f"기존 파일 발견, 업데이트 진행: {file_path}")
            # 기존 파일 데이터 로드 (컬럼 형식이 다를 수 있으므로 주의)
            existing_df = pd.read_excel(file_path)
            new_df = pd.DataFrame(data)
            
            # 기존 데이터의 컬럼이 새 형식과 다른 경우 처리
            for col in columns:
                if col not in existing_df.columns:
                    existing_df[col] = ''  # 빈 컬럼 추가
            
            # 응답 관련 컬럼 제거
            for col in existing_df.columns:
                if col not in columns:
                    existing_df = existing_df.drop(columns=[col])
            
            # 중복 제거하고 병합 (날짜, 시간, 프롬프트를 기준으로)
            combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['date', 'time', 'prompt'])
            
            # 정렬
            combined_df = combined_df.sort_values(by=['date', 'time'])
            
            # 컬럼 순서 정리
            combined_df = combined_df[columns]
            
            try:
                # 저장
                combined_df.to_excel(file_path, index=False)
                logger.info(f"기존 파일 업데이트됨: {len(combined_df)}개 행")
            except Exception as e:
                logger.error(f"엑셀 저장 오류 (업데이트): {str(e)}")
                # 오류 발생 시 CSV로 대체 저장
                csv_path = file_path.replace('.xlsx', '.csv')
                combined_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
                logger.info(f"CSV 파일로 대체 저장됨: {csv_path}")
                return csv_path
        else:
            logger.info(f"새 엑셀 파일 생성: {file_path}")
            # 새 파일 생성
            df = pd.DataFrame(data, columns=columns)
            try:
                df.to_excel(file_path, index=False)
                logger.info(f"새 파일 생성됨: {len(df)}개 행")
            except Exception as e:
                logger.error(f"엑셀 저장 오류 (새 파일): {str(e)}")
                # 오류 발생 시 CSV로 대체 저장
                csv_path = file_path.replace('.xlsx', '.csv')
                df.to_csv(csv_path, index=False, encoding='utf-8-sig')
                logger.info(f"CSV 파일로 대체 저장됨: {csv_path}")
                return csv_path
        
        return file_path
    except Exception as e:
        logger.error(f"엑셀 저장 중 오류 발생: {str(e)}\n{traceback.format_exc()}")
        return None

def extract_prompts(workspace_path=WORKSPACE_PATH, save_path=SAVE_PATH):
    """
    Cursor 폴더에서 프롬프트 데이터를 추출하여 엑셀 파일로 저장
    
    Args:
        workspace_path (str): Cursor 작업 디렉토리 경로
        save_path (str): 저장 경로
    
    Returns:
        list: 저장된 파일 경로 목록
    """
    # 저장 경로 생성
    os.makedirs(save_path, exist_ok=True)
    logger.info(f"저장 경로 생성: {save_path}")
    
    # 처리 결과 저장 (파일 경로)
    result_files = []
    
    # 오늘 수정된 폴더 찾기
    today_folders = find_today_folders(workspace_path)
    
    # 발견한 폴더가 없으면 종료
    if not today_folders:
        logger.warning("처리할 폴더가 없습니다.")
        return []
    
    # 각 폴더 처리
    for folder_path in today_folders:
        folder_name = os.path.basename(folder_path)
        
        # 폴더 처리 시작
        logger.info(f"[{folder_name}] 폴더 처리 시작")
        
        # 데이터베이스 처리
        project_name, data = process_database(folder_path)
        
        if data:
            # 데이터를 엑셀로 저장
            file_path = save_to_excel(project_name, data, save_path)
            if file_path:
                result_files.append(file_path)
                logger.info(f"파일 저장 완료: {file_path}")
            else:
                logger.error(f"파일 저장 실패: {project_name}")
        else:
            logger.warning(f"[{folder_name}] 저장할 데이터가 없습니다.")
    
    return result_files

def main():
    """
    메인 함수 - 프롬프트 추출 및 저장 실행
    """
    try:
        logger.info("Cursor 프롬프트 추출 시작")
        
        # 프롬프트 추출
        result_files = extract_prompts()
        
        if result_files:
            logger.info(f"프롬프트 추출 완료: {len(result_files)}개 파일 저장됨")
            for file_path in result_files:
                logger.info(f"  - {file_path}")
        else:
            logger.warning("저장된 파일이 없습니다.")
        
        logger.info("프롬프트 추출 종료")
    except Exception as e:
        logger.error(f"프롬프트 추출 중 오류 발생: {str(e)}\n{traceback.format_exc()}")

# 스크립트로 실행되었을 때만 main() 호출
if __name__ == "__main__":
    main()
