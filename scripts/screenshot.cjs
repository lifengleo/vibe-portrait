/**
 * 截图脚本（被 run.py 调用）
 * 通过环境变量传参：
 *   VIBE_HTML — 要截的 index.html 绝对路径
 *   VIBE_OUT  — 输出目录
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const HTML = process.env.VIBE_HTML;
const OUT_DIR = process.env.VIBE_OUT;

if (!HTML || !OUT_DIR) {
  console.error("Missing VIBE_HTML / VIBE_OUT env");
  process.exit(1);
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 900, height: 1200 },  // 大于 768 避免移动断点
    deviceScaleFactor: 3,
  });
  const page = await ctx.newPage();
  await page.goto('file://' + HTML, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1200);

  const pngPath = path.join(OUT_DIR, 'portrait.png');
  await page.locator('.poster').screenshot({ path: pngPath, type: 'png' });
  await browser.close();

  // 用 sharp 转 JPG（hd + share 两版）
  let sharp;
  try {
    sharp = require('sharp');
  } catch (e) {
    console.warn('sharp not installed, skipping JPG conversion');
    return;
  }

  await sharp(pngPath)
    .jpeg({ quality: 88, mozjpeg: true })
    .toFile(path.join(OUT_DIR, 'portrait-hd.jpg'));

  await sharp(pngPath)
    .resize({ width: 1500 })
    .jpeg({ quality: 90, mozjpeg: true })
    .toFile(path.join(OUT_DIR, 'portrait-share.jpg'));

  // 删 PNG
  fs.unlinkSync(pngPath);
  console.log('Saved JPGs to', OUT_DIR);
})();
