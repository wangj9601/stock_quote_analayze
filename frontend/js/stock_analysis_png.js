/**
 * 个股分析 · PNG 长图导出（html2canvas，失败时回退 SVG foreignObject）
 * 覆盖页面可见结果：策略 / 阻力支撑 / 形态 / 波段趋势 / 江恩扇形
 */
(function (global) {
  const MAX_CANVAS = 16384;
  const H2C_CDN = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js';
  const H2C_LOCAL = 'js/vendor/html2canvas.min.js';

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const el = document.createElement('script');
      el.async = true;
      el.src = src;
      el.onload = () => resolve();
      el.onerror = () => reject(new Error(`加载脚本失败: ${src}`));
      document.head.appendChild(el);
    });
  }

  async function ensureHtml2Canvas() {
    if (typeof global.html2canvas === 'function') return global.html2canvas;
    try {
      await loadScript(H2C_LOCAL);
    } catch (_) {
      /* 本地 vendor 缺失时走 CDN */
    }
    if (typeof global.html2canvas === 'function') return global.html2canvas;
    await loadScript(H2C_CDN);
    if (typeof global.html2canvas !== 'function') {
      throw new Error('html2canvas 未加载');
    }
    return global.html2canvas;
  }

  function pickCaptureScale(width, height, preferred) {
    const w = Math.max(1, Number(width) || 1);
    const h = Math.max(1, Number(height) || 1);
    const pref = preferred != null && Number.isFinite(Number(preferred)) ? Number(preferred) : 2;
    const scale = Math.min(pref, MAX_CANVAS / w, MAX_CANVAS / h);
    return Math.max(1, Math.floor(scale * 100) / 100);
  }

  function pngFilenameFromHost(host) {
    if (host && typeof host.pngFilename === 'function') return host.pngFilename();
    if (host && typeof host.pdfFilename === 'function') {
      return String(host.pdfFilename()).replace(/\.pdf$/i, '.png');
    }
    return '个股分析.png';
  }

  function isPngIgnoreElement(el) {
    if (!el) return false;
    if (el.id === 'ssaGannTradeObserveBtn') return true;
    const cls = el.classList;
    if (cls && (cls.contains('ssa-card-links') || cls.contains('ssa-scroll-fab'))) return true;
    if (el.tagName === 'A' && cls && cls.contains('ssa-link')) return true;
    return false;
  }

  function flattenDetailsForCapture(root) {
    if (!root || typeof root.querySelectorAll !== 'function') return;
    root.querySelectorAll('details').forEach((details) => {
      const doc = details.ownerDocument || document;
      const box = doc.createElement('div');
      box.className = `${details.className || ''} ms-details-static`.trim();
      const summary = details.querySelector('summary');
      if (summary) {
        const title = doc.createElement('div');
        title.className = 'ms-details-static-title';
        title.textContent = summary.textContent || '';
        box.appendChild(title);
        summary.remove();
      }
      while (details.firstChild) box.appendChild(details.firstChild);
      details.replaceWith(box);
    });
  }

  function fixSvgLayout(root) {
    if (!root || typeof root.querySelectorAll !== 'function') return;
    root.querySelectorAll('svg.ms-zigzag-svg, svg.gann-fan-svg').forEach((svg) => {
      const vb = String(svg.getAttribute('viewBox') || '')
        .trim()
        .split(/[\s,]+/);
      const vw = Number(vb[2]);
      const vh = Number(vb[3]);
      if (Number.isFinite(vw) && vw > 0) svg.setAttribute('width', String(vw));
      if (Number.isFinite(vh) && vh > 0) {
        svg.setAttribute('height', String(vh));
        svg.style.height = `${vh}px`;
        svg.style.maxHeight = 'none';
      }
      svg.style.display = 'block';
      const wrap = svg.parentElement;
      if (wrap && wrap.style) wrap.style.overflow = 'visible';
    });
  }

  function setDetailsOpen(root, open) {
    const states = [];
    if (!root || typeof root.querySelectorAll !== 'function') return states;
    root.querySelectorAll('details').forEach((el) => {
      states.push({ el, open: !!el.open });
      el.open = !!open;
    });
    return states;
  }

  function restoreDetails(states) {
    (states || []).forEach((s) => {
      if (s && s.el) s.el.open = s.open;
    });
  }

  function prepareClone(clonedDoc) {
    clonedDoc.body.classList.add('ssa-png-capturing');
    const root = clonedDoc.getElementById('ssaExportRoot');
    if (!root) return;
    root.classList.add('ssa-png-shot');
    root.querySelectorAll('[hidden]').forEach((n) => n.remove());
    root.querySelectorAll('#ssaGannTradeObserveBtn, .ssa-card-links, a.ssa-link').forEach((n) => n.remove());
    flattenDetailsForCapture(root);
    fixSvgLayout(root);
    if (!root.querySelector('.ssa-png-title')) {
      const title = clonedDoc.createElement('h3');
      title.className = 'ssa-png-title';
      title.textContent = '个股分析结果';
      root.insertBefore(title, root.firstChild);
    }
  }

  function collectPageCss() {
    const parts = [];
    Array.from(document.styleSheets || []).forEach((sheet) => {
      try {
        const rules = sheet.cssRules;
        if (!rules) return;
        Array.from(rules).forEach((rule) => parts.push(rule.cssText));
      } catch (_) {
        if (sheet.href) parts.push(`@import url('${sheet.href}');`);
      }
    });
    return parts.join('\n');
  }

  function downloadCanvas(canvas, filename) {
    return new Promise((resolve, reject) => {
      const finish = (href) => {
        const a = document.createElement('a');
        a.href = href;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        resolve(filename);
      };
      if (typeof canvas.toBlob === 'function') {
        canvas.toBlob((blob) => {
          if (!blob) {
            try {
              finish(canvas.toDataURL('image/png'));
            } catch (e) {
              reject(e);
            }
            return;
          }
          const url = URL.createObjectURL(blob);
          finish(url);
          setTimeout(() => URL.revokeObjectURL(url), 4000);
        }, 'image/png');
        return;
      }
      try {
        finish(canvas.toDataURL('image/png'));
      } catch (e) {
        reject(e);
      }
    });
  }

  async function captureViaSvg(root, scale) {
    const width = Math.max(1, Math.ceil(root.scrollWidth || root.offsetWidth || 800));
    const height = Math.max(1, Math.ceil(root.scrollHeight || root.offsetHeight || 1));
    const clone = root.cloneNode(true);
    clone.classList.add('ssa-png-shot');
    clone.querySelectorAll('[hidden]').forEach((n) => n.remove());
    clone.querySelectorAll('#ssaGannTradeObserveBtn, .ssa-card-links, a.ssa-link').forEach((n) => n.remove());
    flattenDetailsForCapture(clone);
    fixSvgLayout(clone);
    if (!clone.querySelector('.ssa-png-title')) {
      const title = document.createElement('h3');
      title.className = 'ssa-png-title';
      title.textContent = '个股分析结果';
      clone.insertBefore(title, clone.firstChild);
    }
    clone.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
    const css = collectPageCss();
    const inner = new XMLSerializer().serializeToString(clone);
    const svg =
      `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">` +
      `<foreignObject width="100%" height="100%">` +
      `<div xmlns="http://www.w3.org/1999/xhtml" style="width:${width}px;background:#fff;">` +
      `<style>${css}</style>${inner}</div></foreignObject></svg>`;
    const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    try {
      const img = await new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error('SVG 栅格化失败'));
        image.src = url;
      });
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.floor(width * scale));
      canvas.height = Math.max(1, Math.floor(height * scale));
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      return canvas;
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  async function waitFonts() {
    try {
      if (document.fonts && document.fonts.ready) await document.fonts.ready;
    } catch (_) {
      /* ignore */
    }
  }

  /**
   * @param {object} host StockMultiStrategy
   * @returns {Promise<string>} 文件名
   */
  async function exportFromHost(host) {
    if (!host || typeof host.hasExportableResult !== 'function' || !host.hasExportableResult()) {
      throw new Error('请先完成个股分析再导出');
    }
    const root = document.getElementById('ssaExportRoot');
    if (!root) throw new Error('未找到分析结果区域');
    const prevDetails = setDetailsOpen(root, true);
    try {
      await new Promise((resolve) => {
        if (typeof requestAnimationFrame === 'function') {
          requestAnimationFrame(() => requestAnimationFrame(resolve));
        } else {
          setTimeout(resolve, 32);
        }
      });
      const width = Math.max(1, root.scrollWidth || root.offsetWidth || 0);
      const height = Math.max(1, root.scrollHeight || root.offsetHeight || 0);
      if (height < 8) throw new Error('当前没有可导出的分析结果');
      const scale = pickCaptureScale(width, height, 2);
      const filename = pngFilenameFromHost(host);
      await waitFonts();

      let canvas = null;
      try {
        const html2canvas = await ensureHtml2Canvas();
        canvas = await html2canvas(root, {
          backgroundColor: '#ffffff',
          scale,
          useCORS: true,
          logging: false,
          ignoreElements: isPngIgnoreElement,
          onclone: prepareClone,
        });
      } catch (e) {
        console.warn('html2canvas 导出失败，回退 SVG', e);
        canvas = await captureViaSvg(root, scale);
      }
      if (!canvas) throw new Error('生成 PNG 失败');
      await downloadCanvas(canvas, filename);
      return filename;
    } finally {
      restoreDetails(prevDetails);
    }
  }

  global.StockAnalysisPng = {
    exportFromHost,
    pickCaptureScale,
    pngFilenameFromHost,
    isPngIgnoreElement,
    flattenDetailsForCapture,
    fixSvgLayout,
    MAX_CANVAS,
  };
})(typeof window !== 'undefined' ? window : globalThis);
