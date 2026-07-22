import type { Person } from './types';

export function personName(p: Person): string {
  return [p.first, p.last].filter(Boolean).join(' ');
}

export function isRemotePhoto(url: string | undefined): boolean {
  return !!url && /^https?:\/\//i.test(url);
}
