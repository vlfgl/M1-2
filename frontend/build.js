// Vercel 빌드 스크립트: 정적 파일을 dist/로 복사하고,
// 환경변수 API_BASE_URL로 dist/config.js를 생성한다. (외부 패키지 없음)
const fs = require("fs");
const path = require("path");

const apiBase = (process.env.API_BASE_URL || "").trim().replace(/\/+$/, "");
if (!apiBase) {
  console.error("✗ API_BASE_URL 환경변수가 없습니다. Vercel Project Settings → Environment Variables에서 설정하세요.");
  process.exit(1);
}
if (!/^https?:\/\//.test(apiBase)) {
  console.error(`✗ API_BASE_URL은 http(s)://로 시작해야 합니다: ${apiBase}`);
  process.exit(1);
}

const out = path.join(__dirname, "dist");
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out);
for (const f of ["index.html", "style.css", "app.js"]) {
  fs.copyFileSync(path.join(__dirname, f), path.join(out, f));
}
fs.writeFileSync(
  path.join(out, "config.js"),
  `window.APP_CONFIG = ${JSON.stringify({ API_BASE_URL: apiBase })};\n`
);
console.log(`✓ dist/ 생성 완료 (API_BASE_URL=${apiBase})`);
