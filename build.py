#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""자바 백엔드 로드맵 빌드 스크립트 (표준 라이브러리만 사용).

  python3 build.py                      전체 빌드: 권별 HTML, index.html, IMAGE_PROMPTS.md, STATUS.md
  python3 build.py images               미생성 이미지 목록만 갱신
  python3 build.py check <파일>...       회차 원고(content/<slug>/NN.html) 형식 검사
  python3 build.py appendix <파일>...    부록 영역 원고(content/appendix-pitfalls/NN-영역.html) 형식·링크 검사
  python3 build.py status               진행 현황만 출력
  python3 build.py brief <slug> <회차>    작성 에이전트용 회차 브리프 출력
  python3 build.py todo [개수]           남은 회차를 로드맵 순서대로 JSON 출력

회차 원고 형식은 AUTHORING.md 참고.
"""
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from volumes import STAGES, VOLUMES, BY_SLUG, BY_NO  # noqa: E402

CONTENT = ROOT / 'content'
SITE_TITLE = '자바 백엔드 로드맵'
STORAGE_PREFIX = 'java-backend-roadmap-'
BUILD_DATE = '2026-11-14'
MIN_CHARS, GOAL_CHARS = 8000, 14000
ALLOWED = {'p', 'h3', 'h4', 'ul', 'ol', 'li', 'strong', 'b', 'em', 'i', 'code', 'pre', 'table', 'thead', 'tbody', 'tr',
           'th', 'td', 'div', 'aside', 'span', 'figure', 'figcaption', 'details', 'summary', 'br', 'hr', 'a',
           'blockquote', 'dl', 'dt', 'dd', 'sub', 'sup', 'small', 'kbd', 'mark', 'img', 'caption'}
VOID = {'br', 'hr', 'img'}
LANG_LABEL = {'java': 'Java', 'sql': 'SQL', 'xml': 'XML / HTML', 'html': 'HTML', 'yaml': 'YAML', 'json': 'JSON',
              'bash': '셸', 'shell': '셸', 'ini': '설정 파일', 'properties': '설정 파일', 'kotlin': 'Kotlin',
              'groovy': 'Gradle', 'http': 'HTTP 메시지', 'plaintext': '', 'text': ''}
HLJS_ALIAS = {'html': 'xml', 'properties': 'ini', 'groovy': 'kotlin', 'http': 'plaintext', 'text': 'plaintext'}


# ---------------------------------------------------------------------------
# 원고 파싱
# ---------------------------------------------------------------------------
def esc_code(src):
    """<code>…</code>와 <pre class="diagram">…</pre> 안쪽은 원문 그대로 쓰고 여기서 한 번만 이스케이프한다."""
    def fix(m):
        return m[1] + html.escape(html.unescape(m[2]), quote=False) + m[3]
    src = re.sub(r'(<code\b[^>]*>)(.*?)(</code>)', fix, src, flags=re.S)
    return re.sub(r'(<pre class="diagram">)(.*?)(</pre>)', fix, src, flags=re.S)


def code_blocks(body):
    """<pre><code class="language-x"> 에 언어 라벨과 하이라이트 별칭을 붙인다."""
    def code(m):
        lang = m[1] or 'plaintext'
        label = re.search(r'data-label="([^"]*)"', m[0])
        label = label[1] if label else LANG_LABEL.get(lang, lang)
        return (f'<div class="code-label">{label}</div>' if label else '') + f'<pre><code class="language-{HLJS_ALIAS.get(lang, lang)}">'
    return re.sub(r'<pre(?: data-label="[^"]*")?><code(?: class="language-([a-z]+)")?>', code, body)


def part(src, name):
    m = re.search(rf'<x-{name}\b[^>]*>(.*?)</x-{name}>', src, re.S)
    return m[1].strip() if m else None


def text_of(s):
    return html.unescape(re.sub(r'<[^>]+>', '', s))


class Balance(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED:
            self.errors.append(f'허용하지 않는 태그 <{tag}> (줄 {self.getpos()[0]}). 코드라면 <code>로 감싸야 한다.')
        elif tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID or tag not in ALLOWED:
            return
        if not self.stack or self.stack[-1][0] != tag:
            self.errors.append(f'닫는 태그 </{tag}>가 짝이 맞지 않는다 (줄 {self.getpos()[0]}, 열려 있는 태그: {self.stack[-1][0] if self.stack else "없음"}).')
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break
        else:
            self.stack.pop()


def balance(fragment, where):
    p = Balance()
    p.feed(fragment)
    p.close()
    return [f'{where}: {e}' for e in p.errors] + [f'{where}: <{t}>가 닫히지 않았다 (줄 {line}).' for t, line in p.stack]


def visual_path(visual_id):
    webp = Path('assets', 'visuals', f'{visual_id}.webp')
    png = webp.with_suffix('.png')
    if not (ROOT / webp).is_file() and (ROOT / png).is_file():
        return png
    return webp


def parse(path, vol, num):
    """원고 하나를 읽어 (lesson dict, errors, warnings)를 돌려준다."""
    raw = path.read_text(encoding='utf-8')
    errors, warns = [], []
    if '<!--MORE-->' in raw:
        errors.append('<!--MORE--> 마커가 남아 있다. 이어 쓰기를 끝내야 한다.')
    src = esc_code(raw)
    title, secs, scope = vol['lessons'][num - 1]
    L = dict(num=num, title=title, sections=secs, scope=scope, vol=vol, visuals=[])
    meta = dict(re.findall(r'^\s*([a-z]+)\s*:\s*(.+?)\s*$', part(src, 'meta') or '', re.M))
    L['deck'] = meta.get('deck', '')
    if not L['deck']:
        errors.append('x-meta에 deck(한 문장 부제)이 없다.')
    body = part(src, 'lecture')
    if body is None:
        return L, errors + ['x-lecture가 없다.'], warns
    for name in ('goals', 'summary', 'review', 'practice', 'answer', 'glossary', 'refs'):
        if part(src, name) is None:
            errors.append(f'x-{name}가 없다.')

    # 시각 자료 슬롯
    def visual(m):
        attrs = dict(re.findall(r'([a-z]+)="([^"]*)"', m[1]))
        vid = attrs.get('id', '')
        v = dict(id=vid, title=attrs.get('title', ''), kind=attrs.get('kind', '다이어그램'), ratio=attrs.get('ratio', '16:9'),
                 hint=(part(m[2], 'hint') or ''), prompt=html.unescape(part(m[2], 'prompt') or ''), caption=(part(m[2], 'caption') or ''),
                 lesson=num, slug=vol['slug'])
        if not re.fullmatch(rf'{vol["slug"]}-{num:02}-[a-z0-9-]+', vid):
            errors.append(f'x-visual id "{vid}"는 {vol["slug"]}-{num:02}-<영문소문자-이름> 형식이어야 한다.')
        if any(x['id'] == vid for x in L['visuals']):
            errors.append(f'x-visual id "{vid}"가 중복된다.')
        for k in ('title', 'hint', 'prompt'):
            if not v[k]:
                errors.append(f'x-visual {vid}: {k}가 비어 있다.')
        L['visuals'].append(v)
        src_img = visual_path(vid).as_posix()
        # 이미지가 로드되기 전에는 슬롯이 숨겨져 있으므로 곧바로 요청한다.
        return (f'<figure class="visual-slot learning-visual" data-visual="{vid}"><img src="{src_img}" alt="{html.escape(v["title"])}" decoding="async">'
                + (f'<figcaption>{v["caption"]}</figcaption>' if v['caption'] else '') + '</figure>')
    body = re.sub(r'<x-visual\b([^>]*)>(.*?)</x-visual>', visual, body, flags=re.S)
    if '<x-' in body:
        errors.append('x-lecture 안에 처리되지 않은 x- 태그가 있다 (x-visual 형식 확인).')
    if re.search(r'<h[12]\b', body):
        errors.append('x-lecture 안에서는 h3, h4만 쓴다 (h1, h2 금지).')
    errors += balance(body, 'x-lecture')

    # 소제목 id와 차례
    toc = []

    def heading(m):
        anchor = f'lesson-{num:02}-topic-{len(toc) + 1:02}'
        toc.append((anchor, text_of(m[1])))
        return f'<h3 id="{anchor}">{m[1]}</h3>'
    body = re.sub(r'<h3>(.*?)</h3>', heading, body, flags=re.S)
    if len(toc) < 4:
        warns.append(f'h3 소제목이 {len(toc)}개뿐이다. 책의 한 챕터라면 보통 6개 이상이다.')

    body = code_blocks(body)

    chars = len(re.sub(r'\s+', '', text_of(body)))
    L.update(body=body, toc=toc, chars=chars)
    if chars < MIN_CHARS:
        errors.append(f'본문이 {chars:,}자다. 최소 {MIN_CHARS:,}자(공백 제외), 목표 {GOAL_CHARS:,}자 이상.')
    elif chars < GOAL_CHARS:
        warns.append(f'본문이 {chars:,}자다. 목표는 {GOAL_CHARS:,}자 이상이다. 억지로 줄인 곳이 없는지 확인.')
    L['minutes'] = int(meta['minutes']) if meta.get('minutes', '').isdigit() else max(30, round(chars / 450 / 5) * 5)

    lis = lambda name: [x.strip() for x in re.findall(r'<li>(.*?)</li>', part(src, name) or '', re.S)]
    dts = lambda name: [(a.strip(), b.strip()) for a, b in re.findall(r'<dt>(.*?)</dt>\s*<dd>(.*?)</dd>', part(src, name) or '', re.S)]
    L['goals'], L['practice'] = lis('goals'), lis('practice')
    L['summary'], L['glossary'] = dts('summary'), dts('glossary')
    L['review'], L['answer'] = part(src, 'review') or '', part(src, 'answer') or ''
    L['refs'] = [(u, a.strip(), re.sub(r'^[\s—–\-·:]+', '', n).strip()) for u, a, n in re.findall(r'<li>\s*<a href="([^"]+)"[^>]*>(.*?)</a>(.*?)</li>', part(src, 'refs') or '', re.S)]
    L['quiz'] = []
    for ans, inner in re.findall(r'<x-quiz answer="(\d)">(.*?)</x-quiz>', src, re.S):
        q, opts, why = re.search(r'<q>(.*?)</q>', inner, re.S), re.findall(r'<o>(.*?)</o>', inner, re.S), re.search(r'<why>(.*?)</why>', inner, re.S)
        if not q or not why or not 3 <= len(opts) <= 5 or int(ans) >= len(opts):
            errors.append('x-quiz 형식 오류: <q>, <o> 3~5개, <why>가 필요하고 answer는 0부터 세는 보기 번호다.')
            continue
        L['quiz'].append(dict(q=q[1].strip(), options=[o.strip() for o in opts], answer=int(ans), why=why[1].strip()))
    for name, n, lo in (('goals', len(L['goals']), 3), ('summary', len(L['summary']), 5), ('practice', len(L['practice']), 3),
                        ('quiz', len(L['quiz']), 3), ('glossary', len(L['glossary']), 4), ('refs', len(L['refs']), 2)):
        if n < lo:
            errors.append(f'x-{name} 항목이 {n}개다. 최소 {lo}개.')
    for name in ('review', 'answer'):
        errors += balance(L[name], f'x-{name}')
    for u, _, _ in L['refs']:
        if not u.startswith('http'):
            errors.append(f'x-refs의 URL이 http(s)로 시작하지 않는다: {u}')
    return L, errors, warns


def load():
    """모든 권의 원고를 읽는다. {slug: {num: lesson}}와 문제 목록을 돌려준다."""
    done, problems = {}, {}
    for vol in VOLUMES:
        done[vol['slug']] = {}
        for num in range(1, len(vol['lessons']) + 1):
            f = CONTENT / vol['slug'] / f'{num:02}.html'
            if not f.exists():
                continue
            L, errors, warns = parse(f, vol, num)
            if errors:
                problems[f'{vol["slug"]}/{num:02}'] = errors
            else:
                done[vol['slug']][num] = L
    return done, problems


def reviewed(slug):
    f = CONTENT / slug / 'REVIEW.md'
    return {int(n) for n in re.findall(r'^- (\d{2}):', f.read_text(encoding='utf-8'), re.M)} if f.exists() else set()


# ---------------------------------------------------------------------------
# HTML 조립
# ---------------------------------------------------------------------------
def stage_of(no):
    return next(s for s in STAGES if no in s[2])


def roadmap_svg(current=None):
    rows = []
    for i, (name, _, nos) in enumerate(STAGES):
        x, y = 30 + (i % 2) * 240, 44 + (i // 2) * 62
        on = current in nos
        rows.append(f'<rect x="{x}" y="{y}" width="220" height="46" rx="10" fill="{"#c8e6ad" if on else "#243f40"}" stroke="#507370"/>'
                    f'<text x="{x + 110}" y="{y + 20}" fill="{"#193c36" if on else "#f1f4e8"}" font-size="13" font-weight="700">{name}</text>'
                    f'<text x="{x + 110}" y="{y + 36}" fill="{"#193c36" if on else "#b2c7bd"}" font-size="10">{" · ".join(BY_NO[n]["short"] for n in nos)[:34]}</text>')
    return ('<svg viewBox="0 0 520 330" role="img" aria-label="로드맵 여덟 단계 가운데 현재 위치"><g font-family="system-ui,sans-serif" text-anchor="middle">'
            '<text x="260" y="24" fill="#b2c7bd" font-size="11" letter-spacing="1.5">JAVA → SPRING → JPA → DATABASE</text>' + ''.join(rows)
            + '<text x="260" y="312" fill="#b2c7bd" font-size="11">문법이 아니라, 그 아래에서 일어나는 일을 배운다.</text></g></svg>')


def article(L, total, written):
    n, vol = L['num'], L['vol']
    name = f'lesson-{n:02}'
    src = vol['course'] + ' · 섹션 ' + ', '.join(str(s) for s in L['sections']) + (' (일부)' if L['scope'] else '')
    quizzes = ''
    for qi, q in enumerate(L['quiz']):
        k = f'{n}-{qi}'
        quizzes += (f'<form class="quiz" data-quiz="{k}" data-answer="{q["answer"]}"><fieldset><legend>{qi + 1}. {q["q"]}</legend>'
                    + ''.join(f'<label><input type="radio" name="q-{k}" value="{i}"><span>{x}</span></label>' for i, x in enumerate(q['options']))
                    + f'</fieldset><button type="submit" class="secondary">답 확인</button><p class="feedback" aria-live="polite" hidden></p><span class="explanation" hidden>{q["why"]}</span></form>')
    prev = next((f'#lesson-{i:02}' for i in range(n - 1, 0, -1) if i in written), '#home')
    nxt = next((f'#lesson-{i:02}' for i in range(n + 1, total + 1) if i in written), '#glossary')
    toc = ''.join(f'<li><a href="#{a}">{html.escape(t)}</a></li>' for a, t in L['toc'])
    refs = ''.join(f'<li><span><a href="{u}" target="_blank" rel="noopener">{a} ↗</a>' + (f' <small>· {note}</small>' if note else '') + '</span></li>' for u, a, note in L['refs'])
    summary = ''.join(f'<div><dt>{a}</dt><dd>{b}</dd></div>' for a, b in L['summary'])
    return f'''<article class="page lesson" id="{name}" data-lesson="{n}" aria-labelledby="title-{name}">
 <header class="lesson-header"><p class="eyebrow">{vol["short"]} / {n:02}회</p><h1 id="title-{name}" tabindex="-1">{L["title"]}</h1><p class="deck">{L["deck"]}</p><div class="lesson-tags"><span class="book-tag">{src}</span><span>{L["minutes"]}분 학습</span><span>본문 {L["chars"]:,}자</span></div></header>
 <section class="objectives"><div><span class="eyebrow">TODAY'S OUTCOME</span><h2>오늘 끝나면 할 수 있는 것</h2></div><ul>{"".join("<li>" + x + "</li>" for x in L["goals"])}</ul><p>핵심 강의 → 핵심 요약 → 실무 재판단 → 적용 연습 → 이해 확인</p></section>
 <nav class="in-lesson" aria-label="강의 안에서 이동"><a href="#{name}-concept">핵심 강의</a><a href="#{name}-summary">핵심 요약</a><a href="#{name}-practice">적용 연습</a><a href="#{name}-quiz">확인 문제</a></nav>
 <section class="prose" id="{name}-concept"><h2><span>01</span> 핵심 강의</h2><details class="lesson-toc" id="{name}-toc"><summary>이 강의의 차례 · 소제목 {len(L["toc"])}개</summary><ol>{toc}</ol></details>{L["body"]}</section>
 <section class="lesson-summary" id="{name}-summary" aria-labelledby="{name}-summary-title"><span class="eyebrow">SUMMARY · 핵심 요약</span><h2 id="{name}-summary-title">이번 강의에서 기억할 것</h2><dl class="takeaways">{summary}</dl></section>
 <aside class="review"><span class="eyebrow">ENGINEERING JUDGMENT</span><h3>실무에서 다시 판단하면</h3>{L["review"] if L["review"].lstrip().startswith("<") else "<p>" + L["review"] + "</p>"}</aside>
 <section class="practice" id="{name}-practice"><h2><span>02</span> 적용 연습</h2><p>정답을 열기 전에 먼저 자기 말로 적어 본다. 코드를 실행할 수 있다면 직접 돌려서 확인한다.</p><ol>{"".join("<li>" + x + "</li>" for x in L["practice"])}</ol><label for="exercise-{n}">나의 답 / 메모</label><textarea id="exercise-{n}" data-note="exercise-{n}" rows="6" placeholder="결론만 쓰기보다 왜 그렇게 되는지를 적어 보세요."></textarea><details class="answer"><summary>예시 해설과 완료 기준</summary>{L["answer"] if L["answer"].lstrip().startswith("<") else "<p>" + L["answer"] + "</p>"}</details></section>
 <section id="{name}-quiz"><h2><span>03</span> 이해 확인</h2><p class="micro">점수보다 이유를 설명하는 연습이다. 답은 바꿔서 다시 확인할 수 있다.</p>{quizzes}</section>
 <section class="reflection"><h2>오늘의 한 문장</h2><label for="reflection-{n}">이 강의를 남에게 설명한다면 첫 문장은?</label><textarea id="reflection-{n}" data-note="reflection-{n}" rows="3" placeholder="예: static 변수는 메서드 영역에 하나만 있고, 그래서…"></textarea></section>
 <details class="further"><summary>근거와 더 읽을 자료</summary><ul class="ref-list">{refs}</ul><p class="micro">본문의 사실 관계를 확인하는 데 쓴 공식 명세·문서다. 링크는 인터넷이 필요하다.</p></details>
 <footer class="lesson-footer"><button class="complete" data-complete="{n}" type="button" aria-pressed="false">이 강의 학습 완료</button><div><a href="{prev}">← 이전</a><a class="button secondary" href="{nxt}">{"용어 복습" if nxt == "#glossary" else "다음 강의"} →</a></div></footer></article>'''


def head(title, desc):
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark">'
            f'<title>{title}</title><meta name="description" content="{html.escape(desc)}"><link rel="stylesheet" href="assets/course.css"><link rel="stylesheet" href="assets/roadmap.css?v=2">'
            '<script src="assets/roadmap-storage.js"></script><script defer src="assets/navigation.js"></script></head>')


def sidebar_header(brand, subtitle=''):
    subtitle = f'<small>{subtitle}</small>' if subtitle else ''
    return (f'<dialog id="menu-dialog" aria-label="목차"></dialog><aside id="sidebar" class="sidebar" aria-label="목차">'
            f'<div class="sidebar-head"><a class="brand" href="#home"><span class="brand-icon" aria-hidden="true">▤</span>'
            f'<span>{brand}{subtitle}</span></a><button type="button" id="menu-close" aria-label="목차 닫기">닫기 ×</button></div>')


def sidebar_search(label, placeholder):
    return (f'<label class="search-label" for="nav-search">{label}</label>'
            f'<input id="nav-search" type="search" placeholder="{placeholder}">'
            '<p id="nav-count" class="micro" role="status"></p>')


def volume_page(vol, lessons):
    total, written = len(vol['lessons']), set(lessons)
    file = f'{vol["no"]:02}-{vol["slug"]}.html'
    brand = f'ROADMAP {vol["no"]:02}'
    page_title = f'{vol["short"]} · {SITE_TITLE}'
    nav = cards = ''
    for i, (title, _, _) in enumerate(vol['lessons'], 1):
        if i in written:
            L = lessons[i]
            nav += f'<a href="#lesson-{i:02}" data-nav="{i}"><span class="nav-num">{i:02}회</span><span>{title}</span><span class="done-mark" aria-hidden="true"></span></a>'
            cards += (f'<a class="lesson-card" href="#lesson-{i:02}" data-card="{i}"><span class="card-day">{i:02}회 <small>{L["minutes"]} MIN · 섹션 {", ".join(map(str, L["sections"]))}</small></span>'
                      f'<h3>{title}</h3><p>{L["deck"]}</p><span class="card-link">강의 열기 <span>↗</span></span></a>')
        else:
            nav += f'<span class="nav-pending"><span class="nav-num">{i:02}회</span><span>{title}</span><span class="pending-mark">준비 중</span></span>'
            cards += f'<div class="lesson-card is-pending"><span class="card-day">{i:02}회 <small>준비 중</small></span><h3>{title}</h3><p>아직 작성되지 않은 회차다.</p></div>'
    articles = ''.join(article(lessons[i], total, written) for i in sorted(written))
    terms = [(t, d, i) for i in sorted(written) for t, d in lessons[i]['glossary']]
    gloss = ('<section class="page" id="glossary"><header class="lesson-header"><p class="eyebrow">REFERENCE / ' + str(len(terms)) + ' TERMS</p><h1 tabindex="-1">막힐 때 돌아오는 용어 사전</h1>'
             '<p class="deck">이 권에서 나온 용어를 회차로 다시 연결한다.</p></header><label for="glossary-search">용어 검색</label><input id="glossary-search" type="search" placeholder="용어를 입력하세요"><div class="glossary-grid">'
             + ''.join(f'<article class="glossary-item"><h2>{t}</h2><p>{d}</p><a href="#lesson-{i:02}">{i:02}회 「{vol["lessons"][i - 1][0]}」에서 다시 보기 →</a></article>' for t, d, i in terms)
             + '</div><p id="glossary-empty" hidden>일치하는 용어가 없습니다.</p></section>')
    ref_rows = ''.join(f'<tr><td><a href="#lesson-{i:02}">{i:02}회</a></td><td><a href="{u}" target="_blank" rel="noopener">{a}</a></td><td>{note}</td></tr>' for i in sorted(written) for u, a, note in lessons[i]['refs'])
    sources = f'''<section class="page" id="sources"><header class="lesson-header"><p class="eyebrow">SOURCES &amp; SCOPE</p><h1 tabindex="-1">근거와 범위</h1><p class="deck">이 권이 무엇을 기준으로 쓰였고 어디까지 다루는지.</p></header><div class="prose">
<h2>범위</h2><p>회차 구성은 인프런에 공개된 「{vol["course"]}」 커리큘럼의 섹션과 수업 제목을 기준으로 삼았다(<code>source/curriculum/{vol["no"]:02}-{vol["slug"]}.md</code>, 수집일 {BUILD_DATE}). 강의 영상·교안·예제 코드는 옮기지 않았고, 설명과 예제는 공식 명세와 문서를 근거로 새로 썼다. 따라서 강의에서 실제로 쓰는 예제나 설명 순서와는 다를 수 있다.</p>
<h2>회차별 근거 자료</h2><div class="table-wrap"><table class="source-table"><thead><tr><th>회차</th><th>자료</th><th>확인한 내용</th></tr></thead><tbody>{ref_rows}</tbody></table></div>
<h2>시각 자료</h2><p>그림 파일을 <code>assets/visuals/&lt;ID&gt;.webp</code>로 넣으면 본문의 해당 자리에 자동으로 표시된다. 생성용 프롬프트는 <code>IMAGE_PROMPTS.md</code>에 있다. <span id="visual-count" class="micro"></span></p>
<h2>학습 기록</h2><p>완료 표시·문제 답·메모는 이 브라우저에만 저장된다. 다른 기기로 옮기거나 브라우저 데이터를 지우기 전에는 기록을 내보내 둔다.</p></div></section>'''
    stage = stage_of(vol['no'])
    first = f'#lesson-{min(written):02}' if written else '#home'
    return f'''{head(page_title, vol["desc"])}<body data-key="{STORAGE_PREFIX}{vol["slug"]}-v1" data-total="{total}" data-title="{page_title}" data-brand="{brand}" data-first="{first.lstrip("#")}"><a class="skip" href="#main">본문으로 건너뛰기</a><noscript><p class="noscript">JavaScript가 꺼져 있어 모든 강의를 한 페이지로 표시합니다.</p></noscript><div id="storage-warning" class="storage-warning" role="status" hidden>브라우저 저장소를 사용할 수 없습니다. 닫기 전에 기록 내보내기를 사용하세요.</div>
{sidebar_header(brand, vol["short"])}<div class="sidebar-intro">문법이 아니라<br><b>그 아래의 원리를 배운다.</b></div><label class="search-label" for="course-search">강의 검색</label><input id="course-search" type="search" placeholder="스택 프레임, 프록시, 인덱스…"><p id="search-count" class="micro" aria-live="polite"></p><nav aria-label="전체 강의"><a class="overview-link" href="index.html">← 전체 로드맵</a><a class="overview-link" href="#home">이 권의 안내</a><a id="lesson-outline-link" class="overview-link" hidden>현재 강의의 소제목 차례</a><div class="nav-group"><p>{stage[0]}</p>{nav}</div><div class="nav-resources"><a href="#glossary">↗ 용어 사전</a><a href="#sources">↗ 근거와 범위</a></div></nav><div class="sidebar-bottom"><span>{len(written)} / {total} LESSONS</span><span>VOL {vol["no"]:02}</span></div></aside>
<div class="shell"><header class="topbar"><button id="menu-toggle" class="icon-button" type="button" aria-controls="sidebar" aria-expanded="false" hidden><span aria-hidden="true">☰</span> <span class="menu-label">목차 열기</span></button><span id="current-label">수업 안내</span><div class="top-actions"><span id="progress-label">0 / {total} 완료</span><button id="theme-toggle" class="icon-button" type="button" aria-label="테마 전환">다크 모드</button><button id="print-current" class="icon-button" type="button">인쇄</button></div><div class="course-progress"><span id="course-progress-bar"></span></div></header><main id="main" tabindex="-1">
<section id="home" class="page"><div class="hero"><div class="hero-copy"><span class="eyebrow">ROADMAP VOL {vol["no"]:02} · {stage[0]}</span><h1 tabindex="-1">{vol["short"]}</h1><p>{vol["desc"]}</p><div class="hero-actions"><a id="resume-link" class="button" href="{first}">첫 수업 시작하기 →</a><a class="hero-secondary" href="#curriculum">전체 강의 보기 ↓</a></div><div class="hero-stats"><span><b>{total}</b>회 수업</span><span><b>{len(written)}</b>회 작성됨</span><span><b>{sum(L["chars"] for L in lessons.values()):,}</b>자</span></div></div><div class="hero-art">{roadmap_svg(vol["no"])}<div class="art-caption"><span>BASED ON THE PUBLIC CURRICULUM</span><b>{vol["course"]}</b></div></div></div>
<div class="home-intro"><div><span class="eyebrow">WHAT THIS VOLUME IS</span><h2>코드 작성법보다,<br>왜 그렇게 동작하는지.</h2><p>각 회차는 강의의 한 섹션에 대응한다. 그 섹션이 다루는 주제를 빠짐없이 짚되, 무게는 <b>바닥의 원리</b>에 둔다. {vol["focus"]}</p></div><aside><b>읽는 법</b><p>본문을 읽고 핵심 요약으로 뼈대를 확인한 다음, 적용 연습을 손으로 풀고 확인 문제로 이유를 점검한다. 한 회차가 책의 한 챕터 분량이므로 나눠 읽어도 된다.</p><p>사실 관계는 공식 명세와 문서를 근거로 삼았고, 회차 끝의 「근거와 더 읽을 자료」에 적어 두었다.</p></aside></div>
<section class="learning-tools"><div><h2>내 학습 기록</h2><p>완료 표시·문제 답·메모를 이 브라우저에 보관합니다.</p></div><div><button id="export-progress" class="secondary" type="button">기록 내보내기</button><button id="import-progress" class="secondary" type="button">기록 가져오기</button><input id="import-file" type="file" accept="application/json,.json" hidden><button id="print-all" class="text-button" type="button">전체 강의 인쇄</button></div><p id="record-status" role="status"></p></section>
<div id="curriculum"><div class="section-heading"><span class="eyebrow">THE LEARNING MAP</span><h2>{vol["short"]} — {total}회</h2><p>{vol["course"]}의 섹션 순서를 따른다.</p></div><section class="curriculum-group"><div class="lesson-grid">{cards}</div></section></div></section>
{articles}{gloss}{sources}<footer class="site-footer"><span>{SITE_TITLE} · VOL {vol["no"]:02}</span><a href="index.html">전체 로드맵</a><span>로컬 학습 자료 · 외부 분석 도구 없음</span></footer></main></div><div id="toast" role="status" hidden></div><script src="assets/vendor/highlightjs/highlight.min.js"></script><script src="assets/code-highlight.js"></script><script src="assets/course.js?v=3"></script></body></html>''', file


def hub_page(done):
    nav = sections = ''
    total_l = sum(len(v['lessons']) for v in VOLUMES)
    done_l = sum(len(x) for x in done.values())
    for name, desc, nos in STAGES:
        nav += f'<div class="nav-group"><p>{name}</p>' + ''.join(f'<a href="{n:02}-{BY_NO[n]["slug"]}.html"><span class="nav-num">{n:02}</span><span>{BY_NO[n]["short"]}</span></a>' for n in nos) + '</div>'
        cards = ''
        for n in nos:
            v = BY_NO[n]
            w, t = len(done[v['slug']]), len(v['lessons'])
            state = '작성 완료' if w == t else (f'{w}/{t}회 작성됨' if w else '준비 중')
            cards += (f'<a class="lesson-card{"" if w else " is-pending"}" href="{n:02}-{v["slug"]}.html" data-volume="{STORAGE_PREFIX}{v["slug"]}-v1" data-total="{t}"><span class="card-day">VOL {n:02} <small>{t}회 · {state}</small></span>'
                      f'<h3>{v["short"]}</h3><p>{v["desc"]}</p><span class="card-link"><span class="vol-progress"></span> 열기 <span>↗</span></span></a>')
        sections += f'<section class="curriculum-group"><h2>{name}</h2><p class="stage-desc">{desc}</p><div class="lesson-grid">{cards}</div></section>'
    has_appx = any(APPX.glob('[0-9][0-9]-*.html'))
    appx_nav = f'<div class="nav-group"><p>부록</p><a href="{APPX_FILE}"><span class="nav-num">+</span><span>흔하지만 치명적인 실수</span></a></div>' if has_appx else ''
    appx_card = (f'<section class="curriculum-group"><h2>부록</h2><p class="stage-desc">권을 가로질러 모아 본 것.</p><div class="lesson-grid"><a class="lesson-card" href="{APPX_FILE}"><span class="card-day">APPENDIX</span>'
                 '<h3>흔하지만 치명적인 실수</h3><p>한두 줄로 저지르기 쉽고 결과가 큰 실수를 영역별로 모았다. 강의에 있는 것은 해당 회차로 연결하고, 없는 것은 부록에서 설명한다.</p><span class="card-link">열기 <span>↗</span></span></a></div></section>') if has_appx else ''
    return f'''{head(SITE_TITLE, "자바에서 스프링, JPA, 데이터베이스까지 백엔드의 동작 원리를 배우는 학습 자료.")}<body><a class="skip" href="#main">본문으로 건너뛰기</a>
{sidebar_header(SITE_TITLE)}<div class="sidebar-intro">문법이 아니라<br><b>그 아래의 원리를 배운다.</b></div>{sidebar_search("권·부록 검색", "권 제목 또는 기술명")}<nav aria-label="전체 권"><div id="nav-results" hidden></div>{nav}{appx_nav}</nav><div class="sidebar-bottom"><span>{len(VOLUMES)} VOLUMES</span><span>{total_l} LESSONS</span></div></aside>
<div class="shell"><header class="topbar"><button id="menu-toggle" class="icon-button" type="button" aria-controls="sidebar" aria-expanded="false" hidden><span aria-hidden="true">☰</span> <span class="menu-label">목차 열기</span></button><span id="current-label">전체 로드맵</span><div class="top-actions"><span id="progress-label">{done_l} / {total_l}회 작성됨</span><button id="theme-toggle" class="icon-button" type="button" aria-label="테마 전환">다크 모드</button></div></header><main id="main" tabindex="-1">
<section id="home" class="page"><div class="hero"><div class="hero-copy"><span class="eyebrow">JAVA · SPRING · JPA · DATABASE</span><h1 tabindex="-1">{SITE_TITLE}</h1><p>자바에서 스프링, JPA, 데이터베이스까지. JVM·스레드·네트워크·DB 엔진이 어떻게 동작하는지 살펴봅니다.</p><div class="hero-actions"><a class="button" href="01-java-intro.html">1권부터 시작하기 →</a><a class="hero-secondary" href="#curriculum">전체 권 보기 ↓</a></div><div class="hero-stats"><span><b>{len(VOLUMES)}</b>권</span><span><b>{total_l}</b>회 수업</span><span><b>{done_l}</b>회 작성됨</span></div></div><div class="hero-art">{roadmap_svg()}<div class="art-caption"><span>FUNDAMENTALS FIRST.</span><b>왜 그렇게 동작하는지<br>설명할 수 있을 때까지.</b></div></div></div>
<div class="home-intro"><div><span class="eyebrow">HOW THIS COURSE IS BUILT</span><h2>로드맵의 순서,<br>실제 커리큘럼의 범위.</h2><p>권 하나가 로드맵의 강의 하나에, 회차 하나가 그 강의의 섹션 하나에 대응한다. 회차의 범위는 인프런에 공개된 커리큘럼(섹션·수업 제목)에서 가져왔고, 설명과 예제는 언어 명세·공식 문서를 근거로 새로 썼다. 강의 영상이나 교안의 내용을 옮긴 것이 아니다.</p></div><aside><b>빠진 것</b><p>로드맵 21번 「스프링 부트 - 핵심 원리와 활용」은 제외했다. 16번 도서 「자바 ORM 표준 JPA 프로그래밍」은 같은 주제인 15권 JPA 기본편에서 함께 다룬다.</p><p>로드맵은 스프링을 시작하기 전에 최소한 자바 기본편과 중급 1·2편(2~4권)을 다지라고 권한다.</p></aside></div>
<div id="curriculum"><div class="section-heading"><span class="eyebrow">THE ROADMAP</span><h2>여덟 단계, {len(VOLUMES)}권.</h2><p>번호는 로드맵의 순번이다. 준비 중인 권은 회차가 작성되는 대로 채워진다.</p></div>{sections}{appx_card}</div></section>
<footer class="site-footer"><span>{SITE_TITLE} · {BUILD_DATE}</span><span>로컬 학습 자료 · 외부 분석 도구 없음</span></footer></main></div>
<script>(()=>{{document.querySelectorAll('[data-volume]').forEach(a=>{{try{{const s=JSON.parse(readRoadmapStorage(a.dataset.volume));if(s&&s.done&&s.done.length)a.querySelector('.vol-progress').textContent=s.done.length+' / '+a.dataset.total+' 완료 ·'}}catch(e){{}}}})}})();</script></body></html>'''


# ---------------------------------------------------------------------------
# 부록: 흔하지만 치명적인 실수 모음 (content/appendix-pitfalls/NN-영역.html → appendix-pitfalls.html)
# ---------------------------------------------------------------------------
APPX = CONTENT / 'appendix-pitfalls'
APPX_FILE = 'appendix-pitfalls.html'
HARMS = ('데이터 손상', '장애', '보안', '틀린 결과', '성능')


def lesson_lookup(done=None):
    """(slug, num) → lesson dict(없거나 검사 실패면 None). done이 없으면 필요한 회차만 읽는다."""
    cache = {}

    def get(slug, num):
        if done is not None:
            return done.get(slug, {}).get(num)
        if (slug, num) not in cache:
            f, vol = CONTENT / slug / f'{num:02}.html', BY_SLUG.get(slug)
            L, errors = (parse(f, vol, num)[:2] if vol and f.exists() else (None, ['없음']))
            cache[slug, num] = None if errors else L
        return cache[slug, num]
    return get


def parse_area(path, lesson):
    """부록 영역 파일 하나를 읽어 (area dict, errors)를 돌려준다. 형식은 content/appendix-pitfalls/README.md."""
    src = esc_code(path.read_text(encoding='utf-8'))
    errors = []
    meta = dict(re.findall(r'^\s*([a-z]+)\s*:\s*(.+?)\s*$', part(src, 'meta') or '', re.M))
    A = dict(file=path.name, key=path.stem, title=meta.get('title', ''), desc=meta.get('desc', ''), items=[])
    if not A['title'] or not A['desc']:
        errors.append('x-meta에 title과 desc가 있어야 한다.')
    for attrs, inner in re.findall(r'<x-item\b([^>]*)>(.*?)</x-item>', src, re.S):
        attrs = dict(re.findall(r'([a-z]+)="([^"]*)"', attrs))
        iid, where = attrs.get('id', ''), f'항목 {attrs.get("id", "?")}'
        it = dict(id=iid, harm=attrs.get('harm', ''), title=part(inner, 'title') or '', symptom=part(inner, 'symptom') or '',
                  body=part(inner, 'body'), see=[], refs=[])
        if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', iid):
            errors.append(f'{where}: id는 영문 소문자·숫자·하이픈이어야 한다.')
        if any(x['id'] == iid for x in A['items']):
            errors.append(f'{where}: id가 중복된다.')
        if it['harm'] not in HARMS:
            errors.append(f'{where}: harm은 {" / ".join(HARMS)} 중 하나여야 한다.')
        for k in ('title', 'symptom'):
            if not it[k]:
                errors.append(f'{where}: x-{k}가 비어 있다.')
        for sattrs, note in re.findall(r'<x-see\b([^>]*)>(.*?)</x-see>', inner, re.S):
            sattrs = dict(re.findall(r'([a-z]+)="([^"]*)"', sattrs))
            m = re.fullmatch(r'([a-z0-9-]+)/(\d\d)', sattrs.get('to', ''))
            L = lesson(m[1], int(m[2])) if m else None
            if not L:
                errors.append(f'{where}: x-see to="{sattrs.get("to", "")}" 회차를 찾을 수 없다(형식: slug/NN).')
                continue
            h = ' '.join(html.unescape(sattrs.get('h', '')).split())
            hit = next(((a, t) for a, t in L['toc'] if h and h in ' '.join(t.split())), None)
            if h and not hit:
                errors.append(f'{where}: {sattrs["to"]}에 "{h}"가 들어간 h3 소제목이 없다.')
                continue
            vol = L['vol']
            it['see'].append(dict(href=f'{vol["no"]:02}-{vol["slug"]}.html#' + (hit[0] if hit else f'lesson-{L["num"]:02}'),
                                  label=f'{vol["short"]} {L["num"]:02}회 「{L["title"]}」' + (f' › {html.escape(hit[1])}' if hit else ''), note=note.strip()))
        if it['body'] is None and not it['see']:
            errors.append(f'{where}: x-see(강의에 있는 내용)도 x-body(강의에 없는 내용)도 없다.')
        if it['body'] is not None:
            if re.search(r'<h[123]\b|<x-', it['body']):
                errors.append(f'{where}: x-body 안에서는 h4만 쓰고 x- 태그는 쓰지 않는다.')
            errors += balance(it['body'], f'{where} x-body')
            it['chars'] = len(re.sub(r'\s+', '', text_of(it['body'])))
            if it['chars'] < 500:
                errors.append(f'{where}: x-body가 {it["chars"]}자다. 원인·재현·고치는 법을 쓰면 500자는 넘는다.')
            it['body'] = code_blocks(it['body'])
            it['refs'] = [(u, a.strip(), re.sub(r'^[\s—–\-·:]+', '', n).strip()) for u, a, n in
                          re.findall(r'<li>\s*<a href="(http[^"]+)"[^>]*>(.*?)</a>(.*?)</li>', part(inner, 'refs') or '', re.S)]
            if not it['refs']:
                errors.append(f'{where}: x-body가 있으면 x-refs에 실제로 연 근거 URL이 하나 이상 있어야 한다.')
        for k in ('title', 'symptom'):
            errors += balance(it[k], f'{where} x-{k}')
        A['items'].append(it)
    if not A['items']:
        errors.append('x-item이 하나도 없다.')
    return A, errors


def appendix_page(areas):
    n_all = sum(len(a['items']) for a in areas)
    n_new = sum(1 for a in areas for it in a['items'] if it['body'] is not None)
    nav = sections = ''
    for i, a in enumerate(areas, 1):
        nav += f'<a href="#area-{i:02}"><span class="nav-num">{i:02}</span><span>{a["title"]}</span></a>'
        index = arts = ''
        for it in a['items']:
            new = it['body'] is not None
            index += f'<li><a href="#p-{it["id"]}">{it["title"]}</a>{" <small>· 부록에서 설명</small>" if new else ""}</li>'
            see = ''.join(f'<li><a href="{s["href"]}">{s["label"]}</a>' + (f' — {s["note"]}' if s['note'] else '') + '</li>' for s in it['see'])
            refs = ''.join(f'<li><span><a href="{u}" target="_blank" rel="noopener">{t} ↗</a>' + (f' <small>· {note}</small>' if note else '') + '</span></li>' for u, t, note in it['refs'])
            arts += (f'<article class="pitfall{" is-new" if new else ""}" id="p-{it["id"]}"><h3>{it["title"]}</h3>'
                     f'<div class="lesson-tags"><span class="book-tag">{it["harm"]}</span><span>{"부록에서 설명" if new else "강의에 있음"}</span></div>'
                     f'<p class="pitfall-symptom">{it["symptom"]}</p>'
                     + (it['body'] if new else '')
                     + (f'<div class="pitfall-see"><b>{"관련 강의" if new else "강의에서 보기"}</b><ul>{see}</ul></div>' if see else '')
                     + (f'<details class="further"><summary>근거</summary><ul class="ref-list">{refs}</ul></details>' if refs else '') + '</article>')
        sections += (f'<section class="prose pitfall-area" id="area-{i:02}"><h2><span>{i:02}</span> {a["title"]}</h2><p>{a["desc"]}</p>'
                     f'<details class="lesson-toc" open><summary>이 영역의 실수 {len(a["items"])}개</summary><ol>{index}</ol></details>{arts}</section>')
    return f'''{head(f"부록 · 흔하지만 치명적인 실수 · {SITE_TITLE}", "자바·스프링·JPA에서 누구나 한 번쯤 저지르지만 결과가 큰 실수를 모았다.")}<body><a class="skip" href="#main">본문으로 건너뛰기</a>
{sidebar_header("APPENDIX", "흔하지만 치명적인 실수")}<div class="sidebar-intro">한 줄의 실수가<br><b>장애가 되는 자리.</b></div>{sidebar_search("부록 항목 검색", "찾고 싶은 실수나 키워드")}<nav aria-label="영역"><div id="nav-results" hidden></div><a class="overview-link" href="index.html">← 전체 로드맵</a><div class="nav-group"><p>영역</p>{nav}</div></nav><div class="sidebar-bottom"><span>{n_all} PITFALLS</span><span>APPENDIX</span></div></aside>
<div class="shell"><header class="topbar"><button id="menu-toggle" class="icon-button" type="button" aria-controls="sidebar" aria-expanded="false" hidden><span aria-hidden="true">☰</span> <span class="menu-label">목차 열기</span></button><span id="current-label">부록 · 흔하지만 치명적인 실수</span><div class="top-actions"><span id="progress-label">{n_all}개 · 부록에서 설명 {n_new}개</span><button id="theme-toggle" class="icon-button" type="button" aria-label="테마 전환">다크 모드</button></div></header><main id="main" tabindex="-1">
<section id="home" class="page lesson"><header class="lesson-header"><p class="eyebrow">APPENDIX / {n_all} PITFALLS</p><h1 tabindex="-1">흔하지만 치명적인 실수</h1><p class="deck">한두 줄로 저지르기 쉽고, 데이터가 깨지거나 서버가 멈추거나 조용히 틀린 결과가 나가는 실수를 영역별로 모았다.</p></header>
<div class="prose"><p>강의 본문에서 이미 다룬 실수는 <b>증상 한 줄과 해당 회차의 소제목 링크</b>만 두었다. 원리는 그 회차에서 읽는다. 강의 본문에 없는 실수 {n_new}개는 <b>이 부록 안에서</b> 왜 그렇게 되는지, 어떻게 재현되는지, 어떻게 고치는지를 설명한다. 각 항목의 꼬리표는 그 실수가 주로 낳는 결과({" · ".join(HARMS)})다.</p></div>
{sections}</section>
<footer class="site-footer"><span>{SITE_TITLE} · APPENDIX</span><a href="index.html">전체 로드맵</a><span>로컬 학습 자료 · 외부 분석 도구 없음</span></footer></main></div>
<script src="assets/vendor/highlightjs/highlight.min.js"></script><script src="assets/code-highlight.js"></script>
</body></html>'''


def appendix(lesson, write=True):
    """부록 영역 파일을 모두 읽어 (areas, {파일: 오류}) 를 돌려준다. 오류가 없는 영역만 페이지에 넣는다."""
    areas, problems, seen = [], {}, {}
    for f in sorted(APPX.glob('[0-9][0-9]-*.html')):
        A, errors = parse_area(f, lesson)
        for it in A['items']:
            if it['id'] in seen:
                errors.append(f'항목 {it["id"]}: {seen[it["id"]]}에 같은 id가 있다.')
            seen.setdefault(it['id'], f.name)
        if errors:
            problems[f.name] = errors
        else:
            areas.append(A)
    if write and areas:
        (ROOT / APPX_FILE).write_text(appendix_page(areas), encoding='utf-8')
    return areas, problems


# ---------------------------------------------------------------------------
# 산출물
# ---------------------------------------------------------------------------
STYLE_GUIDE = '''```
Style: clean flat vector illustration / infographic for a Korean software-engineering course. No gradients, no 3D, no photos, no realistic human faces (simple role icons only if needed). Generous whitespace, thin 2px lines, rounded rectangles.
Palette: paper background #f5f4ee, ink text #172f31, dark green #153936, accent green #096650, lime #c8e6ad, muted sage for secondary shapes, amber #b68524 for warnings, red-brown #b2412e used sparingly for errors.
Typography: a clean sans-serif; Korean labels must be rendered exactly as given in the prompt (do not translate or paraphrase). Keep label count small so text stays legible.
Output: paper-colored background (#f5f4ee), short labels and clear strokes that stay legible at 720 pixels wide. Export the final asset as compressed WebP. No watermark, no decorative clutter.
```'''


def image_prompts(done):
    vis = [(v, L) for vol in VOLUMES for _, L in sorted(done[vol['slug']].items()) for v in L['visuals']
           if not (ROOT / visual_path(v['id'])).is_file()]
    md = ['# 이미지 생성 프롬프트', '',
          f'아직 만들지 않은 그림 {len(vis)}장의 위치·목적·프롬프트다. `build.py`가 회차 원고의 `<x-visual>`에서 그림 파일이 없는 항목을 모은다.',
          '', '## 쓰는 법', '',
          '1. 아래 **공통 스타일 가이드**를 각 프롬프트 앞에 붙여 이미지 생성 모델에 넘긴다.',
          '2. `python3 tools/save_visual.py <ID> <원본 파일> --remove-source`로 최대 너비 720픽셀의 `assets/visuals/<ID>.webp`를 저장한다. 변환 파일을 검사한 뒤 원본을 삭제한다.',
          '3. 해당 권의 HTML을 다시 열면 그 자리에 그림이 나타난다(파일이 없는 자리는 숨겨진다). 다시 빌드할 필요는 없다.',
          '4. `python3 build.py images`를 실행해 저장한 그림을 이 목록에서 제외한다.',
          '', '## 공통 스타일 가이드', '', STYLE_GUIDE, '']
    cur = None
    for v, L in vis:
        vol = L['vol']
        if cur != vol['slug']:
            cur = vol['slug']
            md += ['---', '', f'# VOL {vol["no"]:02} · {vol["short"]} (`{vol["no"]:02}-{vol["slug"]}.html`)', '']
        md += [f'## `{v["id"]}`', '',
               f'- **파일명**: `{visual_path(v["id"]).as_posix()}`',
               f'- **위치**: {L["num"]:02}회 「{L["title"]}」',
               f'- **제목(alt)**: {v["title"]}',
               f'- **형식 · 비율**: {v["kind"]} · {v["ratio"]}',
               f'- **이 그림이 보여 줘야 하는 것**: {text_of(v["hint"])}', '',
               '**프롬프트** (공통 스타일 가이드 뒤에 이어서):', '', '```', v['prompt'].strip(), '```', '']
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=ROOT, delete=False) as tmp:
        staging = Path(tmp.name)
        tmp.write('\n'.join(md))
    try:
        staging.chmod(0o644)
        staging.replace(ROOT / 'IMAGE_PROMPTS.md')
    finally:
        staging.unlink(missing_ok=True)
    return len(vis)


def status(done, problems):
    total = sum(len(v['lessons']) for v in VOLUMES)
    ok = sum(len(x) for x in done.values())
    md = ['# 진행 현황 (build.py가 자동 생성)', '', f'- 작성 완료: **{ok} / {total}회**', f'- 형식 오류가 있는 원고: {len(problems)}개', '',
          '| VOL | 권 | 작성 | 검수 | 남은 회차 | 본문 글자 수 |', '|---|---|---|---|---|---|']
    for v in VOLUMES:
        d, r = done[v['slug']], reviewed(v['slug'])
        missing = [f'{i:02}' for i in range(1, len(v['lessons']) + 1) if i not in d]
        md.append(f'| {v["no"]:02} | {v["slug"]} | {len(d)}/{len(v["lessons"])} | {len(r & set(d))}/{len(d)} | {" ".join(missing) or "—"} | {sum(L["chars"] for L in d.values()):,} |')
    if problems:
        md += ['', '## 형식 오류', '']
        for k, errs in problems.items():
            md += [f'- `content/{k}.html`'] + [f'  - {e}' for e in errs[:8]]
    text = '\n'.join(md) + '\n'
    (ROOT / 'STATUS.md').write_text(text, encoding='utf-8')
    return text


def brief(slug, num):
    """작성 에이전트가 읽을 회차 브리프: 권 정보와 대응 섹션의 수업 제목만 뽑아 출력한다."""
    vol = BY_SLUG[slug]
    title, secs, scope = vol['lessons'][num - 1]
    cur = (ROOT / 'source' / 'curriculum' / f'{vol["no"]:02}-{slug}.md').read_text(encoding='utf-8')
    blocks = [b for b in re.split(r'^## ', cur, flags=re.M)[1:] if int(re.match(r'섹션 (\d+)\.', b)[1]) in secs]
    before = [v['short'] for v in VOLUMES if v['no'] < vol['no']]
    out = [f'# 작성 브리프: {slug} {num:02}회', '',
           f'- 권: VOL {vol["no"]:02} 「{vol["short"]}」 (대응 강의: {vol["course"]})',
           f'- 권 소개: {vol["desc"]}',
           f'- 이 권에서 깊이 다룰 원리: {vol["focus"]}',
           '- 이 권의 전체 회차: ' + ' / '.join(f'{i:02} {t}' for i, (t, _, _) in enumerate(vol['lessons'], 1)),
           '- 로드맵에서 이 권보다 앞선 권(독자가 이미 읽었다고 가정): ' + (', '.join(before) or '없음'),
           f'- **이 회차: {num:02}회 「{title}」 → content/{slug}/{num:02}.html**']
    if scope:
        out.append(f'- 범위 메모(한 섹션을 나눠 쓴다): {scope}')
    out += ['', '## 이 회차가 다뤄야 할 주제 (인프런에 공개된 커리큘럼의 섹션·수업 제목)', '']
    out += ['### ' + b.strip() + '\n' for b in blocks]
    print('\n'.join(out))


def todo(limit):
    """아직 없거나 검사에 실패하는 회차를 로드맵 순서대로 JSON으로 출력한다."""
    import json
    done, _ = load()
    items = [dict(slug=v['slug'], num=i) for v in VOLUMES for i in range(1, len(v['lessons']) + 1) if i not in done[v['slug']]]
    print(json.dumps(items[:limit] if limit else items, ensure_ascii=False))


def main(argv):
    if argv[:1] == ['brief']:
        brief(argv[1], int(argv[2]))
        return 0
    if argv[:1] == ['todo']:
        todo(int(argv[1]) if len(argv) > 1 else 0)
        return 0
    if argv[:1] == ['appendix']:
        bad, lesson = 0, lesson_lookup()
        for a in argv[1:]:
            A, errors = parse_area(Path(a).resolve(), lesson)
            new = [it for it in A['items'] if it['body'] is not None]
            bad += bool(errors)
            print(f'[{"실패" if errors else "통과"}] {A["file"]} · 항목 {len(A["items"])} · 부록에서 설명 {len(new)}개({sum(it.get("chars", 0) for it in new):,}자) · 강의 링크 {sum(len(it["see"]) for it in A["items"])}')
            for e in errors:
                print('  오류:', e)
        return 1 if bad else 0
    if argv[:1] == ['check']:
        bad = 0
        for a in argv[1:]:
            f = Path(a).resolve()
            slug, num = f.parent.name, int(f.stem)
            L, errors, warns = parse(f, BY_SLUG[slug], num)
            bad += bool(errors)
            print(f'[{"실패" if errors else "통과"}] {slug}/{num:02} · 본문 {L.get("chars", 0):,}자 · 그림 {len(L["visuals"])} · 퀴즈 {len(L.get("quiz", []))}')
            for e in errors:
                print('  오류:', e)
            for w in warns:
                print('  경고:', w)
        return 1 if bad else 0
    done, problems = load()
    if argv[:1] == ['images']:
        if problems:
            print('형식 오류가 있는 원고가 있어 이미지 목록을 갱신할 수 없습니다.', file=sys.stderr)
            return 1
        print('미생성 그림:', image_prompts(done))
        return 0
    if argv[:1] != ['status']:
        for vol in VOLUMES:
            page, file = volume_page(vol, done[vol['slug']])
            (ROOT / file).write_text(page, encoding='utf-8')
        (ROOT / 'index.html').write_text(hub_page(done), encoding='utf-8')
        print('미생성 그림:', image_prompts(done))
        areas, bad = appendix(lesson_lookup(done))
        print(f'부록: 영역 {len(areas)} · 항목 {sum(len(a["items"]) for a in areas)}' + ''.join(f'\n  부록 오류 {k}: {e}' for k, es in bad.items() for e in es))
    print(status(done, problems))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
