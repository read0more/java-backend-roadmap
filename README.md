# 김영한 로드맵 강좌

인프런 「김영한 공부법」 로드맵(https://www.inflearn.com/roadmaps/2238)의 강의 순서를 따라가는 학습 자료다. `index.html`을 브라우저로 열면 전체 목차가 나오고, 권마다 HTML이 하나씩 있다(`01-java-intro.html` … `27-db-perf.html`). 인터넷 없이 읽을 수 있다.

- 25권 222회. 권 하나가 로드맵의 강의 하나, 회차 하나가 그 강의의 섹션 하나에 대응한다.
- 로드맵 21번 「스프링 부트 - 핵심 원리와 활용」은 제외했고, 16번 도서 「자바 ORM 표준 JPA 프로그래밍」은 15권 JPA 기본편에 합쳤다.
- 각 회: 핵심 강의 → 핵심 요약 → 실무 재판단 → 적용 연습·해설 → 확인 문제 → 근거 자료.
- 완료 표시·문제 답·메모는 브라우저(localStorage)에 권별로 저장된다. 다크 모드, 인쇄, 기록 내보내기/가져오기를 지원한다.

## 내용의 범위와 근거

회차 구성은 인프런 강의 페이지에 공개된 커리큘럼(섹션·수업 제목)을 그대로 따른다(`source/curriculum/`, 2026-11-14 수집). 강의 영상·교안·예제 코드는 보지 않았고 옮기지도 않았다. 설명과 예제는 언어 명세·공식 문서(JLS, JVMS, Javadoc, Spring Reference, Jakarta 명세, Hibernate 문서, MySQL 매뉴얼, RFC)를 근거로 새로 썼으며, 회차 끝의 「근거와 더 읽을 자료」에 확인한 문서를 적었다. 따라서 실제 강의의 예제나 설명 순서와는 다르다.

## 이미지 넣기

`IMAGE_PROMPTS.md`에 본문에 넣을 그림의 위치·목적·프롬프트가 있다.

1. 맨 위의 공통 스타일 가이드를 프롬프트 앞에 붙여 이미지 생성 모델에 넘긴다.
2. Pillow가 설치된 Python에서 `python3 tools/save_visual.py <ID> <원본 파일> --remove-source`를 실행한다. 최대 너비 720픽셀의 `assets/visuals/<ID>.webp`를 만들고, 파일을 검사한 뒤 원본을 삭제한다.
3. 해당 권의 HTML을 다시 열면 그 자리에 그림이 나타난다. 파일이 없는 자리는 숨겨지므로 일부만 넣어도 된다.
4. `python3 build.py images`를 실행하면 만든 그림이 프롬프트 목록에서 빠진다.

## 다시 빌드하기

```bash
python3 build.py
```

`content/<slug>/NN.html`(회차 원고)을 고친 뒤 실행하면 권별 HTML, `index.html`, `IMAGE_PROMPTS.md`, `STATUS.md`가 다시 만들어진다. 외부 의존성은 없다.

## 파일 구성

- `index.html`, `NN-<slug>.html`: 빌드 결과물.
- `content/`: 회차 원고. `volumes.py`: 권·회차 계획. `AUTHORING.md`: 원고 형식과 작성 규칙.
- `STATUS.md`: 권별 작성 현황(자동 생성).
- `assets/`: 화면 스타일과 스크립트(`software-design-books-course`와 같은 스타일), `assets/visuals/`: 그림을 넣는 곳.
