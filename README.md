# Cursor 프롬프트 추출기 (Cursor Prompt Extractor)

## 한국어 (Korean)

### 소개
이 프로그램은 Cursor IDE에서 사용자가 입력한 프롬프트를 자동으로 추출하여 엑셀 파일로 저장해주는 도구입니다. 매일 사용한 프롬프트를 효율적으로 관리하고 백업할 수 있도록 도와줍니다.

### 주요 기능
- Cursor IDE의 state.vscdb 파일에서 프롬프트 데이터 자동 추출
- 프로젝트별로 구분하여 일별 엑셀 파일 저장
- 중복 프롬프트 자동 필터링 (MD5 해시 기반)
- 직관적인 GUI 인터페이스 제공
- 자동 백업 및 오류 복구 메커니즘

### 설치 및 사용 방법
1. 제공된 DMG 파일 또는 앱 파일을 다운로드합니다.
2. macOS에서는 앱을 실행하기만 하면 됩니다.
3. "프롬프트 추출" 버튼을 클릭하여 프롬프트 추출을 시작합니다.
4. 추출된 프롬프트는 `~/Desktop/RYJ/saveprompt/[프로젝트명]/[프로젝트명]_YYYYMMDD_prompt.xlsx` 경로에 자동으로 저장됩니다.

### 작동 방식
- Cursor IDE가 프롬프트를 저장하는 SQLite 데이터베이스(state.vscdb)에 접근합니다.
- 데이터베이스에서 'aiService.prompts' 키를 조회하여 프롬프트 데이터를 추출합니다.
- MD5 해시를 이용해 프롬프트별 고유 ID를 생성하여 중복을 방지합니다.
- 데이터베이스 파일 수정 시간을 기준으로 오늘 날짜의 프롬프트만 추출합니다.
- 추출된 데이터는 프로젝트별, 날짜별로 구분하여 엑셀 파일로 저장됩니다.

### 주의사항
- 이 프로그램은 현재 macOS에 최적화되어 있습니다.
- Cursor IDE가 설치되어 있어야 합니다.
- 프롬프트 데이터는 로컬에만 저장되며 외부로 전송되지 않습니다.

### 프로젝트 구조
```
Cursor-Prompt/
├── cursor_logs_gui.py     # GUI 애플리케이션 진입점
├── debug_extraction.py    # 데이터 추출 및 처리 모듈
├── assets/                # 아이콘 및 이미지 리소스
├── dist/                  # 빌드된 애플리케이션
└── icon.icns              # 애플리케이션 아이콘
```

---

## English

### Introduction
This program is a tool that automatically extracts prompts you've entered in Cursor IDE and saves them as Excel files. It helps you efficiently manage and back up the prompts you use daily.

### Key Features
- Automatic extraction of prompt data from Cursor IDE's state.vscdb file
- Saves Excel files by project and date
- Automatic filtering of duplicate prompts (based on MD5 hash)
- Intuitive GUI interface
- Automatic backup and error recovery mechanisms

### Installation and Usage
1. Download the provided DMG file or app file.
2. On macOS, simply run the app.
3. Click the "Extract Prompts" button to start the extraction process.
4. Extracted prompts are automatically saved to `~/Desktop/RYJ/saveprompt/[ProjectName]/[ProjectName]_YYYYMMDD_prompt.xlsx`

### How It Works
- Accesses the SQLite database (state.vscdb) where Cursor IDE stores prompts
- Queries the 'aiService.prompts' key from the database to extract prompt data
- Creates unique IDs for each prompt using MD5 hash to prevent duplicates
- Extracts only prompts from today's date based on the database file's modification time
- Saves the extracted data as Excel files organized by project and date

### Notes
- This program is currently optimized for macOS.
- Cursor IDE must be installed.
- Prompt data is stored locally only and is not transmitted externally.

### Project Structure
```
Cursor-Prompt/
├── cursor_logs_gui.py     # GUI application entry point
├── debug_extraction.py    # Data extraction and processing module
├── assets/                # Icon and image resources
├── dist/                  # Built application
└── icon.icns              # Application icon
```

## 문제 해결

- **데이터를 찾을 수 없음**: Cursor IDE 설치 경로가 기본값과 다를 수 있습니다. "추출 데이터 경로" 설정에서 올바른 경로를 지정해 주세요.
- **저장 실패**: 저장 경로에 쓰기 권한이 있는지 확인하세요.
- **빈 엑셀 파일**: 오늘 작업한 Cursor 대화가 없는 경우 빈 파일이 생성될 수 있습니다.

## 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다. 