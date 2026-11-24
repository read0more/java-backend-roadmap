# 이미지 생성 프롬프트

아직 만들지 않은 그림 0장의 위치·목적·프롬프트다. `build.py`가 회차 원고의 `<x-visual>`에서 그림 파일이 없는 항목을 모은다.

## 쓰는 법

1. 아래 **공통 스타일 가이드**를 각 프롬프트 앞에 붙여 이미지 생성 모델에 넘긴다.
2. `python3 tools/save_visual.py <ID> <원본 파일> --remove-source`로 최대 너비 720픽셀의 `assets/visuals/<ID>.webp`를 저장한다. 변환 파일을 검사한 뒤 원본을 삭제한다.
3. 해당 권의 HTML을 다시 열면 그 자리에 그림이 나타난다(파일이 없는 자리는 숨겨진다). 다시 빌드할 필요는 없다.
4. `python3 build.py images`를 실행해 저장한 그림을 이 목록에서 제외한다.

## 공통 스타일 가이드

```
Style: clean flat vector illustration / infographic for a Korean software-engineering course. No gradients, no 3D, no photos, no realistic human faces (simple role icons only if needed). Generous whitespace, thin 2px lines, rounded rectangles.
Palette: paper background #f5f4ee, ink text #172f31, dark green #153936, accent green #096650, lime #c8e6ad, muted sage for secondary shapes, amber #b68524 for warnings, red-brown #b2412e used sparingly for errors.
Typography: a clean sans-serif; Korean labels must be rendered exactly as given in the prompt (do not translate or paraphrase). Keep label count small so text stays legible.
Output: paper-colored background (#f5f4ee), short labels and clear strokes that stay legible at 720 pixels wide. Export the final asset as compressed WebP. No watermark, no decorative clutter.
```
