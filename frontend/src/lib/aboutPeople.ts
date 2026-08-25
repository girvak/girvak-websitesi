// ============================================================
// GİRVAK — About page people (Airtable-ready shape)
// Fields per person mirror the design's about.js:
//   photo, first, last, company, position, linkedin, color
// Real team + featured directors are listed below; the remaining
// trustee/director cards are deterministic placeholders (no photo →
// they render as coloured initials) until a People table is wired up.
// ============================================================
export interface Person {
  first: string;
  last: string;
  company?: string;
  position?: string;
  photo?: string;
  color?: string;
  linkedin?: string;
}

// GİRVAK team members — real photos (grayscale via CSS), turquoise band.
// Photos resolve from src/assets/images when the portraits are added there;
// until then each card falls back to initials.
export const TEAM: Person[] = [
  { first: 'Mehru', last: 'Öztürk', position: 'General Manager', photo: '/images/team-mehru.png', linkedin: 'https://www.linkedin.com/' },
  { first: 'Cemre', last: 'Şirin', position: 'Director of Business Development & Innovation', photo: '/images/team-cemre.png', linkedin: 'https://www.linkedin.com/' },
  { first: 'Alara', last: 'Üçüncüoğlu', position: 'Business Development & Projects Manager', photo: '/images/team-alara.png', linkedin: 'https://www.linkedin.com/' },
  { first: 'Deniz Hale', last: 'Durakbaşı', position: 'Impact Manager', photo: '/images/team-deniz.png', linkedin: 'https://www.linkedin.com/' },
  { first: 'Murat', last: 'Ulutaş', position: 'Accounting & Finance Manager', photo: '/images/team-murat.png', linkedin: 'https://www.linkedin.com/' },
  { first: 'Selin', last: 'Altuntecim', position: 'Senior Fellow Program Coordinator', photo: '/images/team-selin.png', linkedin: 'https://www.linkedin.com/' },
  { first: 'İrem', last: 'Karaosmanoğlu', position: 'Senior Brand & Communications Coordinator', photo: '/images/team-irem.png', linkedin: 'https://www.linkedin.com/' },
  { first: 'Merve', last: 'Tekeoğlu', position: 'Senior Program Coordinator', photo: '/images/team-merve.png', linkedin: 'https://www.linkedin.com/' },
  { first: 'Elif Gözde', last: 'Kayrak', position: 'Senior Projects Coordinator', photo: '/images/team-elif.png', linkedin: 'https://www.linkedin.com/' },
  { first: 'Mürvet', last: 'Çırpan', position: 'Fellow Program Coordinator', photo: '/images/team-murvet.png', linkedin: 'https://www.linkedin.com/' },
  { first: 'Rana', last: 'Kaya', position: 'Project Coordinator', photo: '/images/team-rana.png', linkedin: 'https://www.linkedin.com/' },
  { first: 'Şevval', last: 'Cihanyaka', position: 'Project Coordinator', photo: '/images/team-sevval.png', linkedin: 'https://www.linkedin.com/' },
];

// Featured board members with real photos + baked accent colour.
export const FEATURED: Person[] = [
  { first: 'Alemşah', last: 'Öztürk', company: '4129Grey', position: 'CEO & Chief Happiness Officer', photo: '/images/about-alemsah.png', color: '#44C3D6', linkedin: 'https://www.linkedin.com/' },
  { first: 'Ahu', last: 'Serter', company: 'Arya Women Investment Platform', position: 'Founder & Chair', photo: '/images/about-ahu.png', color: '#F76D54', linkedin: 'https://www.linkedin.com/' },
  { first: 'Barbaros', last: 'Özbuğutu', company: 'iyzico', position: 'Founder & CEO', photo: '/images/about-barbaros.png', color: '#373D43', linkedin: 'https://www.linkedin.com/' },
];

// Deterministic placeholder people (no photo → initials cards), matching the
// design's generator. Swap for a live Airtable fetch later.
const FIRSTS = ['Ahmet', 'Elif', 'Mehmet', 'Zeynep', 'Can', 'Deniz', 'Burak', 'Selin', 'Emre', 'Aylin', 'Kerem', 'Ece', 'Murat', 'Naz', 'Onur', 'Pınar', 'Tolga', 'Sıla', 'Barış', 'Derya'];
const LASTS = ['Yılmaz', 'Demir', 'Kaya', 'Çelik', 'Şahin', 'Aydın', 'Öztürk', 'Arslan', 'Doğan', 'Koç', 'Kurt', 'Eren', 'Aksoy', 'Polat', 'Taş', 'Acar', 'Bulut', 'Güneş', 'Yıldız', 'Çetin'];
const COMPANIES = ['Koç Holding', 'Sabancı', 'TSKB', 'ÜNLÜ & Co', 'Garanti BBVA', 'Türk Telekom', 'Vodafone', 'Arçelik', 'Anadolu Group', 'Doğuş', 'Eczacıbaşı', 'Boyner', 'Zorlu', 'Borusan', 'Enka'];
const TITLES = ['Chair', 'Board Member', 'Founder', 'CEO', 'Managing Partner', 'Investor', 'Vice Chair', 'Advisor'];

export function makePeople(n: number, seed: number): Person[] {
  const arr: Person[] = [];
  for (let i = 0; i < n; i++) {
    const s = i + seed;
    arr.push({
      first: FIRSTS[(s * 3) % FIRSTS.length],
      last: LASTS[(s * 7) % LASTS.length],
      company: COMPANIES[(s * 5) % COMPANIES.length],
      position: TITLES[(s * 2) % TITLES.length],
      linkedin: 'https://www.linkedin.com/',
    });
  }
  return arr;
}

/** Turkish alphabetical sort by full name (first + last), matching Airtable `name`. */
export function sortPeopleAlpha<T extends { first: string; last?: string }>(people: T[]): T[] {
  return [...people].sort((a, b) => {
    const an = `${a.first} ${a.last ?? ''}`.trim();
    const bn = `${b.first} ${b.last ?? ''}`.trim();
    return an.localeCompare(bn, 'tr', { sensitivity: 'base' });
  });
}

/** Board of directors (yk): Sina first, Yomi second, then Turkish A–Z. */
const TRUSTEE_PRIORITY = ['sina', 'yomi'];

export function sortTrusteesPriority<T extends { first: string; last?: string }>(people: T[]): T[] {
  const full = (p: T) => `${p.first} ${p.last ?? ''}`.trim();
  const rank = (p: T) => {
    const first = p.first.trim().toLocaleLowerCase('tr');
    const fn = full(p).toLocaleLowerCase('tr');
    for (let i = 0; i < TRUSTEE_PRIORITY.length; i++) {
      const key = TRUSTEE_PRIORITY[i];
      if (first === key || fn.startsWith(`${key} `)) return i;
    }
    return TRUSTEE_PRIORITY.length;
  };
  return [...people].sort((a, b) => {
    const dr = rank(a) - rank(b);
    if (dr !== 0) return dr;
    return full(a).localeCompare(full(b), 'tr', { sensitivity: 'base' });
  });
}

// Uniform brand colour per section: trustees = GİRVAK grey, directors = coral,
// team = turquoise (see PeopleGrid `forceColor`).
export const trustees: Person[] = sortPeopleAlpha(makePeople(10, 1));
export const directors: Person[] = sortPeopleAlpha(FEATURED.concat(makePeople(5, 40)));
export const team: Person[] = sortPeopleAlpha(TEAM);
