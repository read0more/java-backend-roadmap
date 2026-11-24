'use strict';
// 언어를 지정한 블록만 강조해 설명용 텍스트의 언어 오인식을 피한다.
if (window.hljs) {
  document.querySelectorAll('pre code[class^="language-"]').forEach((code) => {
    window.hljs.highlightElement(code);
  });
}
