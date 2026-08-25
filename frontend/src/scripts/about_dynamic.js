// About dynamic updater (client-side).
// Fetches /api/content/about and replaces key Airtable-driven sections.

import { safeHref } from '../lib/urls.ts';

(function () {
  // Dev-only. In production the site is fully static: these updaters would
  // overwrite Astro's optimized responsive images with raw backend URLs, and
  // would make the API a hard runtime dependency of every page. Content
  // changes reach production through a rebuild instead.
  if (!import.meta.env.DEV) return;
  const POLL_MS = 10 * 60 * 1000; // 10 minutes

  function escapeHtml(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function emphasizeEntrepreneurship(text) {
    const s = String(text ?? '');
    if (!s) return '';
    const normalized = s.replace(/\s+/g, ' ').trim();
    if (/^to remove the structural barriers that limit access to entrepreneurship in türkiye\.?$/i.test(normalized)) {
      return '<span class="ab-mission-line1">To remove the structural barriers that</span><br /><span class="ab-mission-line2">limit access to <em>entrepreneurship</em> in&nbsp;Türkiye.</span>';
    }
    const withBreak = normalized.replace(/that limit access to\s+/i, 'that limit access to<br />');
    // Wrap entrepreneurship in <em> so the existing CSS can style it.
    const withAccent = withBreak.replace(/entrepreneurship/gi, (m) => `<em>${escapeHtml(m)}</em>`);
    return withAccent.replace(/\bin Türkiye\b/gi, 'in&nbsp;Türkiye');
  }

  function callSplitHero() {
    if (typeof window.__girvakSplitHeroTitle === 'function') {
      window.__girvakSplitHeroTitle();
    }
  }

  async function updateAbout() {
    const resp = await fetch('/api/content/about', {
      method: 'GET',
      cache: 'no-store',
      headers: { 'Accept': 'application/json' },
    });
    if (!resp.ok) return;
    const about = await resp.json();
    if (!about) return;

    // Hero (hero_html)
    const heroTitle = document.querySelector('.ab-hero--home .ab-hero-title');
    if (heroTitle && about.hero_html) {
      heroTitle.innerHTML = about.hero_html;
      callSplitHero();
    }

    // About paragraphs
    const aboutBody = document.querySelector('#aboutus .ab-body');
    if (aboutBody && Array.isArray(about.about_paragraphs)) {
      aboutBody.innerHTML = about.about_paragraphs
        .map((p) => `<p style="width: auto; color: rgb(55, 61, 66)">${escapeHtml(p)}</p>`)
        .join('');
    }

    // Mission section
    const mission = about.mission;
    const missionPk = document.querySelector('#mission .ab-pk');
    const missionH2 = document.querySelector('#mission h2');
    const missionImg = document.querySelector('#mission .ab-photo-img');
    if (mission) {
      if (missionPk) missionPk.textContent = mission.kicker ?? '';
      if (missionH2) missionH2.innerHTML = emphasizeEntrepreneurship(mission.headline ?? '');
      if (missionImg && mission.image) missionImg.src = mission.image;
    }

    // Story headline + paragraphs
    const storyH2 = document.querySelector('#story .ab-story-head h2');
    if (storyH2) storyH2.textContent = about.story_headline ?? '';

    const storyBody = document.querySelector('#story .ab-story-body');
    if (storyBody && Array.isArray(about.story_paragraphs)) {
      storyBody.innerHTML = about.story_paragraphs
        .map((p) => `<p style="width: auto; color: rgb(55, 61, 66)">${escapeHtml(p)}</p>`)
        .join('');
    }

    // Reports
    const reportsSection = document.querySelector('#reports .ab-work-copy');
    const reportsLink = document.querySelector('#reports .h3btn');
    if (reportsSection && about.reports) {
      const h2 = reportsSection.querySelector('h2');
      const p = reportsSection.querySelector('p');
      if (h2) h2.textContent = about.reports.headline ?? '';
      if (p) p.textContent = about.reports.text ?? '';
      if (reportsLink) {
        reportsLink.href = safeHref(about.reports.cta_href, '#');
        const lbl = reportsLink.querySelector('.h3btn-label');
        if (lbl) lbl.textContent = about.reports.cta_label ?? '';
      }
    }

    // Work with us
    const workSection = document.querySelector('#work .ab-work-copy');
    const workLink = document.querySelector('#work .h3btn');
    if (workSection && about.work_with_us) {
      const h2 = workSection.querySelector('h2');
      const p = workSection.querySelector('p');
      if (h2) h2.textContent = about.work_with_us.headline ?? '';
      if (p) p.textContent = about.work_with_us.text ?? '';
      if (workLink) {
        workLink.href = safeHref(about.work_with_us.cta_href, '#');
        const lbl = workLink.querySelector('.h3btn-label');
        if (lbl) lbl.textContent = about.work_with_us.cta_label ?? '';
      }
    }
  }

  // Expose for the UI refresh button.
  window.__girvakUpdateAbout = updateAbout;

  updateAbout().catch(() => {});

  setInterval(() => {
    updateAbout().catch(() => {});
  }, POLL_MS);
})();

