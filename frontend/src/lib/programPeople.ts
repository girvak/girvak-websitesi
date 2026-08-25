import type { Person } from './types';
import { isUnbundled } from './images';

export function personName(p: Person): string {
  return [p.first, p.last].filter(Boolean).join(' ');
}

export function isRemotePhoto(url: string | undefined): boolean {
  return isUnbundled(url);
}
