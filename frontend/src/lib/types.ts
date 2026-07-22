// Mirrors the backend Pydantic models (backend/app/models.py).

export type AccentColor = 'teal' | 'coral' | 'ink';

export interface CTA {
  label: string;
  href: string;
}

export interface SEO {
  title: string;
  description: string;
}

export interface Hero {
  base_text: string;
  rotator_words: string[];
  subhead_pre: string;
  subhead_highlight: string;
  subhead_post: string;
  ctas: CTA[];
  images: string[];
}

export interface ImpactTile {
  count: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  label: string;
  desc: string;
  color: AccentColor;
  row: number;
  col: number;
}

export interface WhatWeDoCard {
  href: string;
  image: string;
  lead: string;
  sub: string;
  eyebrow: string;
  text: string;
  color: AccentColor;
}

export interface Fellow {
  year: string;
  name: string;
  university: string;
  department?: string;
  image: string;
  color: AccentColor;
}

export interface Partner {
  name: string;
  logo: string;
}

export interface Partners {
  headline_pre: string;
  headline_highlight: string;
  sub: string;
  ctas: CTA[];
  featured: Partner;
  logos: Partner[];
}

export interface FooterContact {
  address: string;
  email: string;
  phone: string;
  phone_href: string;
}

export interface Footer {
  newsletter_title: string;
  newsletter_text: string;
  brand_text: string;
  explore_links: CTA[];
  contact: FooterContact;
  copyright: string;
}

export interface HomeContent {
  seo: SEO;
  hero: Hero;
  impact: ImpactTile[];
  impact_image: string;
  what_we_do: WhatWeDoCard[];
  fellows: Fellow[];
  partners: Partners;
  footer: Footer;
}

// People (about page) — mirrors backend Person / PeopleContent.
export interface Person {
  first: string;
  last?: string;
  company?: string;
  position?: string;
  university?: string;
  department?: string;
  photo?: string;
  linkedin?: string;
  roles?: string[];
  year?: string;
  color?: string;
}

export interface PeopleContent {
  trustees: Person[];   // Airtable tag "mh"  (Board of Trustees)
  directors: Person[];  // Airtable tag "yk"  (Board of Directors)
  team: Person[];       // Airtable tag "team"
  fellows: Person[];    // Airtable tag "fellow"
  alumni: Person[];     // Airtable tag "alumni"
  challengers: Person[]; // Airtable tag "challenger"
}

export interface AboutMission {
  kicker: string;
  headline: string;
  image: string;
}

export interface AboutWwsStrip {
  label: string;
  headline: string;
  desc: string;
  overlay_color: string;
  image: string;
}

export interface AboutSectionHead {
  headline: string;
  subheadline: string;
}

export interface AboutCtaBand {
  headline: string;
  text: string;
  cta_label: string;
  cta_href: string;
}

export interface AboutContent {
  seo_title: string;
  seo_description: string;
  hero_html: string;
  about_paragraphs: string[];
  mission: AboutMission;
  story_headline: string;
  story_paragraphs: string[];
  what_we_solve_headline: string;
  what_we_solve_strips: AboutWwsStrip[];
  trustees: AboutSectionHead;
  directors: AboutSectionHead;
  team: AboutSectionHead;
  reports: AboutCtaBand;
  work_with_us: AboutCtaBand;
}
